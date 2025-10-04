from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Enum, ForeignKey
from sqlalchemy.orm   import relationship, synonym
from sqlalchemy.sql   import func
from app.db.session   import Base
import enum

class FeedType(str, enum.Enum):
    NEWS     = "news"
    ANNOUNCE = "announce"
    TWEET    = "tweet"

class FeedItem(Base):
    """Represents a single item in a user's personalized feed.

    This table stores various types of content, like news articles or tweets,
    that are fetched and aggregated for a user. Each item is linked to a user
    and has its content, source, and a generated summary.

    Attributes:
        id (int): Primary key for the feed item.
        user_id (int): Foreign key linking to the user this item belongs to.
        type (FeedType): The type of the feed item (e.g., 'news', 'tweet').
        source (str): The origin of the content (e.g., 'reuters.com').
        original_id (str): The unique identifier from the source (e.g., URL).
        content (str): The raw text content of the item.
        feed_metadata (dict): A JSON field for storing additional source-specific metadata.
        fetched_at (datetime): Timestamp of when the item was added to the database.
        summary (str): An LLM-generated summary of the content.
        user (relationship): SQLAlchemy relationship to the parent User object.
    """
    __tablename__ = "feed_items"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    type        = Column(Enum(FeedType), nullable=False)
    source      = Column(String(100), nullable=False)
    original_id = Column(String(200), nullable=False)
    content     = Column(Text, nullable=False)

    feed_metadata    = Column(JSON, default={})

    fetched_at  = Column(DateTime(timezone=False), server_default=func.now())
    summary     = Column(Text, nullable=True)

    user        = relationship("User", back_populates="feed_items")