from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.fundamentaldata import FundamentalData
from alpha_vantage.cryptocurrencies import CryptoCurrencies
# add news from alphavantage as well
from app.core.config import settings
import web_search_services
import asyncio

class FinancialDataService:
    def __init__(self):
        if not settings.ALPHA_VANTAGE_API_KEY:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set in environment variables.")
        self.ts = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.fd = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.cc = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')

    async def _run_sync(self, func, *args, *kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    async def get_stock_quote(self, symbol: str):
        try:
            data, _ = await self._run_sync(self.ts.get_quote_endpoint, symbol=symbol)
            return data
        except Exception as e:
            print(f"Error fetching company overview for {symbol}: {e}")
            return None
        
    async def get_company_overview(self, symbol: str):
        try:
            data, _ = await self._run_async(self.fd.get_company_overview, symbol=symbol)
            return data
        except Exception as e:
            print(f"Error fetching company overview for {symbol}: {e}")
            return None
        
    async def get_latest_new_for_stock(self, symbol: str, limit: int = 5):
        news_query = f"latest financial news for {symbol} stock" # update this to be better
        news_context = await web_search_services.get_search_context(news_query, max_results = limit, ["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com"])
        return news_context if news_context else "No specific news found via web search."

