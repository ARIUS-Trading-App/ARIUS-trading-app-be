from pydantic import BaseModel
from datetime import datetime

class ForecastPoint(BaseModel):
    """Represents a single data point in a time-series forecast."""
    ds: datetime        
    yhat: float         
    
    class Config:
        from_attributes = True