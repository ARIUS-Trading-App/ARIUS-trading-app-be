from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Enum, ForeignKey
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

    id           = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    symbol       = Column(String(20), nullable=False)
    type         = Column(Enum(TransactionType), nullable=False)
    quantity     = Column(Float, nullable=False)
    price        = Column(Float, nullable=False)
    timestamp    = Column(DateTime(timezone=False), server_default=func.now())

    portfolio    = relationship("Portfolio", back_populates="transactions")
