from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.fundamentaldata import FundamentalData
from alpha_vantage.cryptocurrencies import CryptoCurrencies
from alpha_vantage.foreignexchange import ForeignExchange
from alpha_vantage.techindicators import TechIndicators # Added for technical indicators
from alpha_vantage.alphaintelligence import AlphaIntelligence # Added for market news & sentiment (example)
import finnhub
from datetime import datetime, timedelta
import time
import pandas as pd
import yfinance as yf

from app.core.config import settings # Assuming this contains ALPHA_VANTAGE_API_KEY and other settings
from app.services.web_search_service import web_search_service # Assuming this service is defined elsewhere
import asyncio

class FinancialDataService:
    def __init__(self):
        # yfinance doesn't require explicit client initialization with an API key here.
        # Calls are made directly, e.g., yf.Ticker("AAPL")
        pass

    async def _run_sync(self, func, *args, **kwargs):
        """Helper to run synchronous yfinance calls in an async executor."""
        loop = asyncio.get_event_loop()
        # For yfinance, func will often be a method of a Ticker object.
        # Example: loop.run_in_executor(None, ticker_object.history, period="1d")
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _format_history_data(self, df_history: pd.DataFrame, interval_is_daily=False, is_fx=False, is_crypto=False):
        """
        Formats yfinance history DataFrame into a dictionary keyed by date string.
        """
        formatted_data = {}
        if df_history.empty:
            return formatted_data

        for index_date, row in df_history.iterrows():
            # yfinance index is typically DatetimeIndex
            if interval_is_daily or is_fx or is_crypto and isinstance(index_date, (datetime, pd.Timestamp)): # Daily data has date only
                 date_key = index_date.strftime("%Y-%m-%d")
            elif isinstance(index_date, (datetime, pd.Timestamp)): # Intraday has datetime
                 date_key = index_date.strftime("%Y-%m-%d %H:%M:%S")
            else:
                continue # Should not happen with standard yfinance history

            entry = {
                '1. open': str(row.get('Open', 'N/A')),
                '2. high': str(row.get('High', 'N/A')),
                '3. low': str(row.get('Low', 'N/A')),
                '4. close': str(row.get('Close', 'N/A')),
            }
            if not is_fx: # FX data from yfinance usually doesn't have volume
                entry['5. volume'] = str(row.get('Volume', 'N/A'))
            
            if interval_is_daily and not is_fx and not is_crypto: # For stocks, AlphaVantage had these
                # yfinance history with auto_adjust=True or actions=True will have adjusted close.
                # If auto_adjust=False, 'Adj Close' might be present if not dropping.
                # For simplicity, if 'Adj Close' is there, use it. Otherwise, 'Close' is already adjusted if auto_adjust=True.
                entry['5. adjusted close'] = str(row.get('Adj Close', row.get('Close', 'N/A')))
                entry['7. dividend amount'] = str(row.get('Dividends', '0.0')) # yf provides 'Dividends'
                entry['8. split coefficient'] = str(row.get('Stock Splits', '0.0')) # yf provides 'Stock Splits'
            
            if is_crypto and interval_is_daily: # Match AV crypto daily output structure
                entry[f'4a. close ({settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT.upper()})'] = str(row.get('Close', 'N/A'))
                entry[f'1a. open ({settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT.upper()})'] = str(row.get('Open', 'N/A'))
                entry[f'2a. high ({settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT.upper()})'] = str(row.get('High', 'N/A'))
                entry[f'3a. low ({settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT.upper()})'] = str(row.get('Low', 'N/A'))
                entry[f'5. volume'] = str(row.get('Volume', 'N/A'))
                entry[f'6. market cap (USD)'] = "N/A" # yfinance history doesn't include live market cap per day

            formatted_data[date_key] = entry
        return formatted_data

    ## Stock Data Methods ##

    async def get_stock_quote(self, symbol: str):
        """Fetches a real-time like quote for a given stock symbol using Ticker.info."""
        try:
            ticker = yf.Ticker(symbol)
            # .info can be slow, consider fetching history for latest price if speed is critical for just price
            info = await self._run_sync(lambda: ticker.info)

            if not info or info.get('regularMarketPrice') is None and info.get('currentPrice') is None : # Check for a key price field
                # Sometimes 'quoteType' being 'NONE' indicates no data
                if info.get('quoteType') == 'NONE':
                    print(f"No quote data found for {symbol} via yfinance (quoteType is NONE).")
                    return None
                # Fallback to history if info is too sparse but symbol is valid
                hist = await self._run_sync(ticker.history, period="2d") # Get last couple of days
                if not hist.empty:
                    latest = hist.iloc[-1]
                    prev_close = hist.iloc[-2]['Close'] if len(hist) > 1 else latest['Open'] # Approx
                    return {
                        "01. symbol": symbol,
                        "02. open": str(latest.get('Open', 'N/A')),
                        "03. high": str(latest.get('High', 'N/A')),
                        "04. low": str(latest.get('Low', 'N/A')),
                        "05. price": str(latest.get('Close', 'N/A')),
                        "06. volume": str(latest.get('Volume', 'N/A')),
                        "07. latest trading day": latest.name.strftime('%Y-%m-%d') if latest.name else "N/A",
                        "08. previous close": str(prev_close),
                        "09. change": str(latest.get('Close', 'N/A') - prev_close),
                        "10. change percent": f"{((latest.get('Close', 0) - prev_close) / prev_close * 100 if prev_close else 0):.2f}%"
                    }
                print(f"Error fetching stock quote for {symbol}: No data in Ticker.info and history.")
                return None

            # Formatting to resemble Alpha Vantage
            quote_data = {
                "01. symbol": symbol,
                "02. open": str(info.get('regularMarketOpen', info.get('open', 'N/A'))),
                "03. high": str(info.get('regularMarketDayHigh', info.get('dayHigh', 'N/A'))),
                "04. low": str(info.get('regularMarketDayLow', info.get('dayLow', 'N/A'))),
                "05. price": str(info.get('regularMarketPrice', info.get('currentPrice', 'N/A'))),
                "06. volume": str(info.get('regularMarketVolume', info.get('volume', 'N/A'))),
                "07. latest trading day": datetime.fromtimestamp(info['regularMarketTime']).strftime('%Y-%m-%d') if 'regularMarketTime' in info else "N/A",
                "08. previous close": str(info.get('regularMarketPreviousClose', info.get('previousClose', 'N/A'))),
                "09. change": str(info.get('regularMarketChange', 'N/A')), # Diff from previous close
                "10. change percent": f"{info.get('regularMarketChangePercent', 0) * 100:.2f}%" if 'regularMarketChangePercent' in info else "N/A"
            }
            return quote_data
        except Exception as e:
            print(f"Error fetching stock quote for {symbol} using yfinance: {e}")
            return None

    async def get_daily_adjusted_stock_data(self, symbol: str, outputsize: str = 'compact'):
        """
        Fetches daily time series (date, open, high, low, close, adjusted close, volume, dividend, split coefficient)
        for a given stock symbol.
        'outputsize' can be 'compact' (last 100 data points) or 'full' (max available, yfinance default).
        """
        try:
            ticker = yf.Ticker(symbol)
            period = '1y' # Default for 'full' like behavior, yfinance handles max available
            if outputsize == 'compact':
                # yfinance doesn't have a direct '100 points' param. Fetch a period and slice.
                # Approx 100 trading days is ~140 calendar days.
                # Or fetch more and then slice the DataFrame. For now, use a period.
                period = "5mo" # Roughly 100 trading days

            # auto_adjust=True handles splits and dividends in OHLCV data.
            # actions=True will add Dividends and Stock Splits columns.
            df = await self._run_sync(ticker.history, period=period, interval="1d", actions=True, auto_adjust=True)
            if df.empty:
                return None
            
            if outputsize == 'compact' and len(df) > 100:
                df = df.tail(100)

            return {
                "Meta Data": {
                    "1. Information": "Daily Time Series with Splits and Dividend Events",
                    "2. Symbol": symbol,
                    "3. Output Size": outputsize,
                    "4. Time Zone": str(df.index.tz) if df.index.tz else "N/A (likely US/Eastern for Yahoo)"
                },
                "Time Series (Daily)": self._format_history_data(df, interval_is_daily=True)
            }
        except Exception as e:
            print(f"Error fetching daily adjusted stock data for {symbol} from yfinance: {e}")
            return None

    async def get_intraday_stock_data(self, symbol: str, interval: str = '5min', outputsize: str = 'compact'):
        """
        Fetches intraday time series (date, open, high, low, close, volume) for a given stock symbol.
        'interval': '1m', '5m', '15m', '30m', '60m' (maps to yfinance '1m', '5m', etc.).
        'outputsize': 'compact' (last 1-2 days) or 'full' (max 7 days for 1m, up to 60 days for others by yfinance).
        """
        yf_interval = interval.replace('min', 'm') # e.g. '5min' -> '5m'

        period = "2d" # Default for compact
        if outputsize == 'full':
            if yf_interval == '1m':
                period = "7d" # Max for 1m interval
            else:
                period = "59d" # Max for other intraday intervals

        try:
            ticker = yf.Ticker(symbol)
            df = await self._run_sync(ticker.history, period=period, interval=yf_interval, actions=False, auto_adjust=False) # No adjustments for raw intraday
            if df.empty:
                return None
            
            # If compact, and data is more than 1-2 days, might need to trim further based on actual dates.
            # For simplicity, yfinance period control is the primary filter here.

            time_series_key = f"Time Series ({interval})" # Original key format
            return {
                 "Meta Data": {
                    "1. Information": f"Intraday ({interval}) Time Series",
                    "2. Symbol": symbol,
                    "3. Output Size": outputsize,
                    "4. Interval": interval,
                    "5. Time Zone": str(df.index.tz) if df.index.tz else "N/A"
                },
                time_series_key: self._format_history_data(df)
            }
        except Exception as e:
            print(f"Error fetching intraday stock data for {symbol} with interval {interval} from yfinance: {e}")
            return None

    ## Fundamental Data Methods ##

    async def get_company_overview(self, symbol: str):
        """Fetches company information, financial ratios, and other key metrics from Ticker.info."""
        try:
            ticker = yf.Ticker(symbol)
            info = await self._run_sync(lambda: ticker.info)
            if not info or info.get('quoteType') == 'NONE':
                return None

            # Map yfinance .info fields to Alpha Vantage like structure
            # This is an approximation, fields will differ.
            overview = {
                "Symbol": info.get('symbol'),
                "AssetType": info.get('quoteType'),
                "Name": info.get('longName', info.get('shortName')),
                "Description": info.get('longBusinessSummary'),
                "CIK": "N/A via yfinance", # Not directly in .info
                "Exchange": info.get('exchange'),
                "Currency": info.get('currency'),
                "Country": info.get('country'),
                "Sector": info.get('sector'),
                "Industry": info.get('industry'),
                "Address": f"{info.get('address1', '')}, {info.get('city', '')}, {info.get('zip', '')}", # Approximate
                "FiscalYearEnd": "N/A", # info.get('lastFiscalYearEnd') is a timestamp
                "LatestQuarter": "N/A", # info.get('mostRecentQuarter') is a timestamp
                "MarketCapitalization": str(info.get('marketCap')),
                "EBITDA": str(info.get('ebitda')),
                "PERatio": str(info.get('trailingPE', info.get('forwardPE'))),
                "PEGRatio": str(info.get('pegRatio')),
                "BookValue": str(info.get('bookValue')),
                "DividendPerShare": str(info.get('dividendRate', info.get('trailingAnnualDividendRate'))), # AV: DividendPerShare
                "DividendYield": str(info.get('dividendYield', info.get('trailingAnnualDividendYield'))),
                "EPS": str(info.get('trailingEps', info.get('forwardEps'))), # AV: DilutedEPSTTM
                "RevenuePerShareTTM": str(info.get('revenuePerShare')),
                "ProfitMargin": str(info.get('profitMargins')),
                "OperatingMarginTTM": str(info.get('operatingMargins')),
                "ReturnOnAssetsTTM": str(info.get('returnOnAssets')),
                "ReturnOnEquityTTM": str(info.get('returnOnEquity')),
                "RevenueTTM": str(info.get('totalRevenue')), # Often TTM
                "GrossProfitTTM": str(info.get('grossProfits')),
                "DilutedEPSTTM": str(info.get('trailingEps')), # yf 'trailingEps'
                "QuarterlyEarningsGrowthYOY": str(info.get('earningsQuarterlyGrowth')),
                "QuarterlyRevenueGrowthYOY": str(info.get('revenueQuarterlyGrowth')), # Not directly in info, usually in financials
                "Beta": str(info.get('beta')),
                "52WeekHigh": str(info.get('fiftyTwoWeekHigh')),
                "52WeekLow": str(info.get('fiftyTwoWeekLow')),
                "50DayMovingAverage": str(info.get('fiftyDayAverage')),
                "200DayMovingAverage": str(info.get('twoHundredDayAverage')),
                "SharesOutstanding": str(info.get('sharesOutstanding')),
                "PriceToSalesRatioTTM": str(info.get('priceToSalesTrailing12Months')),
                "PriceToBookRatio": str(info.get('priceToBook')),
            }
            return overview
        except Exception as e:
            print(f"Error fetching company overview for {symbol} from yfinance: {e}")
            return None
            
    async def get_latest_new_for_stock(self, symbol: str, limit: int = 5):
        # This method uses web_search_service, no change needed for yfinance migration itself
        # However, yfinance also has a news method. We could combine or choose.
        # For now, keeping the original web search based one.
        news_query = f"latest financial news for {symbol} stock"
        news_context = await web_search_service.get_search_context(
            news_query,
            max_results=limit,
            allowed_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com"]
        )
        return news_context if news_context else "No specific news found via web search."

    async def get_daily_series(self, symbol: str, outputsize: str = "compact"):
        """
        Return OHLC data for a given symbol (unadjusted by default from yf history unless auto_adjust=True).
        This will fetch unadjusted data to match Alpha Vantage's 'get_daily' more closely.
        """
        try:
            ticker = yf.Ticker(symbol)
            period = "5mo" # approx 100 points for compact
            if outputsize == 'full':
                period = "max" # yfinance max history

            df = await self._run_sync(ticker.history, period=period, interval="1d", auto_adjust=False, actions=False)
            if df.empty:
                return {}
            
            if outputsize == 'compact' and len(df) > 100:
                df = df.tail(100)
            
            # Original AV returned: data.get("Time Series (Daily)", {})
            return self._format_history_data(df, interval_is_daily=True)
        except Exception as e:
            print(f"Error fetching daily series for {symbol} from yfinance: {e}")
            return {}

    def _format_financial_statement(self, df_statement: pd.DataFrame):
        """Converts a yfinance financial statement DataFrame to a list of dicts (annual/quarterly reports)."""
        reports = []
        if df_statement.empty:
            return reports
        # yfinance financial statements have years/quarters as columns
        for col_date in df_statement.columns:
            report_data = {}
            for index_item, value in df_statement[col_date].items():
                # Sanitize item names (e.g., "Total Revenue" -> "totalRevenue") for consistency if needed
                # For now, use original yfinance index names
                report_data[index_item] = str(value) if pd.notna(value) else "N/A"
            
            reports.append({
                "fiscalDateEnding": col_date.strftime('%Y-%m-%d') if isinstance(col_date, pd.Timestamp) else str(col_date),
                "reportedCurrency": "N/A (typically USD for US companies)", # yf doesn't specify per column
                "statementData": report_data
            })
        return reports

    async def get_income_statement(self, symbol: str):
        """Fetches annual and quarterly income statements for a given stock symbol."""
        try:
            ticker = yf.Ticker(symbol)
            # Fetch annual income statement
            annual_is = await self._run_sync(ticker.income_stmt) # or ticker.financials
            # Fetch quarterly income statement
            quarterly_is = await self._run_sync(ticker.quarterly_income_stmt) # or ticker.quarterly_financials

            return {
                "symbol": symbol,
                "annualReports": self._format_financial_statement(annual_is),
                "quarterlyReports": self._format_financial_statement(quarterly_is)
            }
        except Exception as e:
            print(f"Error fetching income statement for {symbol} from yfinance: {e}")
            return None

    async def get_balance_sheet(self, symbol: str):
        """Fetches annual and quarterly balance sheets for a given stock symbol."""
        try:
            ticker = yf.Ticker(symbol)
            annual_bs = await self._run_sync(ticker.balance_sheet)
            quarterly_bs = await self._run_sync(ticker.quarterly_balance_sheet)
            return {
                "symbol": symbol,
                "annualReports": self._format_financial_statement(annual_bs),
                "quarterlyReports": self._format_financial_statement(quarterly_bs)
            }
        except Exception as e:
            print(f"Error fetching balance sheet for {symbol} from yfinance: {e}")
            return None

    async def get_cash_flow(self, symbol: str):
        """Fetches annual and quarterly cash flow statements for a given stock symbol."""
        try:
            ticker = yf.Ticker(symbol)
            annual_cf = await self._run_sync(ticker.cashflow)
            quarterly_cf = await self._run_sync(ticker.quarterly_cashflow)
            return {
                "symbol": symbol,
                "annualReports": self._format_financial_statement(annual_cf),
                "quarterlyReports": self._format_financial_statement(quarterly_cf)
            }
        except Exception as e:
            print(f"Error fetching cash flow statement for {symbol} from yfinance: {e}")
            return None

    async def get_earnings(self, symbol: str):
        """Fetches historical (annual & quarterly) earnings (EPS) for a given stock symbol."""
        try:
            ticker = yf.Ticker(symbol)
            # .earnings is a DataFrame with 'Revenue' and 'Earnings' columns, index is Year (for annual) or Date (for quarterly)
            df_earnings_hist_annual = await self._run_sync(lambda: ticker.earnings) # Annual by default
            df_earnings_hist_quarterly = await self._run_sync(lambda: ticker.quarterly_earnings)

            annual_reports = []
            if not df_earnings_hist_annual.empty:
                for year, row in df_earnings_hist_annual.iterrows():
                    annual_reports.append({
                        "fiscalDateEnding": f"{year}-12-31", # Assuming year end
                        "reportedEPS": str(row.get('Earnings')),
                        "reportedRevenue": str(row.get('Revenue'))
                    })
            
            quarterly_reports = []
            if not df_earnings_hist_quarterly.empty:
                 for date, row in df_earnings_hist_quarterly.iterrows():
                    quarterly_reports.append({
                        "fiscalDateEnding": date.strftime('%Y-%m-%d') if isinstance(date, pd.Timestamp) else str(date),
                        "reportedEPS": str(row.get('Earnings')),
                        "actualEPS": str(row.get('Actual')), # yf earnings often has 'Estimate', 'Actual', 'Surprise'
                        "estimatedEPS": str(row.get('Estimate')),
                        "surprisePercentage": str(row.get('Surprise(%)'))
                    })

            return {
                "symbol": symbol,
                "annualEarnings": annual_reports,
                "quarterlyEarnings": quarterly_reports[-4:] # Last 4 quarters for recent view
            }
        except Exception as e:
            print(f"Error fetching earnings for {symbol} from yfinance: {e}")
            return None

    ## News and Sentiment ##

    async def get_latest_news_for_stock_web(self, symbol: str, limit: int = 5):
        # This method uses web_search_service, no change needed for yfinance migration itself
        news_query = f"latest financial news for {symbol} stock"
        news_context = await web_search_service.get_search_context(
            news_query, max_results=limit,
            include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", "finance.yahoo.com"]
        )
        return news_context if news_context and "No specific news" not in news_context else "No specific news found via web search for this query."

    async def get_alpha_vantage_news_sentiment(self, tickers: str = None, topics: str = None, time_from: str = None, time_to: str = None, sort: str = "LATEST", limit: int = 50):
        """
        Fetches market news using yfinance Ticker.news.
        'tickers': Can be a single symbol for yfinance. Multi-ticker needs iteration.
        'topics', 'time_from'/'time_to' filtering, 'sort' are not directly supported by yf .news.
        Sentiment is not provided by yfinance.
        """
        if not tickers:
            print("Error: At least one ticker symbol must be provided for yfinance news.")
            return None

        symbol = tickers.split(',')[0].strip() # Use the first ticker for simplicity

        try:
            ticker = yf.Ticker(symbol)
            news_list = await self._run_sync(lambda: ticker.news) # Returns a list of news dicts

            if not news_list:
                return None

            # yfinance .news items typically have: 'uuid', 'title', 'publisher', 'link', 'providerPublishTime', 'type', 'thumbnail', 'relatedTickers'
            # Reformat to somewhat match Alpha Vantage structure's 'feed' part.
            feed_items = []
            for item in news_list[:limit]: # Apply limit
                feed_items.append({
                    "title": item.get('title'),
                    "url": item.get('link'),
                    "time_published": datetime.fromtimestamp(item['providerPublishTime']).strftime('%Y%m%dT%H%M%S') if 'providerPublishTime' in item else "N/A",
                    "authors": [item.get('publisher', 'N/A')],
                    "summary": item.get('title'), # yf news doesn't always have a separate summary field
                    "banner_image": item.get('thumbnail', {}).get('resolutions', [{}])[0].get('url') if item.get('thumbnail') else None,
                    "source": item.get('publisher'),
                    "category_within_source": "N/A",
                    "source_domain": item.get('link').split('/')[2] if item.get('link') else "N/A",
                    "topics": [], # yf news doesn't provide structured topics like AV
                    "overall_sentiment_score": "N/A", # No sentiment from yfinance
                    "overall_sentiment_label": "N/A",
                    "ticker_sentiment": []
                })
            
            return {
                "items": str(len(feed_items)),
                "sentiment_score_definition": "Sentiment not provided by yfinance.",
                "relevance_score_definition": "Relevance score not provided by yfinance.",
                "feed": feed_items
            }
        except Exception as e:
            print(f"Error fetching yfinance news for ticker {symbol}: {e}")
            return None

    ## Cryptocurrency Data Methods ##

    async def get_crypto_exchange_rate(self, from_currency_symbol: str, to_currency_symbol: str = None):
        """
        Fetches the real-time exchange rate for a cryptocurrency pair using yfinance.
        Symbol format for yf: "BTC-USD", "ETH-EUR".
        """
        effective_to_currency = to_currency_symbol or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT
        yf_symbol = f"{from_currency_symbol.upper()}-{effective_to_currency.upper()}"

        try:
            ticker = yf.Ticker(yf_symbol)
            # Fetch very recent history to get "latest" price
            df_hist = await self._run_sync(ticker.history, period="1d", interval="1m") # Try 1m for most recent
            if df_hist.empty:
                 df_hist = await self._run_sync(ticker.history, period="2d", interval="5m") # Fallback
            if df_hist.empty:
                print(f"No recent history found for crypto {yf_symbol} on yfinance.")
                return None

            latest_data = df_hist.iloc[-1]
            return {
                "from_currency": from_currency_symbol.upper(),
                "to_currency": effective_to_currency.upper(),
                "exchange_rate": str(latest_data.get('Close', 'N/A')),
                "last_refreshed": latest_data.name.strftime('%Y-%m-%d %H:%M:%S %Z') if latest_data.name else "N/A",
                "bid_price": "N/A", # yfinance history doesn't provide live bid/ask
                "ask_price": "N/A"
            }
        except Exception as e:
            print(f"Error fetching crypto exchange rate for {yf_symbol} from yfinance: {e}")
            return None

    async def get_daily_crypto_data(self, symbol: str, market: str):
        """
        Fetches daily time series for a digital currency.
        'symbol': e.g., 'BTC'
        'market': The destination market (e.g., 'USD'). yf symbol: "BTC-USD"
        """
        yf_symbol = f"{symbol.upper()}-{market.upper()}"
        try:
            ticker = yf.Ticker(yf_symbol)
            # Fetch a reasonable period, e.g., 1 year. 'compact'/'full' not in original signature for this one.
            df = await self._run_sync(ticker.history, period="1y", interval="1d", auto_adjust=False)
            if df.empty:
                return None

            time_series_key = f"Time Series (Digital Currency Daily)"
            return {
                "Meta Data": {
                    "1. Information": "Daily Prices and Volumes for Digital Currency",
                    "2. Digital Currency Code": symbol.upper(),
                    "3. Digital Currency Name": yf_symbol, # yf doesn't provide a separate "name" field easily here
                    "4. Market Code": market.upper(),
                    "5. Market Name": market.upper(),
                    "6. Last Refreshed": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), # Data is as of last trading day
                    "7. Time Zone": str(df.index.tz) if df.index.tz else "N/A"
                },
                time_series_key: self._format_history_data(df, interval_is_daily=True, is_crypto=True)
            }
        except Exception as e:
            print(f"Error fetching daily crypto data for {yf_symbol} from yfinance: {e}")
            return None

    async def get_crypto_rating(self, symbol: str):
        """FCAS Crypto Rating is not available via yfinance."""
        print(f"Function 'get_crypto_rating' for {symbol} is not supported by yfinance.")
        return None

    ## Foreign Exchange (FX) Methods ##

    async def get_daily_fx_rates(self, from_symbol: str, to_symbol: str, outputsize: str = 'compact'):
        """
        Fetches daily FX rates for a currency pair. yf symbol: "EURUSD=X"
        'outputsize' can be 'compact' (last 100 data points) or 'full'.
        """
        yf_symbol = f"{from_symbol.upper()}{to_symbol.upper()}=X"
        period = "5mo" # Approx 100 points for compact
        if outputsize == 'full':
            period = "max"

        try:
            ticker = yf.Ticker(yf_symbol)
            df = await self._run_sync(ticker.history, period=period, interval="1d", auto_adjust=False)
            if df.empty:
                return None
            
            if outputsize == 'compact' and len(df) > 100:
                df = df.tail(100)

            time_series_key = f"Time Series FX (Daily)"
            return {
                "Meta Data": {
                    "1. Information": "FX Daily Prices",
                    "2. From Symbol": from_symbol.upper(),
                    "3. To Symbol": to_symbol.upper(),
                    "4. Output Size": outputsize,
                    "5. Last Refreshed": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "6. Time Zone": str(df.index.tz) if df.index.tz else "N/A"
                },
                time_series_key: self._format_history_data(df, interval_is_daily=True, is_fx=True)
            }
        except Exception as e:
            print(f"Error fetching daily FX rates for {yf_symbol} from yfinance: {e}")
            return None

    ## Technical Indicator Methods ##
    # yfinance does not directly provide pre-calculated technical indicators.
    # These would need to be calculated using the historical data (e.g., with pandas_ta).
    # For a direct service migration, these are commented out.

    async def get_sma(self, symbol: str, interval: str = 'daily', time_period: int = 20, series_type: str = 'close'):
        """
        Simple Moving Average (SMA) - Not directly provided by yfinance.
        Requires calculation on historical data.
        """
        print(f"Function 'get_sma' for {symbol} requires external calculation using yfinance historical data.")
        return None

    async def get_ema(self, symbol: str, interval: str = 'daily', time_period: int = 20, series_type: str = 'close'):
        """
        Exponential Moving Average (EMA) - Not directly provided by yfinance.
        Requires calculation on historical data.
        """
        print(f"Function 'get_ema' for {symbol} requires external calculation using yfinance historical data.")
        return None

    ## Economic Indicator Methods ##
    # Yahoo Finance is not a primary source for broad macroeconomic indicators like GDP, CPI.
    # These are typically sourced from government agencies (e.g., FRED).

    async def get_real_gdp(self, interval: str = 'quarterly'):
        """Real GDP data is not directly available via yfinance."""
        print(f"Function 'get_real_gdp' is not supported by yfinance.")
        return None

    async def get_cpi(self, interval: str = 'monthly'):
        """Consumer Price Index (CPI) data is not directly available via yfinance."""
        print(f"Function 'get_cpi' is not supported by yfinance.")
        return None

    async def get_inflation(self):
        """Inflation data is not directly available via yfinance."""
        print(f"Function 'get_inflation' is not supported by yfinance.")
        return None

    async def get_treasury_yield(self, interval: str = 'monthly', maturity: str = '10year'):
        """
        Treasury Yield data can be fetched from yfinance using specific ticker symbols for treasury rates.
        E.g., '^TNX' for 10-Year Treasury Yield, '^IRX' for 13 Week Treasury Bill, etc.
        """
        maturity_map = {
            '13week': '^IRX', # 13 Week Treasury Bill
            '5year': '^FVX',  # 5 Year Treasury Yield
            '10year': '^TNX', # 10 Year Treasury Yield
            '30year': '^TYX'  # 30 Year Treasury Yield
        }
        # AlphaVantage maturities: '3month', '2year', '5year', '7year', '10year', '30year'.
        # Mapping what's commonly available on Yahoo Finance.
        yf_treasury_symbol = None
        if maturity == '3month': yf_treasury_symbol = '^IRX' # Closest common equivalent
        elif maturity == '2year': yf_treasury_symbol = None # Less common direct symbol, might need specific CUSIP or ^UST2Y (less reliable)
        elif maturity == '5year': yf_treasury_symbol = '^FVX'
        elif maturity == '7year': yf_treasury_symbol = None # Less common direct symbol
        elif maturity == '10year': yf_treasury_symbol = '^TNX'
        elif maturity == '30year': yf_treasury_symbol = '^TYX'

        if not yf_treasury_symbol:
            print(f"Treasury yield for maturity '{maturity}' does not have a direct common yfinance symbol.")
            return None
        
        # yfinance interval mapping for history: '1d', '1wk', '1mo'
        yf_hist_interval = '1d' # Default to daily
        if interval == 'weekly': yf_hist_interval = '1wk'
        elif interval == 'monthly': yf_hist_interval = '1mo'

        try:
            ticker = yf.Ticker(yf_treasury_symbol)
            # Fetch a reasonable period, e.g., last 5 years for yields
            df = await self._run_sync(ticker.history, period="5y", interval=yf_hist_interval, auto_adjust=False)
            if df.empty:
                return None

            data_points = []
            for index_date, row in df.iterrows():
                 date_key = index_date.strftime("%Y-%m-%d")
                 data_points.append({"date": date_key, "value": str(row.get('Close'))}) # Yield is the closing price

            return {
                "name": f"Treasury Yield {maturity} ({yf_treasury_symbol})",
                "interval": interval,
                "unit": "Percent", # Yields are typically in percent
                "data": data_points
            }
        except Exception as e:
            print(f"Error fetching Treasury Yield for {maturity} ({yf_treasury_symbol}) from yfinance: {e}")
            return None
        
    async def get_price_change_24h(self, symbol: str):
        """
        Fetches the price change for a symbol over the last 24 hours (approximately).
        This can be for stocks, crypto (e.g., "BTC-USD"), or FX (e.g., "EURUSD=X").
        """
        try:
            ticker = yf.Ticker(symbol)
            # Fetch data for the last 2 days. Interval '1h' is a good compromise.
            # For highly volatile or thinly traded assets, a shorter interval might be better,
            # but '1h' is generally available for a 2-day period.
            # auto_adjust=False to get raw 'Close' prices.
            hist_df = await self._run_sync(ticker.history, period="2d", interval="1h", auto_adjust=False)

            if hist_df.empty or len(hist_df) < 2:
                # Fallback to a more granular interval if 1h failed or returned insufficient data
                hist_df = await self._run_sync(ticker.history, period="2d", interval="5m", auto_adjust=False)
                if hist_df.empty or len(hist_df) < 2:
                    print(f"Not enough historical data for {symbol} in the last 2 days to calculate 24h change.")
                    return None

            # Ensure the index is a DatetimeIndex and convert to UTC for consistent comparison
            if not isinstance(hist_df.index, pd.DatetimeIndex):
                print(f"History index for {symbol} is not a DatetimeIndex. Type: {type(hist_df.index)}")
                return None
            
            # Convert to UTC if timezone-aware, or localize to UTC if naive (assuming naive times are UTC)
            if hist_df.index.tz is None:
                hist_df.index = hist_df.index.tz_localize('UTC')
            else:
                hist_df.index = hist_df.index.tz_convert('UTC')
            
            hist_df = hist_df.sort_index() # Ensure data is sorted by time

            # Get the latest available data point
            latest_data_point = hist_df.iloc[-1]
            latest_price = latest_data_point['Close']
            latest_timestamp = latest_data_point.name # This is a pd.Timestamp

            # Determine the target timestamp for 24 hours ago
            target_timestamp_24h_ago = latest_timestamp - timedelta(hours=24)

            # Find the closest available data point to 24 hours ago using asof
            # .asof finds the last row whose index is less than or equal to the target_timestamp_24h_ago
            price_24h_ago_series = hist_df['Close'].asof(target_timestamp_24h_ago)

            if pd.isna(price_24h_ago_series):
                # If no data point is found at or before the 24h ago mark (e.g., new listing, sparse data)
                # use the earliest available point in our 2-day window as a fallback.
                price_24h_ago = hist_df['Close'].iloc[0]
                timestamp_of_price_24h_ago = hist_df.index[0]
                print(f"No data at or before {target_timestamp_24h_ago} for {symbol}. Using earliest point: {price_24h_ago} at {timestamp_of_price_24h_ago}")
            else:
                price_24h_ago = price_24h_ago_series
                # For clarity, find the actual timestamp of the matched 'asof' price
                # This involves getting the index of the 'asof' result.
                # Find the index (timestamp) of the value returned by asof
                temp_df_for_asof_index = hist_df[hist_df.index <= target_timestamp_24h_ago]
                if not temp_df_for_asof_index.empty:
                    timestamp_of_price_24h_ago = temp_df_for_asof_index.index[-1]
                else: # Should not happen if asof returned a non-NaN value from the original df
                    timestamp_of_price_24h_ago = hist_df.index[0]


            if pd.isna(latest_price) or pd.isna(price_24h_ago):
                print(f"Could not determine valid current or 24h ago price for {symbol}.")
                return None

            change_amount = latest_price - price_24h_ago
            change_percent = (change_amount / price_24h_ago) * 100 if price_24h_ago != 0 else 0

            return {
                "symbol": symbol,
                "current_price": float(latest_price),
                "price_24h_ago": float(price_24h_ago),
                "change_amount": float(change_amount),
                "change_percent": float(change_percent),
                "latest_price_timestamp": latest_timestamp.strftime('%Y-%m-%d %H:%M:%S %Z'),
                "reference_price_24h_ago_timestamp": timestamp_of_price_24h_ago.strftime('%Y-%m-%d %H:%M:%S %Z')
            }

        except Exception as e:
            print(f"Error calculating 24h price change for {symbol} using yfinance: {e}")
            # import traceback
            # traceback.print_exc() # For more detailed error logging during development
            return None

financial_data_service = FinancialDataService()