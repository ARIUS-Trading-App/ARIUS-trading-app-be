from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class PositionCreate(BaseModel):
    symbol: str = Field(..., example="AAPL")
    quantity: float = Field(..., gt=0)
    avg_price: float = Field(..., gt=0)

class Position(PositionCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PortfolioCreate(BaseModel):
    name: str = Field(..., example="Retirement Fund")

class Portfolio(BaseModel):
    id: int
    name: str
    created_at: datetime
    positions: List[Position] = []

    class Config:
        from_attributes = True

class PriceChange24hResponse(BaseModel):
    symbol: str
    current_price: float
    price_24h_ago: float
    change_amount: float
    change_percent: float
    latest_price_timestamp: str
    reference_price_24h_ago_timestamp: str
