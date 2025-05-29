from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.fundamentaldata import FundamentalData
from alpha_vantage.cryptocurrencies import CryptoCurrencies
from alpha_vantage.foreignexchange import ForeignExchange
from alpha_vantage.techindicators import TechIndicators # Added for technical indicators
from alpha_vantage.alphaintelligence import AlphaIntelligence # Added for market news & sentiment (example)

from app.core.config import settings # Assuming this contains ALPHA_VANTAGE_API_KEY and other settings
from app.services.web_search_service import web_search_service # Assuming this service is defined elsewhere
import asyncio

class FinancialDataService:
    def __init__(self):
        if not settings.ALPHA_VANTAGE_API_KEY:
            raise ValueError("ALPHA_VANTAGE_API_KEY not set in environment variables.")
        self.ts = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.fd = FundamentalData(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.cc = CryptoCurrencies(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.fx = ForeignExchange(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')
        self.ti = TechIndicators(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json') # For technical indicators
        # Note: AlphaIntelligence might require a premium key for some functionalities.
        # self.ai = AlphaIntelligence(key=settings.ALPHA_VANTAGE_API_KEY, output_format='json')


    async def _run_sync(self, func, *args, **kwargs):
        """Helper to run synchronous Alpha Vantage calls in an async executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    ## Stock Data Methods ##

    async def get_stock_quote(self, symbol: str):
        """Fetches a real-time quote for a given stock symbol."""
        try:
            data, _ = await self._run_sync(self.ts.get_quote_endpoint, symbol=symbol)
            # print("^^^^ Stock Quote Data ^^^^")
            # print(data)
            return data
        except Exception as e:
            print(f"Error fetching stock quote for {symbol}: {e}")
            return None

    async def get_daily_adjusted_stock_data(self, symbol: str, outputsize: str = 'compact'):
        """
        Fetches daily time series (date, open, high, low, close, adjusted close, volume, dividend, split coefficient)
        for a given stock symbol.
        'outputsize' can be 'compact' (last 100 data points) or 'full' (full-length time series).
        """
        try:
            data, _ = await self._run_sync(self.ts.get_daily_adjusted, symbol=symbol, outputsize=outputsize)
            return data
        except Exception as e:
            print(f"Error fetching daily adjusted stock data for {symbol}: {e}")
            return None

    async def get_intraday_stock_data(self, symbol: str, interval: str = '5min', outputsize: str = 'compact'):
        """
        Fetches intraday time series (date, open, high, low, close, volume) for a given stock symbol.
        'interval' can be '1min', '5min', '15min', '30min', '60min'.
        'outputsize' can be 'compact' or 'full'.
        """
        try:
            data, _ = await self._run_sync(self.ts.get_intraday, symbol=symbol, interval=interval, outputsize=outputsize)
            return data
        except Exception as e:
            print(f"Error fetching intraday stock data for {symbol} with interval {interval}: {e}")
            return None

    ## Fundamental Data Methods ##

    async def get_company_overview(self, symbol: str):
        """Fetches company information, financial ratios, and other key metrics for a given stock symbol."""
        try:
            # The FundamentalData methods in the library sometimes return just the data, not (data, meta_data)
            data = await self._run_sync(self.fd.get_company_overview, symbol=symbol)
            return data
        except Exception as e:
            print(f"Error fetching company overview for {symbol}: {e}")
            return None
        
    async def get_latest_new_for_stock(self, symbol: str, limit: int = 5):
        news_query = f"latest financial news for {symbol} stock" # update this to be better
        #! there was an error : news_context = await web_search_services.get_search_context(news_query, max_results = limit, ["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com"])
        news_context = await web_search_services.get_search_context(
            news_query,
            max_results=limit,
            allowed_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com"]
        )
        return news_context if news_context else "No specific news found via web search."

    async def get_daily_series(self, symbol: str, outputsize: str = "compact"):
        """
        Return OHLC data for a given symbol.
        keys: 'Time Series (Daily)' → {date: { '1. open':..., '4. close':... }}
        """
        data, _ = await self._run_sync(
            self.ts.get_daily, symbol=symbol, outputsize=outputsize
        )
        return data.get("Time Series (Daily)", {})

    async def get_income_statement(self, symbol: str):
        """Fetches annual and quarterly income statements for a given stock symbol."""
        try:
            data = await self._run_sync(self.fd.get_income_statement_annual, symbol=symbol) # Example: Annual
            # You can also fetch quarterly: await self._run_sync(self.fd.get_income_statement_quarterly, symbol=symbol)
            return data
        except Exception as e:
            print(f"Error fetching income statement for {symbol}: {e}")
            return None

    async def get_balance_sheet(self, symbol: str):
        """Fetches annual and quarterly balance sheets for a given stock symbol."""
        try:
            data = await self._run_sync(self.fd.get_balance_sheet_annual, symbol=symbol) # Example: Annual
            return data
        except Exception as e:
            print(f"Error fetching balance sheet for {symbol}: {e}")
            return None

    async def get_cash_flow(self, symbol: str):
        """Fetches annual and quarterly cash flow statements for a given stock symbol."""
        try:
            data = await self._run_sync(self.fd.get_cash_flow_annual, symbol=symbol) # Example: Annual
            return data
        except Exception as e:
            print(f"Error fetching cash flow statement for {symbol}: {e}")
            return None

    async def get_earnings(self, symbol: str):
        """Fetches annual and quarterly earnings (EPS) for a given stock symbol."""
        try:
            data = await self._run_sync(self.fd.get_earnings_annual, symbol=symbol) # Example: Annual
            return data
        except Exception as e:
            print(f"Error fetching earnings for {symbol}: {e}")
            return None

    ## News and Sentiment ##

    async def get_latest_news_for_stock_web(self, symbol: str, limit: int = 5):
        """Fetches latest news for a stock symbol using a web search service."""
        news_query = f"latest financial news for {symbol} stock"
        news_context = await web_search_service.get_search_context(
            news_query, max_results=limit,
            include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", "finance.yahoo.com"]
        )
        return news_context if news_context and "No specific news" not in news_context else "No specific news found via web search for this query."

    async def get_alpha_vantage_news_sentiment(self, tickers: str = None, topics: str = None, time_from: str = None, time_to: str = None, sort: str = "LATEST", limit: int = 50):
        """
        Fetches market news and sentiment data from Alpha Vantage.
        'tickers': e.g., "AAPL" or "MSFT,GOOG"
        'topics': e.g., "technology" or "earnings,ipo"
        'time_from'/'time_to': e.g., "20220410T0130" (YYYYMMDDTHHMM)
        'sort': "LATEST", "EARLIEST", "RELEVANCE"
        'limit': Number of results (max 1000 for premium)
        """
        try:
            # The get_news_sentiment method is on the TimeSeries object in some versions of the library,
            # or could be on a dedicated AlphaIntelligence object depending on library structure/version.
            # Checking the alpha_vantage library documentation for the exact method is crucial.
            # Assuming it's available under self.ts for this example based on original commented code.
            # If AlphaIntelligence class (self.ai) has it, use self.ai.get_news_sentiment
            data, _ = await self._run_sync(self.ts.get_news_sentiment, tickers=tickers, topics=topics, time_from=time_from, time_to=time_to, sort=sort, limit=limit)
            return data
        except Exception as e:
            print(f"Error fetching Alpha Vantage news & sentiment for tickers {tickers} or topics {topics}: {e}")
            return None

    ## Cryptocurrency Data Methods ##

    async def get_crypto_exchange_rate(self, from_currency_symbol: str, to_currency_symbol: str = None):
        """
        Fetches the real-time exchange rate for a cryptocurrency pair.
        Uses the ForeignExchange endpoint, which is suitable for crypto-to-fiat or crypto-to-crypto.
        """
        effective_to_currency = to_currency_symbol or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT
        try:
            # print(f"**** Fetching crypto exchange rate for {from_currency_symbol} to {effective_to_currency} ****")
            data, _ = await self._run_sync(self.fx.get_currency_exchange_rate,
                                           from_currency=from_currency_symbol,
                                           to_currency=effective_to_currency)
            # print(data)
            if data and "Realtime Currency Exchange Rate" in data and \
               "5. Exchange Rate" in data["Realtime Currency Exchange Rate"]:
                # print("_________ Crypto Exchange Rate Found _________")
                return {
                    "from_currency": data["Realtime Currency Exchange Rate"]["1. From_Currency Code"],
                    "to_currency": data["Realtime Currency Exchange Rate"]["3. To_Currency Code"],
                    "exchange_rate": data["Realtime Currency Exchange Rate"]["5. Exchange Rate"],
                    "last_refreshed": data["Realtime Currency Exchange Rate"]["6. Last Refreshed"],
                    "bid_price": data["Realtime Currency Exchange Rate"].get("8. Bid Price"), # Use .get() as bid/ask might not always be present
                    "ask_price": data["Realtime Currency Exchange Rate"].get("9. Ask Price")
                }
            return None
        except Exception as e:
            print(f"Error fetching crypto exchange rate for {from_currency_symbol} to {effective_to_currency}: {e}")
            return None

    async def get_daily_crypto_data(self, symbol: str, market: str):
        """
        Fetches daily time series (date, open, high, low, close, volume, market cap) for a digital currency.
        'market': The destination market (e.g., 'USD', 'EUR', 'CNY').
        """
        try:
            data, _ = await self._run_sync(self.cc.get_digital_currency_daily, symbol=symbol, market=market)
            return data
        except Exception as e:
            print(f"Error fetching daily crypto data for {symbol} in market {market}: {e}")
            return None

    async def get_crypto_rating(self, symbol: str):
        """Fetches the F CAS Crypto Rating for a given cryptocurrency symbol (e.g., BTC, ETH)."""
        try:
            data = await self._run_sync(self.fd.get_crypto_rating, symbol=symbol)
            return data
        except Exception as e:
            print(f"Error fetching crypto rating for {symbol}: {e}")
            return None

    ## Foreign Exchange (FX) Methods ##

    async def get_daily_fx_rates(self, from_symbol: str, to_symbol: str, outputsize: str = 'compact'):
        """
        Fetches daily FX rates for a currency pair.
        'outputsize' can be 'compact' or 'full'.
        """
        try:
            data, _ = await self._run_sync(self.fx.get_currency_exchange_daily, from_symbol=from_symbol, to_symbol=to_symbol, outputsize=outputsize)
            return data
        except Exception as e:
            print(f"Error fetching daily FX rates for {from_symbol} to {to_symbol}: {e}")
            return None

    ## Technical Indicator Methods ##

    async def get_sma(self, symbol: str, interval: str = 'daily', time_period: int = 20, series_type: str = 'close'):
        """
        Fetches Simple Moving Average (SMA) values for a stock.
        'interval': '1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly'.
        'time_period': Number of data points used to calculate SMA.
        'series_type': 'open', 'high', 'low', 'close'.
        """
        try:
            data, _ = await self._run_sync(self.ti.get_sma, symbol=symbol, interval=interval,
                                           time_period=time_period, series_type=series_type)
            return data
        except Exception as e:
            print(f"Error fetching SMA for {symbol}: {e}")
            return None

    async def get_ema(self, symbol: str, interval: str = 'daily', time_period: int = 20, series_type: str = 'close'):
        """Fetches Exponential Moving Average (EMA) values for a stock."""
        try:
            data, _ = await self._run_sync(self.ti.get_ema, symbol=symbol, interval=interval,
                                           time_period=time_period, series_type=series_type)
            return data
        except Exception as e:
            print(f"Error fetching EMA for {symbol}: {e}")
            return None

    ## Economic Indicator Methods ##

    async def get_real_gdp(self, interval: str = 'quarterly'):
        """
        Fetches Real GDP data for the United States.
        'interval': 'annual', 'quarterly'.
        """
        try:
            data = await self._run_sync(self.fd.get_real_gdp, interval=interval)
            return data
        except Exception as e:
            print(f"Error fetching Real GDP data for interval {interval}: {e}")
            return None

    async def get_cpi(self, interval: str = 'monthly'):
        """
        Fetches Consumer Price Index (CPI) data for the United States.
        'interval': 'monthly', 'semiannual'. (Note: semiannual for US is not standard, monthly is common)
        """
        try:
            data = await self._run_sync(self.fd.get_cpi, interval=interval)
            return data
        except Exception as e:
            print(f"Error fetching CPI data for interval {interval}: {e}")
            return None

    async def get_inflation(self):
        """Fetches Inflation data (annual) for the United States."""
        try:
            data = await self._run_sync(self.fd.get_inflation)
            return data
        except Exception as e:
            print(f"Error fetching Inflation data: {e}")
            return None

    async def get_treasury_yield(self, interval: str = 'monthly', maturity: str = '10year'):
        """
        Fetches Treasury Yield data for the United States.
        'interval': 'daily', 'weekly', 'monthly'.
        'maturity': '3month', '2year', '5year', '7year', '10year', '30year'.
        """
        try:
            data = await self._run_sync(self.fd.get_treasury_yield, interval=interval, maturity=maturity)
            return data
        except Exception as e:
            print(f"Error fetching Treasury Yield for {maturity} maturity, interval {interval}: {e}")
            return None

financial_data_service = FinancialDataService()
