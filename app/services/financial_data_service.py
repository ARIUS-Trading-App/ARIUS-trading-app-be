from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.fundamentaldata import FundamentalData
from alpha_vantage.cryptocurrencies import CryptoCurrencies
# add news from alphavantage as well
from app.core.config import settings
import app.services.web_search_service
import asyncio

class FinancialDataService:
    def __init__(self):
        if not settings.ALPHA_VANTAGE_API_KEY:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set in environment variables.")
        self.ts = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.fd = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.cc = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')

    async def _run_sync(self, func, *args, **kwargs):
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
        
    async def get_latest_news_for_stock(self, symbol: str, limit: int = 5):
        news_query = f"latest financial news for {symbol} stock" # update this prompt to be better
        news_context = await web_search_services.get_search_context(news_query, max_results = limit, include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com"])
        
        # also add news from alpha vantage
        
        return news_context if news_context else "No specific news found via web search."

    async def get_crypto_quote(self, symbol: str, market: str = "USD"):
        try:
            data,  _ = await self._run_async(self.cc.get_digital_currently_daily, symbol=symbol, market=market)
            
            if data and 'Time Series (Digital Currency Daily)' in data:
                latest_date = sorted(data['Time Series (Digital Currency Daily)'].keys(), reverse=True)[0]
                return data['Time Series (Digital Currency Daily)'][latest_date]
            return None
        except Exception as e:
            print(f"Error fetching crypto quote for {symbol}: {e}")
            return None
        
financial_data_service = FinancialDataService()
