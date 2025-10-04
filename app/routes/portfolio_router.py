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

from app.services.llm_provider_service import llm_service

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
    """Creates a new, empty portfolio for the currently authenticated user.
    
    Args:
        data (PortfolioCreate): The name for the new portfolio.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        Portfolio: The newly created portfolio object.
    """
    return crud.create_portfolio(db, current_user.id, data)

@router.get("/", response_model=List[Portfolio])
def list_portfolios(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Lists all portfolios belonging to the currently authenticated user.
    
    Args:
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        List[Portfolio]: A list of the user's portfolios.
    """
    return crud.get_portfolios(db, current_user.id)

@router.post("/{pf_id}/positions", response_model=Position)
def add_position(
    data: PositionCreate,
    pf_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Adds a new stock position to one of the user's portfolios.
    
    Args:
        data (PositionCreate): The details of the position to add.
        pf_id (int): The ID of the portfolio to add the position to.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        Position: The newly created position object.
        
    Raises:
        HTTPException: 404 if the portfolio is not found for the current user.
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
    """Lists all positions within a specific portfolio.
    
    Args:
        pf_id (int): The ID of the portfolio.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        List[Position]: A list of positions in the portfolio.
        
    Raises:
        HTTPException: 404 if the portfolio is not found for the current user.
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
    """Computes and returns the current market value of a portfolio.
    
    Args:
        pf_id (int): The ID of the portfolio.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        dict: An object containing the portfolio ID and its calculated value.
        
    Raises:
        HTTPException: 404 if the portfolio is not found for the current user.
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
    """Generates brief, AI-powered insights about a portfolio.
    
    Args:
        pf_id (int): The ID of the portfolio.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        dict: An object containing the portfolio ID and the generated insight.
        
    Raises:
        HTTPException: 404 if the portfolio is not found for the current user.
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
    status_code=201,
    summary="Record a new buy/sell transaction"
)
def add_transaction(
    pf_id: int,
    tx_in: TransactionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Records a new transaction (buy or sell) for a specified portfolio.
    
    Args:
        pf_id (int): The ID of the portfolio for the transaction.
        tx_in (TransactionCreate): The details of the transaction.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        Transaction: The newly created transaction object.
        
    Raises:
        HTTPException: 404 if the portfolio is not found for the current user.
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
    """Lists transactions for a portfolio, with optional date filtering and pagination.
    
    Args:
        pf_id (int): The ID of the portfolio.
        skip (int): The number of transactions to skip for pagination.
        limit (int): The maximum number of transactions to return.
        start (Optional[date]): The start date for filtering transactions.
        end (Optional[date]): The end date for filtering transactions.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        List[Transaction]: A list of transaction objects.
        
    Raises:
        HTTPException: 404 if the portfolio is not found for the current user.
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
    """Computes the realized and unrealized Profit and Loss (PnL) for a portfolio.
    
    Args:
        pf_id (int): The ID of the portfolio.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        dict: An object with realized_pnl, unrealized_pnl, and other metrics.
        
    Raises:
        HTTPException: 404 if the portfolio is not found for the current user.
    """
    p = crud.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")
    return await compute_pnl(db, pf_id)

@router.get("/{pf_id}/change-24h")
async def get_portfolio_24h_change(
    pf_id: int = Path(..., gt=0, description="The ID of the portfolio to calculate 24h change for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Computes the portfolio's overall percentage change in the last 24 hours.
    
    Args:
        pf_id (int): The ID of the portfolio.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        dict: An object with the portfolio ID and its 24h percentage change.
        
    Raises:
        HTTPException: 404 if the portfolio is not found for the current user.
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
    """Updates the details of an existing transaction record.
    
    Args:
        pf_id (int): The ID of the portfolio containing the transaction.
        tx_id (int): The ID of the transaction to update.
        tx_in (TransactionUpdate): The new data for the transaction.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        Transaction: The updated transaction object.
        
    Raises:
        HTTPException: 404 if the portfolio or transaction is not found.
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
    status_code=204,
    summary="Delete a transaction record"
)
def delete_transaction(
    pf_id: int,
    tx_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Deletes a specific transaction record from a portfolio.
    
    Args:
        pf_id (int): The ID of the portfolio containing the transaction.
        tx_id (int): The ID of the transaction to delete.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Raises:
        HTTPException: 404 if the portfolio or transaction is not found.
    """
    p = crud_pf.get_portfolio(db, pf_id)
    if not p or p.user_id != current_user.id:
        raise HTTPException(404, "Portfolio not found")
    success = crud_tx.delete_transaction(db, tx_id)
    if not success:
        raise HTTPException(404, "Transaction not found")
    return

@router.get("/positions/search-by-symbol", response_model=List[Position])
def get_all_user_positions_by_symbol(
    symbol: str = Query(..., description="Stock symbol to search for (e.g., AAPL)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves all of a user's positions for a specific symbol across all their portfolios.
    
    Args:
        symbol (str): The stock symbol to search for.
        db (Session): The database session dependency.
        current_user: The authenticated user dependency.
        
    Returns:
        List[Position]: A list of all positions matching the symbol for the user.
    """
    positions = crud.get_all_positions_for_symbol_by_user(db=db, user_id=current_user.id, symbol=symbol)
    if not positions:
        pass
    return positions