# app/services/financial_data_service.py
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.fundamentaldata import FundamentalData # Corrected
from alpha_vantage.cryptocurrencies import CryptoCurrencies # Corrected
from app.core.config import settings
from app.services.web_search_service import web_search_service # Import for news
import asyncio

class FinancialDataService:
    def __init__(self):
        if not settings.ALPHA_VANTAGE_API_KEY:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set in environment variables.")
        self.ts = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.fd = FundamentalData(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json') # Corrected
        self.cc = CryptoCurrencies(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json') # Corrected

    async def _run_sync(self, func, *args, **kwargs): # Renamed from _run_async for clarity
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    async def get_stock_quote(self, symbol: str):
        try:
            data, _ = await self._run_sync(self.ts.get_quote_endpoint, symbol=symbol)
            return data
        except Exception as e:
            print(f"Error fetching stock quote for {symbol}: {e}") # Corrected message
            return None
        
    async def get_company_overview(self, symbol: str):
        try:
            # FundamentalData's method is get_company_overview
            data, _ = await self._run_sync(self.fd.get_company_overview, symbol=symbol) # Corrected from self.fd to self.fd
            return data
        except Exception as e:
            print(f"Error fetching company overview for {symbol}: {e}")
            return None
        
    async def get_latest_news_for_stock(self, symbol: str, limit: int = 5):
        news_query = f"latest financial news for {symbol} stock"
        # Corrected: web_search_service instead of web_search_services
        news_context = await web_search_service.get_search_context(
            news_query, max_results=limit, 
            include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", "finance.yahoo.com"]
        )
        # Alpha Vantage News & Sentiment endpoint could be added here if desired
        # For example:
        # try:
        #     av_news_data, _ = await self._run_sync(self.ts.get_news_sentiment, tickers=symbol, limit=limit) # Check AV docs for actual function
        #     # Process av_news_data and add to news_context
        # except Exception as e:
        #     print(f"Error fetching Alpha Vantage news for {symbol}: {e}")
        return news_context if news_context and "No specific news" not in news_context else "No specific news found via web search for this query."


    async def get_crypto_quote(self, symbol: str, market: str = None): # market can use default from settings
        effective_market = market or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT
        try:
            # Corrected method name
            data, _ = await self._run_sync(self.cc.get_digital_currency_daily, symbol=symbol, market=effective_market)
            
            if data and 'Time Series (Digital Currency Daily)' in data:
                time_series = data['Time Series (Digital Currency Daily)']
                if time_series: # Check if time_series is not empty
                    latest_date = sorted(time_series.keys(), reverse=True)[0]
                    return time_series[latest_date]
            return None
        except Exception as e:
            print(f"Error fetching crypto quote for {symbol} in market {effective_market}: {e}")
            return None
        
financial_data_service = FinancialDataService()