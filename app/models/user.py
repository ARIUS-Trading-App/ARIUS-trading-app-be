from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Enum as SAEnum
from sqlalchemy.sql import func
from app.db.session import Base
import enum
from sqlalchemy.orm import relationship

class TradingExperienceLevel(str, enum.Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced" 
    PROFESSIONAL = "Professional"

class RiskAppetite(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    VERY_HIGH = "Very High"
    
class InvestmentGoals(str, enum.Enum):
    Short_term_Gains = "Short-term Gains"
    Long_term_Growth= "Long-term Growth"
    Income_Generation = "Income Generation"
    Capital_Preservation = "Capital Preservation" 
    Speculation = "Speculation"


class User(Base):
    """Represents a user of the application.

    This model stores core user information, profile details, and preferences
    that can be used to personalize the application experience.

    Attributes:
        id (int): Primary key for the user.
        username (str): The user's unique username.
        email (str): The user's unique email address.
        full_name (str): The user's full name.
        profile_picture_url (str): URL to the user's profile picture.
        is_active (bool): Flag indicating if the user's account is active.
        trading_experience (TradingExperienceLevel): The user's self-assessed trading experience.
        risk_appetite (RiskAppetite): The user's tolerance for investment risk.
        investment_goals (InvestmentGoals): The user's primary financial goals.
        preferred_asset_classes (JSON): A list of asset classes the user is interested in.
        interests_for_feed (JSON): A list of topics or symbols for personalizing the feed.
        date_of_birth (datetime): The user's date of birth.
        country_of_residence (str): The user's country.
        timezone (str): The user's preferred timezone.
        portfolios (relationship): Relationship to the user's investment portfolios.
        feed_items (relationship): Relationship to the user's aggregated feed items.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    profile_picture_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    trading_experience = Column(SAEnum(TradingExperienceLevel), nullable=True)
    risk_appetite = Column(SAEnum(RiskAppetite), nullable=True)
    investment_goals = Column(SAEnum(InvestmentGoals), nullable=True)
    preferred_asset_classes = Column(JSON, nullable=True)
    interests_for_feed = Column(JSON, nullable=True)
    date_of_birth = Column(DateTime(timezone=False), nullable=True)
    country_of_residence = Column(String(100), nullable=True)
    timezone = Column(String(50), default="UTC", nullable=False)

    portfolios = relationship("Portfolio", back_populates="user")

    feed_items = relationship("FeedItem", back_populates="user", cascade="all, delete-orphan")


    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"