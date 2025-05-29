# app/services/sentiment_service.py

import os
import nltk
from nltk.data import find
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from typing import List, Tuple

from app.services.news_service import fetch_stock_news     # async def fetch_stock_news(symbol: str, days: int = 1) -> List[str]
from app.services.tweet_service import fetch_stock_tweets  # async def fetch_stock_tweets(symbol: str, limit: int = 20) -> List[str]

# ——— NLTK / VADER setup ————————————————————————————————
ROOT = os.path.dirname(os.path.dirname(__file__))
NLTK_DATA_PATH = os.path.abspath(os.path.join(ROOT, "..", "data", "nltk_data"))
os.environ.setdefault("NLTK_DATA", NLTK_DATA_PATH)
os.makedirs(NLTK_DATA_PATH, exist_ok=True)

try:
    find("sentiment/vader_lexicon.zip")
except LookupError:
    nltk.download("vader_lexicon", download_dir=NLTK_DATA_PATH)

_analyzer = SentimentIntensityAnalyzer()
# —————————————————————————————————————————————————————————————

async def compute_sentiment_score(symbol: str) -> float:
    """
    Returns the average VADER 'compound' score ∈ [–1..1]
    from the last 1 day of news + the latest tweets.
    """
    # fetch 1 day of news
    news: List[str] = await fetch_stock_news(symbol, days=1)

    # fetch up to 20 tweets
    tweets: List[str] = await fetch_stock_tweets(symbol, limit=20)

    texts = news + tweets
    if not texts:
        return 0.0

    # score each snippet
    scores = [_analyzer.polarity_scores(text)["compound"] for text in texts if text]
    return sum(scores) / len(scores)


def classify_score(score: float) -> Tuple[str, str]:
    """
    Map a float score into:
      - action: 'buy' / 'hold' / 'sell'
      - mood:   'greed' / 'neutral' / 'fear'
    """
    if score >= 0.05:
        return "buy", "greed"
    elif score <= -0.05:
        return "sell", "fear"
    else:
        return "hold", "neutral"
