from fastapi import APIRouter, Depends, HTTPException, Path, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.crud import portfolio as crud
from app.crud import transaction as crud_tx
from app.crud import portfolio as crud_pf
from app.schemas.portfolio import PortfolioCreate, Portfolio, PositionCreate, Position

from app.services.portfolio_service import compute_portfolio_value

from app.crud.transaction import create_transaction, get_transactions
from app.schemas.transaction import Transaction, TransactionCreate, TransactionUpdate
from app.services.portfolio_pnl_service import compute_pnl
from app.services.portfolio_service import get_portfolio_24h_change_percentage
from app.services.llm_provider_service import llm_service
from app.models.user import User

from datetime import date

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
    data: PositionCreate,
    pf_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
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


@router.post(
    "/{pf_id}/transactions",
    response_model=Transaction,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new buy/sell transaction"
)
def add_transaction(
    pf_id: int,
    tx_in: TransactionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Record a new transaction (buy/sell) for a portfolio.
    """
    p = crud_pf.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")
    return crud_tx.create_transaction(db, pf_id, tx_in)


@router.get(
    "/{pf_id}/transactions",
    response_model=List[Transaction],
    summary="List transactions with pagination & date filtering"
)
def list_transactions(
    pf_id: int = Path(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, gt=0, le=200),
    start: Optional[date] = Query(None, description="YYYY-MM-DD"),
    end:   Optional[date] = Query(None, description="YYYY-MM-DD"),
    db:    Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List transactions for a portfolio with optional pagination and date filtering.
    """
    p = crud_pf.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return crud_tx.get_transactions(
        db, pf_id, skip=skip, limit=limit,
        start=str(start) if start else None,
        end=str(end) if end else None
    )

@router.get("/{pf_id}/pnl")
async def get_portfolio_pnl(
    pf_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Compute the PnL of a portfolio.
    """
    p = crud.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")
    return await compute_pnl(db, pf_id)

@router.get("/{pf_id}/change-24h") # NEW ENDPOINT
async def get_portfolio_24h_change(
    pf_id: int = Path(..., gt=0, description="The ID of the portfolio to calculate 24h change for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Compute the overall 24-hour percentage change of the portfolio.
    """
    p = crud.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    change_percentage = await get_portfolio_24h_change_percentage(db, portfolio_id=pf_id)
    
    return {
        "portfolio_id": pf_id,
        "change_24h_percentage": change_percentage
    }

@router.put(
    "/{pf_id}/transactions/{tx_id}",
    response_model=Transaction,
    summary="Update an existing transaction"
)
def update_transaction(
    pf_id: int,
    tx_id: int,
    tx_in: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update an existing transaction record.
    """
    p = crud_pf.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")
    tx = crud_tx.update_transaction(db, tx_id, tx_in)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    return tx

@router.delete(
    "/{pf_id}/transactions/{tx_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a transaction record"
)
def delete_transaction(
    pf_id: int,
    tx_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a transaction record.
    """
    p = crud_pf.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")
    success = crud_tx.delete_transaction(db, tx_id)
    if not success:
        raise HTTPException(404, "Transaction not found")
    # Deleting the record simply removes it; your P&L & holdings
    # will be recalculated on next request from remaining transactions.
    return

@router.get("/positions/search-by-symbol", response_model=List[Position])
def get_all_user_positions_by_symbol(
    symbol: str = Query(..., description="Stock symbol to search for (e.g., AAPL)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all positions for a specific symbol across all of the current user's portfolios.
    """
    # The function get_all_positions_for_symbol_by_user is assumed to be in your crud.portfolio module
    # (aliased as 'crud' or 'crud_pf' in your imports)
    positions = crud.get_all_positions_for_symbol_by_user(db=db, user_id=current_user.id, symbol=symbol)
    if not positions:
        # It's common to return an empty list if no positions are found,
        # but you could raise 404 if you prefer that behavior for no matches.
        # For now, returning an empty list is standard.
        pass # Return empty list if no positions are found
    return positions