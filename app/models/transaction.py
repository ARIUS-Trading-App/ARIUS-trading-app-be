from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Enum, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import enum

class TransactionType(str, enum.Enum):
    BUY  = "buy"
    SELL = "sell"

class Transaction(Base):
    """Represents a single financial transaction (buy or sell) within a portfolio.

    This table provides the history of all trades, which is used to calculate
    realized P&L and track portfolio changes over time.

    Attributes:
        id (int): Primary key for the transaction.
        portfolio_id (int): Foreign key linking to the parent portfolio.
        symbol (str): The stock ticker or asset symbol (e.g., "AAPL").
        type (TransactionType): The type of transaction ('buy' or 'sell').
        quantity (float): The number of shares/units transacted.
        price (float): The price per share/unit at the time of the transaction.
        timestamp (datetime): The date and time the transaction occurred.
        portfolio (relationship): SQLAlchemy relationship to the parent Portfolio object.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    type = Column(SAEnum(TransactionType), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=False), server_default=func.now())

    portfolio = relationship("Portfolio", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(id={self.id}, type='{self.type}', symbol='{self.symbol}', portfolio_id={self.portfolio_id})>"