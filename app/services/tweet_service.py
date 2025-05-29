# app/services/tweet_service.py
from typing import List
from app.services.web_search_service import web_search_service

async def fetch_stock_tweets(symbol: str, limit: int = 20) -> List[str]:
    query = f"{symbol} -filter:retweets site:twitter.com"
    hits = await web_search_service.get_search_context(
        query,
        max_results=limit,
        allowed_domains=["twitter.com"]
    )
    return [h.snippet for h in hits]
