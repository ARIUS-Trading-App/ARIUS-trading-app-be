# app/services/tweet_service.py

from typing import List
from app.services.web_search_service import web_search_service

async def fetch_stock_tweets(symbol: str, limit: int = 20) -> List[str]:
    """
    Fetch up to `limit` recent tweets mentioning `symbol` (excluding retweets).
    Uses the raw `search()` call so we get back List[Dict], then extract each
    result's `content` field.
    """
    query = f"{symbol} -filter:retweets site:twitter.com"

    # Call the lower-level search() which returns a List[Dict]
    results = await web_search_service.search(
        query=query,
        max_results=limit,
        include_domains=["twitter.com"],  # optional, but explicit
    )

    # Pull out the snippet/text for each result
    return [item.get("content", "") for item in results]
