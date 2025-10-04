from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
from app.models.transaction import TransactionType
import re

class TransactionBase(BaseModel):
    """Base schema for a transaction, containing core fields and validation."""
    symbol: str = Field(..., example="AAPL")
    type: TransactionType
    quantity: float = Field(..., gt=0, example=10)
    price: float = Field(..., gt=0, example=150.5)

    @validator("symbol")
    def symbol_format(cls, v):
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError("Invalid ticker format")
        return v

class TransactionCreate(TransactionBase):
    """Schema used for logging a new transaction."""
    pass

class TransactionUpdate(BaseModel):
    """Schema for updating an existing transaction, with all fields optional."""
    symbol: Optional[str] = Field(None, example="AAPL")
    type: Optional[TransactionType]
    quantity: Optional[float] = Field(None, gt=0)
    price: Optional[float] = Field(None, gt=0)

    @validator("symbol")
    def symbol_format(cls, v):
        if v and not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError("Invalid ticker format")
        return v

class Transaction(TransactionBase):
    """Schema for a transaction retrieved from the database."""
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True