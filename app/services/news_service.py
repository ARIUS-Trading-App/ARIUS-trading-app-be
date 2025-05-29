# app/services/news_service.py
from newsapi import NewsApiClient
from datetime import datetime, timedelta
from typing import List
from app.core.config import settings

_newsapi = NewsApiClient(api_key=settings.NEWSAPI_KEY)

async def fetch_stock_news(symbol: str, days: int = 1) -> List[str]:
    to = datetime.utcnow()
    frm = to - timedelta(days=days)
    resp = _newsapi.get_everything(
        q=f"{symbol} stock OR {symbol} market",
        from_param=frm.isoformat(),
        to=to.isoformat(),
        language="en",
        sort_by="publishedAt",
        page_size=20,
    )
    return [
        f"{a['title']}. {a.get('description','')}"
        for a in resp.get("articles", [])
    ]
