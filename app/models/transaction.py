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
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    type = Column(SAEnum(TransactionType), nullable=False) # Use SAEnum for consistency
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=False), server_default=func.now())

    # Relationship
    portfolio = relationship("Portfolio", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(id={self.id}, type='{self.type}', symbol='{self.symbol}', portfolio_id={self.portfolio_id})>"