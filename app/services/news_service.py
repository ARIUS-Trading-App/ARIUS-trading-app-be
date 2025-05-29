# app/services/news_service.py

from newsapi import NewsApiClient
from datetime import datetime, timedelta
from typing import List
from app.core.config import settings

_newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY)

async def fetch_stock_news(symbol: str, days: int = 1) -> List[str]:
    """
    Fetch headlines & descriptions for the past `days` days, 
    with from/to timestamps in YYYY-MM-DDTHH:MM:SS format.
    """
    # 1) get now & back up `days`, then strip microseconds
    now = datetime.utcnow().replace(microsecond=0)
    frm = now - timedelta(days=days)

    # 2) create ISO strings with seconds only
    from_param = frm.isoformat(timespec="seconds")  # e.g. "2025-05-28T14:23:01"
    to_param   = now.isoformat(timespec="seconds")  # e.g. "2025-05-29T14:23:01"

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
