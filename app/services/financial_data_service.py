# app/services/financial_data_service.py
from datetime import datetime, timedelta
import time
import pandas as pd
import yfinance as yf
import asyncio
from typing import Dict, List, Optional, Any

from app.core.config import settings
from app.services.web_search_service import web_search_service

class FinancialDataService:
    def __init__(self):
        # yfinance doesn't require explicit client initialization with an API key here.
        pass

    async def _run_sync(self, func, *args, **kwargs):
        """Helper to run synchronous yfinance calls in an async executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _format_history_data(self, df_history: pd.DataFrame, interval_is_daily=False, is_fx=False, is_crypto=False, symbol_meta: Optional[str] = None):
        """
        Formats yfinance history DataFrame into a dictionary keyed by date string.
        """
        formatted_data = {}
        if df_history.empty:
            return formatted_data

        for index_date, row in df_history.iterrows():
            if isinstance(index_date, (datetime, pd.Timestamp)):
                 date_key = index_date.strftime("%Y-%m-%d %H:%M:%S") if not interval_is_daily else index_date.strftime("%Y-%m-%d")
            else:
                continue 

            entry = {
                '1. open': str(row.get('Open', 'N/A')),
                '2. high': str(row.get('High', 'N/A')),
                '3. low': str(row.get('Low', 'N/A')),
                '4. close': str(row.get('Close', 'N/A')),
            }
            if not is_fx:
                entry['5. volume'] = str(row.get('Volume', 'N/A'))
            
            if interval_is_daily and not is_fx and not is_crypto:
                entry['5. adjusted close'] = str(row.get('Adj Close', row.get('Close', 'N/A'))) # yf history with auto_adjust=True, 'Close' is already adj.
                entry['7. dividend amount'] = str(row.get('Dividends', '0.0'))
                entry['8. split coefficient'] = str(row.get('Stock Splits', '0.0')) # yf provides 'Stock Splits', 0.0 if no split
            
            if is_crypto and interval_is_daily:
                # For crypto, yfinance symbol usually includes the market pair e.g. BTC-USD
                market_in_symbol = symbol_meta.split('-')[-1] if symbol_meta else settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT.upper()
                entry[f'1a. open ({market_in_symbol})'] = str(row.get('Open', 'N/A'))
                entry[f'2a. high ({market_in_symbol})'] = str(row.get('High', 'N/A'))
                entry[f'3a. low ({market_in_symbol})'] = str(row.get('Low', 'N/A'))
                entry[f'4a. close ({market_in_symbol})'] = str(row.get('Close', 'N/A'))
                entry[f'5. volume'] = str(row.get('Volume', 'N/A'))
                entry[f'6. market cap ({market_in_symbol})'] = "N/A" # yfinance history doesn't include live market cap per day in history

            formatted_data[date_key] = entry
        return formatted_data

    ## Stock Data Methods ##

    async def get_stock_quote(self, symbol: str) -> Optional[Dict[str, str]]:
        """Fetches a real-time like quote for a given stock symbol using Ticker.info or recent history."""
        try:
            ticker = yf.Ticker(symbol)
            info = await self._run_sync(lambda: ticker.info)

            if info and info.get('regularMarketPrice') is not None:
                quote_data = {
                    "01. symbol": symbol.upper(),
                    "02. open": str(info.get('regularMarketOpen', info.get('open', 'N/A'))),
                    "03. high": str(info.get('regularMarketDayHigh', info.get('dayHigh', 'N/A'))),
                    "04. low": str(info.get('regularMarketDayLow', info.get('dayLow', 'N/A'))),
                    "05. price": str(info.get('regularMarketPrice', info.get('currentPrice', 'N/A'))),
                    "06. volume": str(info.get('regularMarketVolume', info.get('volume', 'N/A'))),
                    "07. latest trading day": datetime.fromtimestamp(info['regularMarketTime']).strftime('%Y-%m-%d') if 'regularMarketTime' in info and info['regularMarketTime'] else "N/A",
                    "08. previous close": str(info.get('regularMarketPreviousClose', info.get('previousClose', 'N/A'))),
                    "09. change": str(info.get('regularMarketChange', 'N/A')),
                    "10. change percent": f"{info.get('regularMarketChangePercent', 0) * 100:.4f}%" if info.get('regularMarketChangePercent') is not None else "N/A"
                }
                return quote_data
            else: # Fallback to history if info is sparse or lacks price
                hist = await self._run_sync(ticker.history, period="2d", interval="1d")
                if not hist.empty:
                    latest = hist.iloc[-1]
                    prev_close_val = hist.iloc[-2]['Close'] if len(hist) > 1 else latest['Open'] # Approx
                    current_price_val = latest.get('Close')

                    change_val = (current_price_val - prev_close_val) if current_price_val is not None and prev_close_val is not None else None
                    change_percent_val = (change_val / prev_close_val * 100) if change_val is not None and prev_close_val and prev_close_val != 0 else None
                    
                    return {
                        "01. symbol": symbol.upper(),
                        "02. open": str(latest.get('Open', 'N/A')),
                        "03. high": str(latest.get('High', 'N/A')),
                        "04. low": str(latest.get('Low', 'N/A')),
                        "05. price": str(current_price_val if current_price_val is not None else 'N/A'),
                        "06. volume": str(latest.get('Volume', 'N/A')),
                        "07. latest trading day": latest.name.strftime('%Y-%m-%d') if latest.name else "N/A",
                        "08. previous close": str(prev_close_val if prev_close_val is not None else 'N/A'),
                        "09. change": str(change_val if change_val is not None else 'N/A'),
                        "10. change percent": f"{change_percent_val:.4f}%" if change_percent_val is not None else "N/A"
                    }
            print(f"Error fetching stock quote for {symbol}: No comprehensive data in Ticker.info and history fallback failed or incomplete.")
            return {"Error Message": f"Could not retrieve a valid quote for {symbol.upper()}. The symbol may be incorrect, delisted, or data may be temporarily unavailable."}

        except Exception as e:
            print(f"Exception fetching stock quote for {symbol} using yfinance: {e}")
            return {"Error Message": f"An error occurred while fetching quote for {symbol.upper()}: {str(e)}"}

    async def get_daily_adjusted_stock_data(self, symbol: str, outputsize: str = 'compact'):
        try:
            ticker = yf.Ticker(symbol)
            period = "max" # yfinance default, we will slice later if 'compact'
            
            # auto_adjust=False and actions=True gives 'Adj Close', 'Dividends', 'Stock Splits'
            df = await self._run_sync(ticker.history, period=period, interval="1d", actions=True, auto_adjust=False)
            if df.empty:
                return {"Error Message": f"No daily data found for symbol {symbol}."}
            
            # Ensure 'Adj Close' exists, if not, use 'Close' as a fallback for it.
            if 'Adj Close' not in df.columns:
                df['Adj Close'] = df['Close'] 

            df = df.sort_index(ascending=False) # Sort descending by date like Alpha Vantage
            if outputsize == 'compact':
                df = df.head(100)

            return {
                "Meta Data": {
                    "1. Information": "Daily Time Series with Splits and Dividend Events",
                    "2. Symbol": symbol.upper(),
                    "3. Output Size": outputsize,
                    "4. Time Zone": str(df.index.tz) if df.index.tz else "UTC" # Yahoo data is typically UTC for daily
                },
                "Time Series (Daily)": self._format_history_data(df.sort_index(ascending=True), interval_is_daily=True) # format expects ascending
            }
        except Exception as e:
            print(f"Error fetching daily adjusted stock data for {symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve daily adjusted stock data for {symbol}: {str(e)}"}

    async def get_intraday_stock_data(self, symbol: str, interval: str = '5min', outputsize: str = 'compact'):
        yf_interval_map = {
            '1min': '1m', '5min': '5m', '15min': '15m', '30min': '30m', '60min': '1h'
        }
        yf_interval = yf_interval_map.get(interval, '5m')

        # Max period for intraday data varies with interval in yfinance
        # '1m' is 7 days, others up to 60 days.
        # For 'compact', we usually want the last 1-2 days.
        period = "2d" # Good default for compact view of intraday
        if outputsize == 'full':
            if yf_interval == '1m': period = "7d"
            else: period = "59d" 

        try:
            ticker = yf.Ticker(symbol)
            df = await self._run_sync(ticker.history, period=period, interval=yf_interval, actions=False, auto_adjust=False)
            if df.empty:
                return {"Error Message": f"No intraday data found for {symbol} with interval {interval}."}

            df = df.sort_index(ascending=False) # Sort descending by date/time
            # outputsize 'compact' for intraday can mean ~100-200 points depending on interval
            # yfinance period control is the main filter here. If more specific trimming needed, do it here.
            # For now, this is sufficient for 'compact' vs 'full' distinction based on period.

            time_series_key = f"Time Series ({interval})"
            return {
                 "Meta Data": {
                    "1. Information": f"Intraday ({interval}) Time Series",
                    "2. Symbol": symbol.upper(),
                    "3. Output Size": outputsize, # Reflects requested, period implies actual
                    "4. Interval": interval,
                    "5. Time Zone": str(df.index.tz) if df.index.tz else "N/A (likely market local time)"
                },
                time_series_key: self._format_history_data(df.sort_index(ascending=True)) # format expects ascending
            }
        except Exception as e:
            print(f"Error fetching intraday stock data for {symbol} ({interval}): {e}")
            return {"Error Message": f"Failed to retrieve intraday data for {symbol} ({interval}): {str(e)}"}

    ## Fundamental Data Methods ##
    async def get_company_overview(self, symbol: str):
        try:
            ticker = yf.Ticker(symbol)
            info = await self._run_sync(lambda: ticker.info)
            if not info or info.get('quoteType') == 'NONE' or not info.get('longName'): # Check for essential fields
                 return {"Error Message": f"No company overview data found for symbol {symbol}. It may be invalid or not a stock."}

            overview = {
                "Symbol": info.get('symbol', symbol.upper()), # Use input symbol if yf doesn't return one
                "AssetType": info.get('quoteType'),
                "Name": info.get('longName', info.get('shortName')),
                "Description": info.get('longBusinessSummary'),
                "CIK": "N/A (Not provided by yfinance)",
                "Exchange": info.get('exchange'),
                "Currency": info.get('currency'),
                "Country": info.get('country'),
                "Sector": info.get('sector'),
                "Industry": info.get('industry'),
                "Address": ", ".join(filter(None, [info.get('address1'), info.get('city'), info.get('state'), info.get('zip'), info.get('country')])),
                "FiscalYearEnd": info.get('fiscalYearEnd'), # This is a timestamp, might need formatting
                "LatestQuarter": info.get('mostRecentQuarter'), # Timestamp
                "MarketCapitalization": str(info.get('marketCap')),
                "EBITDA": str(info.get('ebitda')),
                "PERatio": str(info.get('trailingPE', info.get('forwardPE'))),
                "PEGRatio": str(info.get('pegRatio')),
                "BookValue": str(info.get('bookValue')),
                "DividendPerShare": str(info.get('dividendRate', info.get('trailingAnnualDividendRate'))),
                "DividendYield": str(info.get('dividendYield', info.get('trailingAnnualDividendYield'))),
                "EPS": str(info.get('trailingEps', info.get('forwardEps'))),
                "RevenuePerShareTTM": str(info.get('revenuePerShare')), # TTM if available
                "ProfitMargin": str(info.get('profitMargins')),
                "OperatingMarginTTM": str(info.get('operatingMargins')),
                "ReturnOnAssetsTTM": str(info.get('returnOnAssets')),
                "ReturnOnEquityTTM": str(info.get('returnOnEquity')),
                "RevenueTTM": str(info.get('totalRevenue')), # often TTM
                "GrossProfitTTM": str(info.get('grossProfits')),
                "DilutedEPSTTM": str(info.get('trailingEps')),
                "QuarterlyEarningsGrowthYOY": str(info.get('earningsQuarterlyGrowth')),
                "QuarterlyRevenueGrowthYOY": str(info.get('revenueGrowth')), # yfinance has `revenueGrowth` (yoy)
                "AnalystTargetPrice": str(info.get('targetMeanPrice')),
                "Beta": str(info.get('beta')),
                "52WeekHigh": str(info.get('fiftyTwoWeekHigh')),
                "52WeekLow": str(info.get('fiftyTwoWeekLow')),
                "50DayMovingAverage": str(info.get('fiftyDayAverage')),
                "200DayMovingAverage": str(info.get('twoHundredDayAverage')),
                "SharesOutstanding": str(info.get('sharesOutstanding')),
                "DividendDate": info.get('exDividendDate'), # Timestamp
                "PriceToSalesRatioTTM": str(info.get('priceToSalesTrailing12Months')),
                "PriceToBookRatio": str(info.get('priceToBook')),
            }
            # Convert timestamps to readable dates if they exist
            for key in ["FiscalYearEnd", "LatestQuarter", "DividendDate"]:
                if overview.get(key) and isinstance(overview[key], (int, float)):
                    try:
                        overview[key] = datetime.fromtimestamp(overview[key]).strftime('%Y-%m-%d')
                    except:
                        overview[key] = str(overview[key]) # keep as string if conversion fails
            return overview
        except Exception as e:
            print(f"Error fetching company overview for {symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve company overview for {symbol}: {str(e)}"}

    async def get_daily_series(self, symbol: str, outputsize: str = "compact"):
        """Fetches daily OHLCV data (unadjusted by default)."""
        try:
            ticker = yf.Ticker(symbol)
            period = "max"
            df = await self._run_sync(ticker.history, period=period, interval="1d", auto_adjust=False, actions=False)
            if df.empty:
                return {} # Return empty dict if no data, as per original expectation
            
            df = df.sort_index(ascending=False)
            if outputsize == 'compact':
                df = df.head(100)
            
            return self._format_history_data(df.sort_index(ascending=True), interval_is_daily=True)
        except Exception as e:
            print(f"Error fetching daily series for {symbol} from yfinance: {e}")
            return {} # Return empty dict on error

    def _format_financial_statement(self, df_statement: pd.DataFrame, report_type: str):
        reports = []
        if df_statement.empty:
            return reports
        
        # yfinance financial statements have years/quarters as columns (datetime objects)
        # The actual data items are in the index.
        # We want to transpose this so each column (date) becomes a separate report dict.
        df_transposed = df_statement.transpose()

        for date_col, row_data in df_transposed.iterrows():
            report_data_dict = {item: str(value) if pd.notna(value) else "N/A" for item, value in row_data.items()}
            reports.append({
                "fiscalDateEnding": date_col.strftime('%Y-%m-%d') if isinstance(date_col, pd.Timestamp) else str(date_col),
                "reportedCurrency": "N/A (typically USD for US companies, check source for specifics)",
                **report_data_dict # Unpack all financial items directly into the report
            })
        return reports


    async def get_income_statement(self, symbol: str):
        try:
            ticker = yf.Ticker(symbol)
            # Correctly access the DataFrame properties using a lambda within _run_sync
            annual_is = await self._run_sync(lambda: ticker.income_stmt)
            quarterly_is = await self._run_sync(lambda: ticker.quarterly_income_stmt)
            
            # Check if DataFrames are empty or None before formatting
            if annual_is is None or annual_is.empty:
                print(f"Warning: Annual income statement for {symbol} is None or empty.")
            if quarterly_is is None or quarterly_is.empty:
                print(f"Warning: Quarterly income statement for {symbol} is None or empty.")

            return {
                "symbol": symbol.upper(),
                "annualReports": self._format_financial_statement(annual_is if annual_is is not None else pd.DataFrame(), "Income Statement"),
                "quarterlyReports": self._format_financial_statement(quarterly_is if quarterly_is is not None else pd.DataFrame(), "Income Statement")
            }
        except Exception as e:
            print(f"Error fetching income statement for {symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve income statement for {symbol}: {str(e)}"}

# Apply the same fix to get_balance_sheet, get_cash_flow, etc. if they have similar errors:
# Example for get_balance_sheet:
    async def get_balance_sheet(self, symbol: str):
        try:
            ticker = yf.Ticker(symbol)
            annual_bs = await self._run_sync(lambda: ticker.balance_sheet)
            quarterly_bs = await self._run_sync(lambda: ticker.quarterly_balance_sheet)

            if annual_bs is None or annual_bs.empty:
                print(f"Warning: Annual balance sheet for {symbol} is None or empty.")
            if quarterly_bs is None or quarterly_bs.empty:
                print(f"Warning: Quarterly balance sheet for {symbol} is None or empty.")
                
            return {
                "symbol": symbol.upper(),
                "annualReports": self._format_financial_statement(annual_bs if annual_bs is not None else pd.DataFrame(), "Balance Sheet"),
                "quarterlyReports": self._format_financial_statement(quarterly_bs if quarterly_bs is not None else pd.DataFrame(), "Balance Sheet")
            }
        except Exception as e:
            print(f"Error fetching balance sheet for {symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve balance sheet for {symbol}: {str(e)}"}

    async def get_cash_flow(self, symbol: str):
        try:
            ticker = yf.Ticker(symbol)
            annual_cf = await self._run_sync(lambda: ticker.cashflow)
            quarterly_cf = await self._run_sync(lambda: ticker.quarterly_cashflow)

            if annual_cf is None or annual_cf.empty:
                print(f"Warning: Annual cash flow for {symbol} is None or empty.")
            if quarterly_cf is None or quarterly_cf.empty:
                print(f"Warning: Quarterly cash flow for {symbol} is None or empty.")

            return {
                "symbol": symbol.upper(),
                "annualReports": self._format_financial_statement(annual_cf if annual_cf is not None else pd.DataFrame(), "Cash Flow"),
                "quarterlyReports": self._format_financial_statement(quarterly_cf if quarterly_cf is not None else pd.DataFrame(), "Cash Flow")
            }
        except Exception as e:
            print(f"Error fetching cash flow for {symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve cash flow statement for {symbol}: {str(e)}"}

    async def get_earnings(self, symbol: str):
        """
        Fetches historical annual and quarterly earnings data.
        Prioritizes EPS and Revenue from Income Statements as per yfinance deprecation warning.
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Fetch annual and quarterly income statements
            # These are already DataFrames from the corrected get_income_statement logic
            annual_is_df = await self._run_sync(lambda: ticker.income_stmt)
            quarterly_is_df = await self._run_sync(lambda: ticker.quarterly_income_stmt)

            annual_reports = []
            if annual_is_df is not None and not annual_is_df.empty:
                # yfinance income_stmt has years as columns, items as index
                # Transpose to iterate by report date (column)
                for report_date_col, report_data in annual_is_df.transpose().iterrows():
                    fiscal_date_str = report_date_col.strftime('%Y-%m-%d') if isinstance(report_date_col, pd.Timestamp) else str(report_date_col)
                    
                    # Common keys to look for in yfinance income statement for earnings related data
                    # Exact names can vary slightly, so use .get() and provide fallbacks or check alternatives
                    reported_eps = report_data.get('Diluted EPS', report_data.get('Basic EPS', 'N/A'))
                    net_income = report_data.get('Net Income', report_data.get('Net Income Common Stockholders', 'N/A'))
                    revenue = report_data.get('Total Revenue', report_data.get('Operating Revenue', 'N/A'))
                    
                    # If EPS is N/A but Net Income is available, you might calculate it if you have shares outstanding.
                    # For simplicity now, we'll rely on direct EPS figures if present.

                    annual_reports.append({
                        "fiscalDateEnding": fiscal_date_str,
                        "reportedEPS": str(reported_eps), 
                        "netIncome": str(net_income), # Adding Net Income for more context
                        "reportedRevenue": str(revenue)
                    })
            else:
                print(f"Warning: Annual income statement for {symbol} (for earnings extraction) is None or empty.")
                
            quarterly_reports = []
            if quarterly_is_df is not None and not quarterly_is_df.empty:
                for report_date_col, report_data in quarterly_is_df.transpose().iterrows():
                    fiscal_date_str = report_date_col.strftime('%Y-%m-%d') if isinstance(report_date_col, pd.Timestamp) else str(report_date_col)

                    reported_eps = report_data.get('Diluted EPS', report_data.get('Basic EPS', 'N/A'))
                    net_income = report_data.get('Net Income', report_data.get('Net Income Common Stockholders', 'N/A'))
                    revenue = report_data.get('Total Revenue', report_data.get('Operating Revenue', 'N/A'))
                    
                    # yfinance might also have 'Earnings Estimate' in some contexts, but typically not in historical income_stmt.
                    # The old code had "estimatedEPS" and "surprisePercentage", these are usually from earnings calendar data,
                    # not directly from historical income statements. We'll omit them for now to align with income_stmt data.

                    quarterly_reports.append({
                        "fiscalDateEnding": fiscal_date_str,
                        "reportedEPS": str(reported_eps),
                        "netIncome": str(net_income),
                        "reportedRevenue": str(revenue)
                        # "estimatedEPS" and "surprisePercentage" are typically from Ticker.calendar or Ticker.earnings_dates
                        # which provide forward-looking or recent actual vs estimate.
                        # For this function focusing on historical "earnings" from income statement, these are less relevant.
                    })
            else:
                print(f"Warning: Quarterly income statement for {symbol} (for earnings extraction) is None or empty.")

            # If still no reports, indicate this clearly.
            if not annual_reports and not quarterly_reports:
                print(f"Warning: No earnings data could be extracted from income statements for {symbol}.")
                # Fallback: you could try to fetch Ticker.earnings_history if it provides anything,
                # but given the deprecation of Ticker.earnings, it's safer to rely on income_stmt.

            return {
                "symbol": symbol.upper(),
                "annualEarnings": sorted(annual_reports, key=lambda x: x['fiscalDateEnding'], reverse=True),
                "quarterlyEarnings": sorted(quarterly_reports, key=lambda x: x['fiscalDateEnding'], reverse=True)
            } 
        except Exception as e:
            print(f"Error processing earnings from income statements for {symbol} from yfinance: {e}")
            traceback.print_exc() # Good for debugging
            return {"Error Message": f"Failed to retrieve/process earnings data for {symbol}: {str(e)}"}
        
    ## News and Sentiment ##
    async def get_latest_news_for_stock_web(self, symbol: str, limit: int = 5):
        """This uses web_search_service, not directly yfinance financial data. Preserved."""
        news_query = f"latest financial news for {symbol} stock"
        news_context = await web_search_service.get_search_context(
            news_query, max_results=limit,
            include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", "finance.yahoo.com"]
        )
        return news_context if news_context and "No relevant information" not in news_context else f"No specific news found via web search for {symbol}."

    async def get_alpha_vantage_news_sentiment(self, tickers: str = None, topics: str = None, time_from: str = None, time_to: str = None, sort: str = "LATEST", limit: int = 50):
        # (Consider renaming this to get_yfinance_ticker_news for clarity)
        if not tickers:
            return {"Error Message": "Ticker symbol must be provided."}

        symbol = tickers.split(',')[0].strip().upper()

        try:
            ticker = yf.Ticker(symbol)
            # yf.Ticker.news returns a list of dictionaries
            raw_news_list = await self._run_sync(lambda: ticker.news) 

            if not raw_news_list:
                return {"items": "0", "feed": [], "Note": f"No news found for {symbol} via yfinance."}

            feed_items = []
            for raw_item in raw_news_list[:limit]: # Iterate through raw items from yfinance
                # --- Corrected Key Access ---
                content_data = raw_item.get('content', {}) # Safely get the 'content' sub-dictionary

                title = content_data.get('title')
                
                # URL is nested deeper
                canonical_url_data = content_data.get('canonicalUrl', {})
                url = canonical_url_data.get('url')

                # Publisher (source) is also nested
                provider_data = content_data.get('provider', {})
                publisher_name = provider_data.get('displayName')
                
                # Summary
                summary = content_data.get('summary', title) # Use title as fallback for summary

                # Thumbnail
                thumbnail_data = content_data.get('thumbnail', {})
                banner_image_url = None
                if thumbnail_data:
                    resolutions = thumbnail_data.get('resolutions', [])
                    if resolutions: # yfinance might return a list of resolutions
                        # Prefer 'original' or take the first one if 'original' is not tagged,
                        # or simply the first one if structure is simpler.
                        # For simplicity, let's try to find one with 'original' tag or just the first.
                        original_res = next((res for res in resolutions if res.get('tag') == 'original'), None)
                        if original_res:
                            banner_image_url = original_res.get('url')
                        elif resolutions: # take first if no original
                            banner_image_url = resolutions[0].get('url')
                    else: # If resolutions is empty but thumbnail exists, sometimes URL is directly there
                        banner_image_url = thumbnail_data.get('originalUrl') # Fallback

                # Time published - yfinance raw data has 'pubDate' and 'displayTime'
                # 'pubDate' seems more like the actual publication UTC timestamp.
                # 'providerPublishTime' was used before, let's check if 'pubDate' is better.
                # The raw sample you showed has 'pubDate': '2025-05-29T15:59:15Z' in 'content'
                # Let's use 'pubDate' from content_data, if not, fallback.
                
                publish_time_str = "N/A"
                pub_date_raw = content_data.get('pubDate') # This is often a string like 'YYYY-MM-DDTHH:MM:SSZ'
                
                if pub_date_raw:
                    try:
                        # Convert ISO 8601 string to datetime object then to desired string format
                        dt_obj = datetime.fromisoformat(pub_date_raw.replace('Z', '+00:00')) # Handle 'Z' for UTC
                        publish_time_str = dt_obj.strftime('%Y%m%dT%H%M%S') # Format like AlphaVantage
                    except ValueError:
                        publish_time_str = str(pub_date_raw) # Keep as is if parsing fails
                elif 'providerPublishTime' in raw_item and raw_item['providerPublishTime']: # Fallback to old logic if pubDate not in content
                    try:
                        # This was the old logic, might be needed if 'pubDate' isn't always there
                        publish_time_str = datetime.fromtimestamp(int(raw_item['providerPublishTime'])).strftime('%Y%m%dT%H%M%S')
                    except Exception:
                        publish_time_str = str(raw_item['providerPublishTime'])


                # Source domain from URL
                source_domain = "N/A"
                if url and '//' in url:
                    try:
                        source_domain = url.split('/')[2]
                    except IndexError:
                        pass

                feed_items.append({
                    "title": title,
                    "url": url,
                    "time_published": publish_time_str,
                    "authors": [publisher_name] if publisher_name else ['N/A'], # Use displayName as author
                    "summary": summary,
                    "banner_image": banner_image_url,
                    "source": publisher_name or "N/A", # Use displayName as source
                    "category_within_source": "N/A", # Not directly available
                    "source_domain": source_domain,
                    "topics": [], # Not directly available in this structured way
                    "overall_sentiment_score": "N/A", # yfinance doesn't provide this
                    "overall_sentiment_label": "N/A",
                    "ticker_sentiment": [{"ticker": symbol, "relevance_score": "N/A", "ticker_sentiment_score": "N/A", "ticker_sentiment_label": "N/A"}]
                })
            
            return {
                "items": str(len(feed_items)),
                "feed": feed_items
                # Removed sentiment/relevance score definitions as they are N/A
            }
        except Exception as e:
            print(f"Error fetching yfinance news for ticker {symbol}: {e}")
            traceback.print_exc() # Print full traceback for better debugging
            return {"Error Message": f"Failed to retrieve news for {symbol}: {str(e)}"}
    ## Cryptocurrency Data Methods ##
    async def get_crypto_exchange_rate(self, from_currency_symbol: str, to_currency_symbol: str = None):
        effective_to_currency = to_currency_symbol or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT # Use existing setting as default
        yf_symbol = f"{from_currency_symbol.upper()}-{effective_to_currency.upper()}"

        try:
            ticker = yf.Ticker(yf_symbol)
            # For "exchange rate", info might be enough if available and fresh
            info = await self._run_sync(lambda: ticker.info)
            if info and info.get('regularMarketPrice'):
                 last_refreshed_ts = info.get('regularMarketTime')
                 last_refreshed_str = datetime.fromtimestamp(last_refreshed_ts).strftime('%Y-%m-%d %H:%M:%S %Z') if last_refreshed_ts else "N/A"
                 return {
                    "Realtime Currency Exchange Rate": { # Mimicking AV structure
                        "1. From_Currency Code": from_currency_symbol.upper(),
                        "2. From_Currency Name": info.get('fromCurrency', from_currency_symbol.upper()), # yf info might have this
                        "3. To_Currency Code": effective_to_currency.upper(),
                        "4. To_Currency Name": info.get('toCurrency', effective_to_currency.upper()),
                        "5. Exchange Rate": str(info.get('regularMarketPrice')),
                        "6. Last Refreshed": last_refreshed_str,
                        "7. Time Zone": "UTC", # Common for crypto, yf source dependent
                        "8. Bid Price": str(info.get('bid', 'N/A')),
                        "9. Ask Price": str(info.get('ask', 'N/A')),
                    }
                 }
            
            # Fallback to history if info is not sufficient
            # Fetch very recent history to get "latest" price (last 1 day, most granular interval available)
            df_hist = await self._run_sync(ticker.history, period="2d", interval="1m") # Try 1m for most recent
            if df_hist.empty:
                df_hist = await self._run_sync(ticker.history, period="2d", interval="5m") # Fallback
            
            if df_hist.empty:
                return {"Error Message": f"No recent history found for crypto {yf_symbol} on yfinance to determine exchange rate."}

            latest_data = df_hist.iloc[-1]
            return { # Simpler structure for history fallback
                "from_currency": from_currency_symbol.upper(),
                "to_currency": effective_to_currency.upper(),
                "exchange_rate": str(latest_data.get('Close', 'N/A')),
                "last_refreshed": latest_data.name.strftime('%Y-%m-%d %H:%M:%S %Z') if latest_data.name and hasattr(latest_data.name, 'strftime') else "N/A",
                "bid_price": "N/A", # yfinance history doesn't provide live bid/ask
                "ask_price": "N/A",
                "Note": "Data from recent history, not live quote."
            }
        except Exception as e:
            print(f"Error fetching crypto exchange rate for {yf_symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve exchange rate for {yf_symbol}: {str(e)}"}

    async def get_daily_crypto_data(self, symbol: str, market: str): # market is like 'USD', 'EUR'
        yf_symbol = f"{symbol.upper()}-{market.upper()}"
        try:
            ticker = yf.Ticker(yf_symbol)
            df = await self._run_sync(ticker.history, period="max", interval="1d", auto_adjust=False) # Get all daily data
            if df.empty:
                return {"Error Message": f"No daily crypto data found for {yf_symbol}."}

            df = df.sort_index(ascending=False) # Sort descending

            # Attempt to get a "name" for the crypto from info if possible
            crypto_name = yf_symbol
            try:
                info = await self._run_sync(lambda: ticker.info)
                if info and info.get('shortName'): crypto_name = info.get('shortName')
                elif info and info.get('longName'): crypto_name = info.get('longName')
            except: pass


            time_series_key = f"Time Series (Digital Currency Daily)"
            return {
                "Meta Data": {
                    "1. Information": "Daily Prices and Volumes for Digital Currency",
                    "2. Digital Currency Code": symbol.upper(),
                    "3. Digital Currency Name": crypto_name,
                    "4. Market Code": market.upper(),
                    "5. Market Name": market.upper(), # Often same as code
                    "6. Last Refreshed": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), # Indicates when data was fetched by us
                    "7. Time Zone": "UTC" # Crypto daily data often UTC
                },
                time_series_key: self._format_history_data(df.sort_index(ascending=True), interval_is_daily=True, is_crypto=True, symbol_meta=yf_symbol)
            }
        except Exception as e:
            print(f"Error fetching daily crypto data for {yf_symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve daily crypto data for {yf_symbol}: {str(e)}"}
            
    async def get_crypto_rating(self, symbol: str):
        """FCAS Crypto Rating is not available via yfinance. This function is a no-op."""
        print(f"Function 'get_crypto_rating' for {symbol} is not supported by yfinance.")
        return {"Note": f"Crypto ratings (FCAS) are not available through yfinance for {symbol}."}

    ## Foreign Exchange (FX) Methods ##
    async def get_daily_fx_rates(self, from_symbol: str, to_symbol: str, outputsize: str = 'compact'):
        yf_symbol = f"{from_symbol.upper()}{to_symbol.upper()}=X"
        period = "max"
        
        try:
            ticker = yf.Ticker(yf_symbol)
            df = await self._run_sync(ticker.history, period=period, interval="1d", auto_adjust=False)
            if df.empty:
                return {"Error Message": f"No daily FX rates found for {yf_symbol}."}

            df = df.sort_index(ascending=False)
            if outputsize == 'compact':
                df = df.head(100)

            time_series_key = f"Time Series FX (Daily)"
            return {
                "Meta Data": {
                    "1. Information": "FX Daily Prices (Open, High, Low, Close)",
                    "2. From Symbol": from_symbol.upper(),
                    "3. To Symbol": to_symbol.upper(),
                    "4. Output Size": outputsize,
                    "5. Last Refreshed": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), # Data fetched now
                    "6. Time Zone": "UTC" # FX market data is often UTC referenced
                },
                time_series_key: self._format_history_data(df.sort_index(ascending=True), interval_is_daily=True, is_fx=True)
            }
        except Exception as e:
            print(f"Error fetching daily FX rates for {yf_symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve daily FX rates for {yf_symbol}: {str(e)}"}

    ## Technical Indicator Methods (Not directly provided by yfinance, require calculation) ##
    async def get_sma(self, symbol: str, interval: str = 'daily', time_period: int = 20, series_type: str = 'close'):
        return {"Note": "SMA calculation needs to be implemented separately using historical data from yfinance."}
    async def get_ema(self, symbol: str, interval: str = 'daily', time_period: int = 20, series_type: str = 'close'):
        return {"Note": "EMA calculation needs to be implemented separately using historical data from yfinance."}

    ## Economic Indicator Methods (Not primary yfinance features) ##
    async def get_real_gdp(self, interval: str = 'quarterly'):
        return {"Note": "Real GDP data is not directly available via yfinance. Check sources like FRED."}
    async def get_cpi(self, interval: str = 'monthly'):
        return {"Note": "CPI data is not directly available via yfinance. Check sources like FRED."}
    async def get_inflation(self):
        return {"Note": "Inflation data is not directly available via yfinance. Check sources like FRED."}

    async def get_treasury_yield(self, interval: str = 'daily', maturity: str = '10year'):
        # AlphaVantage maturities: '3month', '2year', '5year', '7year', '10year', '30year'.
        # yfinance treasury symbols:
        maturity_map_yf = {
            '3month': '^IRX',  # 13 Week Treasury Bill
            '2year': '^UST2Y', # US 2 Year Treasury Yield (less common, might need to check specific ticker for data)
            '5year': '^FVX',   # ICE BofA US 5-Year Treasury Index
            '7year': None,     # No direct common yf symbol, might need specific CUSIP/bond ticker
            '10year': '^TNX',  # CBOE Interest Rate 10 Year T Note
            '30year': '^TYX'   # CBOE Interest Rate 30 Year T Bond
        }
        yf_treasury_symbol = maturity_map_yf.get(maturity)

        if not yf_treasury_symbol:
            return {"Error Message": f"Treasury yield for maturity '{maturity}' does not have a direct common yfinance symbol or is not supported."}
        
        yf_hist_interval_map = {'daily': '1d', 'weekly': '1wk', 'monthly': '1mo'}
        yf_hist_interval = yf_hist_interval_map.get(interval, '1d')

        try:
            ticker = yf.Ticker(yf_treasury_symbol)
            df = await self._run_sync(ticker.history, period="5y", interval=yf_hist_interval, auto_adjust=False) # Fetch e.g. 5 years of data
            if df.empty:
                return {"Error Message": f"No data found for Treasury Yield {maturity} ({yf_treasury_symbol})."}

            df = df.sort_index(ascending=False) # Latest first
            data_points = []
            for index_date, row in df.iterrows():
                date_key = index_date.strftime("%Y-%m-%d")
                # Yield is typically the 'Close' price for these ^ tickers
                data_points.append({"date": date_key, "value": str(row.get('Close', 'N/A'))}) 

            return {
                "name": f"Treasury Yield {maturity} ({yf_treasury_symbol})",
                "interval": interval,
                "unit": "percent",
                "data": data_points
            }
        except Exception as e:
            print(f"Error fetching Treasury Yield for {maturity} ({yf_treasury_symbol}) from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve Treasury Yield for {maturity}: {str(e)}"}

    async def get_price_change_24h(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the price change for a symbol over the last 24 hours (approximately).
        Symbol can be for stocks (e.g., "AAPL"), crypto (e.g., "BTC-USD"), or FX (e.g., "EURUSD=X").
        """
        try:
            ticker = yf.Ticker(symbol)
            # Fetch data for the last 2 days. Interval '1h' provides good granularity.
            # For some assets, might need to try other intervals like '30m' or '15m' if '1h' is sparse.
            hist_df = await self._run_sync(ticker.history, period="2d", interval="1h", auto_adjust=False, prepost=True)

            if hist_df.empty or len(hist_df) < 2:
                # Fallback to a more granular interval or different period if 1h failed or is too sparse
                hist_df = await self._run_sync(ticker.history, period="2d", interval="15m", auto_adjust=False, prepost=True)
                if hist_df.empty or len(hist_df) < 2:
                    hist_df = await self._run_sync(ticker.history, period="2d", interval="1d", auto_adjust=False) # last resort daily
                    if hist_df.empty or len(hist_df) < 2:
                        return {"Error Message": f"Not enough historical data for {symbol} in the last 2 days to calculate 24h change accurately."}
            
            hist_df = hist_df.sort_index() # Ensure data is sorted by time ascending

            # Ensure index is timezone-aware (UTC for comparison)
            if hist_df.index.tz is None:
                hist_df.index = hist_df.index.tz_localize('UTC') # Assume UTC if naive, or market's tz if known
            else:
                hist_df.index = hist_df.index.tz_convert('UTC')

            latest_data_point = hist_df.iloc[-1]
            latest_price = latest_data_point['Close']
            latest_timestamp_utc = latest_data_point.name # pd.Timestamp in UTC

            # Target timestamp for 24 hours ago from the latest data point's timestamp
            target_timestamp_24h_ago_utc = latest_timestamp_utc - timedelta(hours=24)
            
            # Find the closest available data point to 24 hours ago using 'asof'
            price_24h_ago_series = hist_df['Close'].asof(target_timestamp_24h_ago_utc)

            if pd.isna(price_24h_ago_series):
                # If no exact or earlier match, use the earliest point in our fetched window as a rough proxy
                price_24h_ago = hist_df['Close'].iloc[0]
                timestamp_of_price_24h_ago_utc = hist_df.index[0]
                note = "Used earliest available price in the fetched window as 24h ago reference due to sparse data."
            else:
                price_24h_ago = price_24h_ago_series
                # Get the actual timestamp of the data point selected by 'asof'
                idx_loc = hist_df.index.get_indexer([target_timestamp_24h_ago_utc], method='ffill')[0] # 'ffill' finds prior
                timestamp_of_price_24h_ago_utc = hist_df.index[idx_loc]
                note = None

            if pd.isna(latest_price) or pd.isna(price_24h_ago):
                 return {"Error Message": f"Could not determine valid current or 24h ago price for {symbol}."}

            change_amount = latest_price - price_24h_ago
            change_percent = (change_amount / price_24h_ago) * 100 if price_24h_ago != 0 else float('inf') if change_amount > 0 else 0

            response = {
                "symbol": symbol.upper(),
                "current_price": float(latest_price),
                "price_24h_ago": float(price_24h_ago),
                "change_amount": float(change_amount),
                "change_percent": float(change_percent),
                "latest_price_timestamp_utc": latest_timestamp_utc.strftime('%Y-%m-%d %H:%M:%S %Z'),
                "reference_price_24h_ago_timestamp_utc": timestamp_of_price_24h_ago_utc.strftime('%Y-%m-%d %H:%M:%S %Z'),
            }
            if note:
                response["note"] = note
            return response

        except Exception as e:
            print(f"Error calculating 24h price change for {symbol} using yfinance: {e}")
            # import traceback; traceback.print_exc() # For dev debugging
            return {"Error Message": f"An error occurred calculating 24h price change for {symbol}: {str(e)}"}

financial_data_service = FinancialDataService()