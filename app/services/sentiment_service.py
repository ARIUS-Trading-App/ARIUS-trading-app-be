# app/services/sentiment_service.py

import os
import nltk
from nltk.data import find
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from typing import List, Tuple

from app.services.news_service import fetch_stock_news
from app.services.tweet_service import fetch_stock_tweets

# ——— NLTK / VADER setup ————————————————————————————————
# Calculate the desired NLTK data path relative to this file's location.
# Assuming this file (sentiment_service.py) is in app/services/
# We want data/nltk_data at the project root level.
# So, __file__ -> app/services/sentiment_service.py
# os.path.dirname(__file__) -> app/services
# os.path.dirname(os.path.dirname(__file__)) -> app
# os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) -> project_root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NLTK_DATA_PATH_CUSTOM = os.path.join(PROJECT_ROOT, "data", "nltk_data")

# Ensure the custom directory exists
os.makedirs(NLTK_DATA_PATH_CUSTOM, exist_ok=True)

# Add the custom path to NLTK's list of search paths
# This is more reliable than relying on environment variables alone,
# as it directly modifies NLTK's runtime configuration.
if NLTK_DATA_PATH_CUSTOM not in nltk.data.path:
    nltk.data.path.append(NLTK_DATA_PATH_CUSTOM)

# For debugging, print the paths NLTK will search
print(f"[INFO] Custom NLTK data path configured: {NLTK_DATA_PATH_CUSTOM}")
print(f"[INFO] NLTK will search for data in: {nltk.data.path}")

try:
    # Check if vader_lexicon can be found using the standard NLTK mechanism
    # The resource name for vader_lexicon.zip/vader_lexicon/vader_lexicon.txt
    # is typically 'sentiment/vader_lexicon.zip' (NLTK handles unzipping internally)
    find("sentiment/vader_lexicon.zip")
    print("[INFO] NLTK: vader_lexicon.zip found in search paths.")
except LookupError:
    print("[WARNING] NLTK: vader_lexicon.zip not found. Attempting download...")
    try:
        nltk.download("vader_lexicon", download_dir=NLTK_DATA_PATH_CUSTOM)
        print(f"[INFO] NLTK: vader_lexicon downloaded to {NLTK_DATA_PATH_CUSTOM}.")
        # After download, re-check if it can be found
        find("sentiment/vader_lexicon.zip")
        print("[INFO] NLTK: vader_lexicon.zip now found after download.")
    except Exception as download_e:
        print(f"[ERROR] NLTK: Failed to download vader_lexicon: {download_e}")
        print("[ERROR] Please ensure you have internet connectivity and the NLTK_DATA_PATH_CUSTOM is writable.")
        raise  # Re-raise the exception to stop app startup if critical resource fails

_analyzer = None
try:
    _analyzer = SentimentIntensityAnalyzer()
    print("[INFO] SentimentIntensityAnalyzer initialized successfully.")
except Exception as e:
    print(f"[ERROR] Critical error initializing SentimentIntensityAnalyzer: {e}")
    print(f"[ERROR] This usually means 'vader_lexicon' is still not accessible.")
    print(f"[ERROR] NLTK search paths being used: {nltk.data.path}")
    print(f"[ERROR] Expected location for vader_lexicon.zip within one of these paths: sentiment/vader_lexicon.zip")
    raise # Stop the application if the analyzer can't be initialized.
# —————————————————————————————————————————————————————————————

async def compute_sentiment_score(symbol: str) -> float:
    """
    Returns the average VADER 'compound' score ∈ [–1..1]
    from the last 1 day of news + the latest tweets.
    """
    if _analyzer is None:
        print("[ERROR] Sentiment analyzer not initialized. Returning neutral score.")
        return 0.0

    # fetch 1 day of news
    news: List[str] = await fetch_stock_news(symbol, days=1)

    # fetch up to 20 tweets
    tweets: List[str] = await fetch_stock_tweets(symbol, limit=20)

    texts = news + tweets
    if not texts:
        return 0.0

    # score each snippet
    scores = [_analyzer.polarity_scores(text)["compound"] for text in texts if text and isinstance(text, str)]
    if not scores: # Handle case where all texts were empty, None, or not strings
        return 0.0
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