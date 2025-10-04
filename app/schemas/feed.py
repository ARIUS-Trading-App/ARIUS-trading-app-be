from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.models.feed import FeedType

class FeedItemBase(BaseModel):
    """Base schema for a feed item, containing core fields."""
    type: FeedType
    source: str
    original_id: str
    content: str
    feed_metadata: dict = {}

class FeedItemCreate(FeedItemBase):
    """Schema used for creating a new feed item in the database."""
    pass

class FeedItem(FeedItemBase):
    """Schema for a feed item retrieved from the database, including generated fields."""
    id: int
    fetched_at: datetime
    summary: Optional[str]

    class Config:
        from_attributes = True

class FeedFilters(BaseModel):
    """Defines available query parameters for filtering the user's feed."""
    types: Optional[List[FeedType]] = None
    sources: Optional[List[str]] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    limit: int = Field(50, gt=0, le=200)
    skip: int = Field(0, ge=0)