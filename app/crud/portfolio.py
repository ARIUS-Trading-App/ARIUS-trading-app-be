from sqlalchemy.orm import Session
from typing import List
from app.models.portfolio import Portfolio, Position
from app.schemas.portfolio import PortfolioCreate, PositionCreate

def create_portfolio(db: Session, user_id: int, data: PortfolioCreate) -> Portfolio:
    """Creates a new portfolio for a user in the database.

    Args:
        db (Session): The SQLAlchemy database session.
        user_id (int): The ID of the user who owns the portfolio.
        data (PortfolioCreate): The data for the new portfolio (e.g., name).

    Returns:
        Portfolio: The newly created Portfolio object.
    """
    p = Portfolio(user_id=user_id, name=data.name)
    db.add(p); db.commit(); db.refresh(p)
    return p

def get_portfolios(db: Session, user_id: int) -> List[Portfolio]:
    """Retrieves all portfolios belonging to a specific user.

    Args:
        db (Session): The SQLAlchemy database session.
        user_id (int): The ID of the user.

    Returns:
        List[Portfolio]: A list of the user's Portfolio objects.
    """
    return db.query(Portfolio).filter(Portfolio.user_id==user_id).all()

def get_portfolio(db: Session, portfolio_id: int) -> Portfolio:
    """Retrieves a single portfolio by its unique ID.

    Args:
        db (Session): The SQLAlchemy database session.
        portfolio_id (int): The ID of the portfolio to retrieve.

    Returns:
        Portfolio: The Portfolio object if found, otherwise None.
    """
    return db.query(Portfolio).filter(Portfolio.id==portfolio_id).first()

def create_position(db: Session, portfolio_id: int, data: PositionCreate) -> Position:
    """Creates a new asset position within a specific portfolio.

    Args:
        db (Session): The SQLAlchemy database session.
        portfolio_id (int): The ID of the portfolio to add the position to.
        data (PositionCreate): The data for the new position (symbol, quantity, etc.).

    Returns:
        Position: The newly created Position object.
    """
    pos = Position(portfolio_id=portfolio_id, **data.dict())
    db.add(pos); db.commit(); db.refresh(pos)
    return pos

def get_positions(db: Session, portfolio_id: int) -> List[Position]:
    """Retrieves all positions held within a specific portfolio.

    Args:
        db (Session): The SQLAlchemy database session.
        portfolio_id (int): The ID of the portfolio.

    Returns:
        List[Position]: A list of Position objects in the portfolio.
    """
    return db.query(Position).filter(Position.portfolio_id==portfolio_id).all()

def get_all_positions_for_symbol_by_user(db: Session, user_id: int, symbol: str) -> List[Position]:
    """Retrieves all positions for a symbol across all of a user's portfolios.

    Args:
        db (Session): The SQLAlchemy database session.
        user_id (int): The ID of the user.
        symbol (str): The stock symbol to search for.

    Returns:
        List[Position]: A list of matching Position objects.
    """
    return (
        db.query(Position)
        .join(Portfolio, Position.portfolio_id == Portfolio.id)
        .filter(Portfolio.user_id == user_id)
        .filter(Position.symbol == symbol)
        .all()
    )