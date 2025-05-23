from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.fundamentaldata import FundamentalData 
from alpha_vantage.cryptocurrencies import CryptoCurrencies 
from alpha_vantage.foreignexchange import ForeignExchange
from app.core.config import settings
from app.services.web_search_service import web_search_service 
import asyncio

class FinancialDataService:
    def __init__(self):
        if not settings.ALPHA_VANTAGE_API_KEY:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set in environment variables.")
        self.ts = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.fd = FundamentalData(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json') 
        self.cc = CryptoCurrencies(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json') 
        self.fx = ForeignExchange(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json') 


    async def _run_sync(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    async def get_stock_quote(self, symbol: str):
        try:
            data, _ = await self._run_sync(self.ts.get_quote_endpoint, symbol=symbol)
            return data
        except Exception as e:
            print(f"Error fetching stock quote for {symbol}: {e}") 
            return None
        
    async def get_company_overview(self, symbol: str):
        try:
            data, _ = await self._run_sync(self.fd.get_company_overview, symbol=symbol)
        except Exception as e:
            print(f"Error fetching company overview for {symbol}: {e}")
            return None
        
    async def get_latest_news_for_stock(self, symbol: str, limit: int = 5):
        news_query = f"latest financial news for {symbol} stock"
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


    async def get_crypto_quote(self, symbol: str, market: str = None):
        from_currency_symbol = symbol
        effective_to_currency = market or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT
        try:
            # data, _ = await self._run_sync(self.cc.get_digital_currency_daily, symbol=symbol, market=effective_market)
            print("****")
            data, _ = await self._run_sync(self.fx.get_currency_exchange_rate,
                                           from_currency=from_currency_symbol,
                                           to_currency=effective_to_currency)
            print(data)
            if data and "5. Exchange Rate" in data: 
                print("_________")
                return data["5. Exchange Rate"]
            return None
        except Exception as e:
            print(f"Error fetching crypto quote for {symbol} in market {effective_to_currency}: {e}")
            return None
        
financial_data_service = FinancialDataService()