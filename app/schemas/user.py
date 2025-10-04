from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from app.models.user import TradingExperienceLevel, RiskAppetite, InvestmentGoals

class UserBase(BaseModel):
    """Base user schema with fields common to all user-related operations."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    profile_picture_url: Optional[str] = None
    is_active: Optional[bool] = True
    trading_experience: Optional[TradingExperienceLevel] = None
    risk_appetite: Optional[RiskAppetite] = None
    investment_goals: Optional[InvestmentGoals] = None
    preferred_asset_classes: Optional[List[str]] = []
    interests_for_feed: Optional[List[str]] = []
    date_of_birth: Optional[datetime] = None
    country_of_residence: Optional[str] = None
    timezone: Optional[str] = "UTC"
    
class UserCreate(UserBase):
    """Schema for creating a new user. Inherits base fields and makes some required."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    
class UserUpdate(UserBase):
    """Schema for updating a user's profile. All fields are optional."""
    pass
    
class UserInDBBase(UserBase):
    """Base schema for a user object as it exists in the database."""
    id: int
    class ConfigDict:
        from_attributes = True
        
class User(UserInDBBase):
    """Schema for a user object as returned by the API (public-facing)."""
    pass

class UserInDB(UserInDBBase):
    """Schema for a user object including sensitive data stored in the DB."""
    hashed_password: str