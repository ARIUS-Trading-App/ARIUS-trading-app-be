import os
import nltk
from nltk.data import find
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from typing import List, Tuple

from app.services.news_service import fetch_stock_news
from app.services.tweet_service import fetch_stock_tweets

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NLTK_DATA_PATH_CUSTOM = os.path.join(PROJECT_ROOT, "data", "nltk_data")

os.makedirs(NLTK_DATA_PATH_CUSTOM, exist_ok=True)

if NLTK_DATA_PATH_CUSTOM not in nltk.data.path:
    nltk.data.path.append(NLTK_DATA_PATH_CUSTOM)

print(f"[INFO] Custom NLTK data path configured: {NLTK_DATA_PATH_CUSTOM}")
print(f"[INFO] NLTK will search for data in: {nltk.data.path}")

try:
    find("sentiment/vader_lexicon.zip")
    print("[INFO] NLTK: vader_lexicon.zip found in search paths.")
except LookupError:
    print("[WARNING] NLTK: vader_lexicon.zip not found. Attempting download...")
    try:
        nltk.download("vader_lexicon", download_dir=NLTK_DATA_PATH_CUSTOM)
        print(f"[INFO] NLTK: vader_lexicon downloaded to {NLTK_DATA_PATH_CUSTOM}.")
        find("sentiment/vader_lexicon.zip")
        print("[INFO] NLTK: vader_lexicon.zip now found after download.")
    except Exception as download_e:
        print(f"[ERROR] NLTK: Failed to download vader_lexicon: {download_e}")
        print("[ERROR] Please ensure you have internet connectivity and the NLTK_DATA_PATH_CUSTOM is writable.")
        raise

_analyzer = None
try:
    _analyzer = SentimentIntensityAnalyzer()
    print("[INFO] SentimentIntensityAnalyzer initialized successfully.")
except Exception as e:
    print(f"[ERROR] Critical error initializing SentimentIntensityAnalyzer: {e}")
    print(f"[ERROR] This usually means 'vader_lexicon' is still not accessible.")
    print(f"[ERROR] NLTK search paths being used: {nltk.data.path}")
    print(f"[ERROR] Expected location for vader_lexicon.zip within one of these paths: sentiment/vader_lexicon.zip")
    raise

async def compute_sentiment_score(symbol: str) -> float:
    """Computes an aggregate sentiment score for a stock symbol.

    This function fetches recent news and tweets related to the symbol,
    calculates the VADER 'compound' sentiment score for each piece of text,
    and returns the average score.

    Args:
        symbol (str): The stock symbol.

    Returns:
        float: The average compound sentiment score, ranging from -1 (very negative)
               to 1 (very positive). Returns 0.0 if no text is found.
    """
    if _analyzer is None:
        print("[ERROR] Sentiment analyzer not initialized. Returning neutral score.")
        return 0.0

    news: List[str] = await fetch_stock_news(symbol, days=1)
    tweets: List[str] = await fetch_stock_tweets(symbol, limit=20)

    texts = news + tweets
    if not texts:
        return 0.0

    scores = [_analyzer.polarity_scores(text)["compound"] for text in texts if text and isinstance(text, str)]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def classify_score(score: float) -> Tuple[str, str]:
    """Classifies a sentiment score into human-readable labels.

    Args:
        score (float): A sentiment score, typically from -1 to 1.

    Returns:
        Tuple[str, str]: A tuple containing an action ('buy'/'hold'/'sell')
                         and a mood ('greed'/'neutral'/'fear').
    """
    if score >= 0.05:
        return "buy", "greed"
    elif score <= -0.05:
        return "sell", "fear"
    else:
        return "hold", "neutral"