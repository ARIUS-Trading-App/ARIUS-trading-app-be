# app/schemas/transaction.py

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
from app.models.transaction import TransactionType
import re

class TransactionBase(BaseModel):
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
    pass

class TransactionUpdate(BaseModel):
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
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True
