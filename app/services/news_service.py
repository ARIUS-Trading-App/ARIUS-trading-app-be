from newsapi import NewsApiClient
from datetime import datetime, timedelta
from typing import List
from app.core.config import settings

_newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY)

async def fetch_stock_news(symbol: str, days: int = 1) -> List[str]:
    """Fetches recent news headlines and descriptions for a given stock symbol.

    Args:
        symbol (str): The stock symbol (e.g., "AAPL").
        days (int): The number of past days to fetch news for.

    Returns:
        List[str]: A list of strings, where each string combines a news
                   article's title and description.
    """
    now = datetime.utcnow().replace(microsecond=0)
    frm = now - timedelta(days=days)

    from_param = frm.isoformat(timespec="seconds")
    to_param   = now.isoformat(timespec="seconds")

    resp = _newsapi.get_everything(
        q=f"{symbol} stock OR {symbol} market",
        from_param=from_param,
        to=to_param,
        language="en",
        sort_by="publishedAt",
        page_size=20,
    )

    return [
        f"{a['title']}. {a.get('description','')}"
        for a in resp.get("articles", [])
    ]