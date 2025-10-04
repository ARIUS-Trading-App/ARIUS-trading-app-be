from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.schemas.feed import FeedItem, FeedItemCreate, FeedFilters
from app.crud.feed import (
    list_feed_items, create_feed_item
)
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.services.feed_service import FeedFetcher
import asyncio

router = APIRouter(prefix="/feeds", tags=["Feed"])

@router.post(
    "/",
    response_model=FeedItem,
    status_code=status.HTTP_201_CREATED,
    summary="Manually add a feed item"
)
def add_feed_item(
    dto: FeedItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Manually create and store a new item in the user's feed."""
    return create_feed_item(db, current_user.id, dto)

@router.get(
    "/",
    response_model=List[FeedItem],
    summary="List feed items with filters & pagination"
)
def get_feed(
    filters: FeedFilters = Depends(),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Retrieves a list of feed items for the current user, with optional filtering."""
    return list_feed_items(db, current_user.id, filters)

@router.post(
    "/refresh",
    summary="Refresh feed from external sources"
)
async def refresh_feed(
    keyword: str = Query(..., example="Tesla OR Apple"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Triggers a background refresh of the user's feed based on a keyword."""
    fetcher = FeedFetcher(db, current_user.id)
    await asyncio.gather(
        fetcher.fetch_news(keyword),
        fetcher.fetch_tweets(keyword)
    )
    return {"msg": "Feed refreshed for keyword", "keyword": keyword}