from typing import List
from app.services.web_search_service import web_search_service

async def fetch_stock_tweets(symbol: str, limit: int = 20) -> List[str]:
    """Fetches recent tweets for a given stock symbol.

    Uses the web search service to search Twitter, filtering out retweets.

    Args:
        symbol (str): The stock symbol (e.g., "$AAPL" or "Apple").
        limit (int): The maximum number of tweets to return.

    Returns:
        List[str]: A list of strings, where each string is the content of a tweet.
    """
    query = f"{symbol} -filter:retweets site:twitter.com"

    results = await web_search_service.search(
        query=query,
        max_results=limit,
        include_domains=["twitter.com"],
    )

    return [item.get("content", "") for item in results]