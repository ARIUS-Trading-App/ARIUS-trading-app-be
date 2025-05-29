from sqlalchemy.orm import Session
from typing import List
from app.models.portfolio import Portfolio, Position
from app.schemas.portfolio import PortfolioCreate, PositionCreate

def create_portfolio(db: Session, user_id: int, data: PortfolioCreate) -> Portfolio:
    """Create a new portfolio for a user."""
    p = Portfolio(user_id=user_id, name=data.name)
    db.add(p); db.commit(); db.refresh(p)
    return p

def get_portfolios(db: Session, user_id: int) -> List[Portfolio]:
    """Retrieve all portfolios for a user."""
    return db.query(Portfolio).filter(Portfolio.user_id==user_id).all()

def get_portfolio(db: Session, portfolio_id: int) -> Portfolio:
    """Retrieve a portfolio by its ID."""
    return db.query(Portfolio).filter(Portfolio.id==portfolio_id).first()

def create_position(db: Session, portfolio_id: int, data: PositionCreate) -> Position:
    """Create a new position in a portfolio."""
    pos = Position(portfolio_id=portfolio_id, **data.dict())
    db.add(pos); db.commit(); db.refresh(pos)
    return pos

def get_positions(db: Session, portfolio_id: int) -> List[Position]:
    """Retrieve all positions in a portfolio."""
    return db.query(Position).filter(Position.portfolio_id==portfolio_id).all()

def get_all_positions_for_symbol_by_user(db: Session, user_id: int, symbol: str) -> List[Position]:
    """
    Retrieve all positions for a specific symbol across all portfolios of a given user.

    Args:
        db: The SQLAlchemy database session.
        user_id: The ID of the user.
        symbol: The stock symbol to search for (e.g., "AAPL").

    Returns:
        A list of Position objects matching the criteria.
    """
    # Query the Position table
    # Join with the Portfolio table to access Portfolio.user_id
    # Filter by Portfolio.user_id matching the provided user_id
    # Filter by Position.symbol matching the provided symbol
    # Retrieve all matching Position objects
    return (
        db.query(Position)
        .join(Portfolio, Position.portfolio_id == Portfolio.id) # Explicit join condition
        .filter(Portfolio.user_id == user_id)
        .filter(Position.symbol == symbol)
        .all()
    )