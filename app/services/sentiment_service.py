# app/services/sentiment_service.py
from typing import List, Tuple
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from app.services.news_service import fetch_stock_news
from app.services.tweet_service import fetch_stock_tweets

# one global analyzer
_analyzer = SentimentIntensityAnalyzer()

async def compute_sentiment_score(symbol: str) -> float:
    """
    Returns the average VADER 'compound' score ∈ [–1..1] 
    from the last day of news + tweets.
    """
    news, tweets = await fetch_stock_news(symbol), await fetch_stock_tweets(symbol)
    texts = news + tweets
    if not texts:
        return 0.0
    scores = [_analyzer.polarity_scores(t)["compound"] for t in texts]
    return sum(scores) / len(scores)

def classify_score(score: float) -> Tuple[str,str]:
    """
    Map a float score into:
    - 'buy' vs 'sell' vs 'neutral'
    - 'greed' vs 'fear' vs 'neutral'
    using classic VADER thresholds.
    """
    if score >= 0.05:
        return "buy", "greed"
    elif score <= -0.05:
        return "sell", "fear"
    else:
        return "hold", "neutral"
