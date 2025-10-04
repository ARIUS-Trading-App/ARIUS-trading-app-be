from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class PositionCreate(BaseModel):
    """Schema for creating a new position within a portfolio."""
    symbol: str = Field(..., example="AAPL")
    quantity: float = Field(..., gt=0)
    avg_price: float = Field(..., gt=0)

class Position(PositionCreate):
    """Schema for a position retrieved from the database."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PortfolioCreate(BaseModel):
    """Schema for creating a new portfolio."""
    name: str = Field(..., example="Retirement Fund")

class Portfolio(BaseModel):
    """Schema for a portfolio retrieved from the database, including its positions."""
    id: int
    name: str
    created_at: datetime
    positions: List[Position] = []

    class Config:
        from_attributes = True

class PriceChange24hResponse(BaseModel):
    """Defines the response structure for a 24-hour price change request."""
    symbol: str
    current_price: float
    price_24h_ago: float
    change_amount: float
    change_percent: float
    latest_price_timestamp: str
    reference_price_24h_ago_timestamp: str