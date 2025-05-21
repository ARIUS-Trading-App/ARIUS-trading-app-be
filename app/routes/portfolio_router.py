from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.crud import portfolio as crud
from app.schemas.portfolio import PortfolioCreate, Portfolio, PositionCreate, Position

from app.services.portfolio_service import compute_portfolio_value


router = APIRouter(prefix="/portfolios", tags=["Portfolios"])

@router.post("/", response_model=Portfolio)
def create_portfolio(
    data: PortfolioCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new portfolio for the current user.
    """
    return crud.create_portfolio(db, current_user.id, data)

@router.get("/", response_model=List[Portfolio])
def list_portfolios(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List all portfolios for the current user.
    """
    return crud.get_portfolios(db, current_user.id)

@router.post("/{pf_id}/positions", response_model=Position)
def add_position(
    pf_id: int = Path(..., gt=0),
    data: PositionCreate = Depends(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Add a position to a portfolio.
    """
    p = crud.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")
    return crud.create_position(db, pf_id, data)

@router.get("/{pf_id}/positions", response_model=List[Position])
def list_positions(
    pf_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List all positions in a portfolio.
    """
    p = crud.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")
    return crud.get_positions(db, pf_id)


@router.get("/{pf_id}/value")
async def get_portfolio_value(
    pf_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Compute the value of a portfolio.
    """
    p = crud.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")
    value = await compute_portfolio_value(db, pf_id)
    return {"portfolio_id": pf_id, "value": value}

@router.get("/{pf_id}/insights")
async def portfolio_insights(
    pf_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Generate insights for a portfolio using LLM.
    """
    p = crud.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")

    positions = crud.get_positions(db, pf_id)
    summary = "\n".join([f"{pos.symbol}: {pos.quantity} shares" for pos in positions])

    prompt = (
        f"User's portfolio:\n{summary}\n"
        "Provide 3 concise bullet points on diversification, "
        "performance expectations, and potential risks."
    )

    insight = await llm_service.generate_response(prompt)

    return {"portfolio_id": pf_id, "insight": insight}
