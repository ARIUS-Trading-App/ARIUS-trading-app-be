from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db.session import Base
from sqlalchemy.sql import func

class Portfolio(Base):
    """Represents a user's investment portfolio.

    A portfolio is a container for a collection of financial positions and
    their associated transaction history. Each portfolio is owned by a single user.

    Attributes:
        id (int): Primary key for the portfolio.
        user_id (int): Foreign key linking to the owner user.
        name (str): The user-defined name for the portfolio (e.g., "Retirement Fund").
        created_at (datetime): Timestamp of when the portfolio was created.
        user (relationship): SQLAlchemy relationship to the parent User object.
        positions (relationship): Relationship to the collection of Position objects in this portfolio.
        transactions (relationship): Relationship to the transaction history of this portfolio.
    """
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now())

    user = relationship("User", back_populates="portfolios")
    positions = relationship("Position", back_populates="portfolio", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="portfolio", cascade="all, delete-orphan")
    def __repr__(self):
        return f"<Portfolio(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class Position(Base):
    """Represents a single asset holding within a portfolio.

    This model tracks the quantity and average cost of a specific stock
    or asset held in a portfolio.

    Attributes:
        id (int): Primary key for the position.
        portfolio_id (int): Foreign key linking to the parent portfolio.
        symbol (str): The stock ticker or asset symbol (e.g., "AAPL").
        quantity (float): The number of shares/units held.
        avg_price (float): The average price paid for the shares/units held.
        created_at (datetime): Timestamp of when the position was first created.
        portfolio (relationship): SQLAlchemy relationship to the parent Portfolio object.
    """
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now())

    portfolio = relationship("Portfolio", back_populates="positions")

    def __repr__(self):
        return f"<Position(id={self.id}, symbol='{self.symbol}', portfolio_id={self.portfolio_id})>"