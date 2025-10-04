from datetime import datetime, timedelta
import time
import pandas as pd
import yfinance as yf
import asyncio
from typing import Dict, List, Optional, Any
import traceback

from app.core.config import settings
from app.services.web_search_service import web_search_service

class FinancialDataService:
    def __init__(self):
        pass

    async def _run_sync(self, func, *args, **kwargs):
        """Runs a synchronous function in a separate thread to avoid blocking.

        This is a helper to use the synchronous yfinance library in an async
        application.

        Args:
            func: The synchronous function to run.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            The result of the synchronous function call.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _format_history_data(self, df_history: pd.DataFrame, interval_is_daily=False, is_fx=False, is_crypto=False, symbol_meta: Optional[str] = None):
        """Formats a pandas DataFrame from yfinance into a dictionary.

        This function reshapes the historical data DataFrame into a structure
        similar to the Alpha Vantage API's time series format.

        Args:
            df_history (pd.DataFrame): The DataFrame containing historical price data.
            interval_is_daily (bool): Flag if the data interval is daily.
            is_fx (bool): Flag if the data is for a foreign exchange pair.
            is_crypto (bool): Flag if the data is for a cryptocurrency.
            symbol_meta (Optional[str]): Additional metadata about the symbol.

        Returns:
            Dict[str, Dict]: A dictionary where keys are dates and values are
                             dictionaries of OHLCV data.
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
                entry['5. adjusted close'] = str(row.get('Adj Close', row.get('Close', 'N/A')))
                entry['7. dividend amount'] = str(row.get('Dividends', '0.0'))
                entry['8. split coefficient'] = str(row.get('Stock Splits', '0.0'))
            
            if is_crypto and interval_is_daily:
                market_in_symbol = symbol_meta.split('-')[-1] if symbol_meta else settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT.upper()
                entry[f'1a. open ({market_in_symbol})'] = str(row.get('Open', 'N/A'))
                entry[f'2a. high ({market_in_symbol})'] = str(row.get('High', 'N/A'))
                entry[f'3a. low ({market_in_symbol})'] = str(row.get('Low', 'N/A'))
                entry[f'4a. close ({market_in_symbol})'] = str(row.get('Close', 'N/A'))
                entry[f'5. volume'] = str(row.get('Volume', 'N/A'))
                entry[f'6. market cap ({market_in_symbol})'] = "N/A"

            formatted_data[date_key] = entry
        return formatted_data


    async def get_stock_quote(self, symbol: str) -> Optional[Dict[str, str]]:
        """Fetches a real-time quote for a stock.

        Tries to get live market data from the ticker's info. If that's not
        available, it falls back to the most recent historical data.

        Args:
            symbol (str): The stock symbol (e.g., "AAPL").

        Returns:
            Optional[Dict[str, str]]: A dictionary containing quote data,
                                      or an error message.
        """
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
            else:
                hist = await self._run_sync(ticker.history, period="2d", interval="1d")
                if not hist.empty:
                    latest = hist.iloc[-1]
                    prev_close_val = hist.iloc[-2]['Close'] if len(hist) > 1 else latest['Open']
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
        """Fetches daily time series data, adjusted for splits and dividends.

        Args:
            symbol (str): The stock symbol.
            outputsize (str): 'compact' for the last 100 data points,
                              'full' for the entire history.

        Returns:
            Dict: A dictionary containing metadata and the daily time series data.
        """
        try:
            ticker = yf.Ticker(symbol)
            period = "max" 
            
            df = await self._run_sync(ticker.history, period=period, interval="1d", actions=True, auto_adjust=False)
            if df.empty:
                return {"Error Message": f"No daily data found for symbol {symbol}."}
            
            if 'Adj Close' not in df.columns:
                df['Adj Close'] = df['Close'] 

            df = df.sort_index(ascending=False)
            if outputsize == 'compact':
                df = df.head(100)

            return {
                "Meta Data": {
                    "1. Information": "Daily Time Series with Splits and Dividend Events",
                    "2. Symbol": symbol.upper(),
                    "3. Output Size": outputsize,
                    "4. Time Zone": str(df.index.tz) if df.index.tz else "UTC"
                },
                "Time Series (Daily)": self._format_history_data(df.sort_index(ascending=True), interval_is_daily=True) 
            }
        except Exception as e:
            print(f"Error fetching daily adjusted stock data for {symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve daily adjusted stock data for {symbol}: {str(e)}"}

    async def get_intraday_stock_data(self, symbol: str, interval: str = '5min', outputsize: str = 'compact'):
        """Fetches intraday time series data for a stock.

        Args:
            symbol (str): The stock symbol.
            interval (str): The time interval between data points.
                            Supported: '1min', '5min', '15min', '30min', '60min'.
            outputsize (str): 'compact' for recent data, 'full' for extended data.

        Returns:
            Dict: A dictionary containing metadata and the intraday time series.
        """
        yf_interval_map = {
            '1min': '1m', '5min': '5m', '15min': '15m', '30min': '30m', '60min': '1h'
        }
        yf_interval = yf_interval_map.get(interval, '5m')

    
        period = "2d" 
        if outputsize == 'full':
            if yf_interval == '1m': period = "7d"
            else: period = "59d" 

        try:
            ticker = yf.Ticker(symbol)
            df = await self._run_sync(ticker.history, period=period, interval=yf_interval, actions=False, auto_adjust=False)
            if df.empty:
                return {"Error Message": f"No intraday data found for {symbol} with interval {interval}."}

            df = df.sort_index(ascending=False)

            time_series_key = f"Time Series ({interval})"
            return {
                 "Meta Data": {
                    "1. Information": f"Intraday ({interval}) Time Series",
                    "2. Symbol": symbol.upper(),
                    "3. Output Size": outputsize,
                    "4. Interval": interval,
                    "5. Time Zone": str(df.index.tz) if df.index.tz else "N/A (likely market local time)"
                },
                time_series_key: self._format_history_data(df.sort_index(ascending=True))
            }
        except Exception as e:
            print(f"Error fetching intraday stock data for {symbol} ({interval}): {e}")
            return {"Error Message": f"Failed to retrieve intraday data for {symbol} ({interval}): {str(e)}"}

    async def get_company_overview(self, symbol: str):
        """Retrieves comprehensive overview and key metrics for a company.

        Args:
            symbol (str): The stock symbol.

        Returns:
            Dict: A dictionary containing company information and financial ratios.
        """
        try:
            ticker = yf.Ticker(symbol)
            info = await self._run_sync(lambda: ticker.info)
            if not info or info.get('quoteType') == 'NONE' or not info.get('longName'):
                 return {"Error Message": f"No company overview data found for symbol {symbol}. It may be invalid or not a stock."}

            overview = {
                "Symbol": info.get('symbol', symbol.upper()),
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
                "FiscalYearEnd": info.get('fiscalYearEnd'),
                "LatestQuarter": info.get('mostRecentQuarter'),
                "MarketCapitalization": str(info.get('marketCap')),
                "EBITDA": str(info.get('ebitda')),
                "PERatio": str(info.get('trailingPE', info.get('forwardPE'))),
                "PEGRatio": str(info.get('pegRatio')),
                "BookValue": str(info.get('bookValue')),
                "DividendPerShare": str(info.get('dividendRate', info.get('trailingAnnualDividendRate'))),
                "DividendYield": str(info.get('dividendYield', info.get('trailingAnnualDividendYield'))),
                "EPS": str(info.get('trailingEps', info.get('forwardEps'))),
                "RevenuePerShareTTM": str(info.get('revenuePerShare')),
                "ProfitMargin": str(info.get('profitMargins')),
                "OperatingMarginTTM": str(info.get('operatingMargins')),
                "ReturnOnAssetsTTM": str(info.get('returnOnAssets')),
                "ReturnOnEquityTTM": str(info.get('returnOnEquity')),
                "RevenueTTM": str(info.get('totalRevenue')),
                "GrossProfitTTM": str(info.get('grossProfits')),
                "DilutedEPSTTM": str(info.get('trailingEps')),
                "QuarterlyEarningsGrowthYOY": str(info.get('earningsQuarterlyGrowth')),
                "QuarterlyRevenueGrowthYOY": str(info.get('revenueGrowth')),
                "AnalystTargetPrice": str(info.get('targetMeanPrice')),
                "Beta": str(info.get('beta')),
                "52WeekHigh": str(info.get('fiftyTwoWeekHigh')),
                "52WeekLow": str(info.get('fiftyTwoWeekLow')),
                "50DayMovingAverage": str(info.get('fiftyDayAverage')),
                "200DayMovingAverage": str(info.get('twoHundredDayAverage')),
                "SharesOutstanding": str(info.get('sharesOutstanding')),
                "DividendDate": info.get('exDividendDate'),
                "PriceToSalesRatioTTM": str(info.get('priceToSalesTrailing12Months')),
                "PriceToBookRatio": str(info.get('priceToBook')),
            }

            for key in ["FiscalYearEnd", "LatestQuarter", "DividendDate"]:
                if overview.get(key) and isinstance(overview[key], (int, float)):
                    try:
                        overview[key] = datetime.fromtimestamp(overview[key]).strftime('%Y-%m-%d')
                    except:
                        overview[key] = str(overview[key])
            return overview
        except Exception as e:
            print(f"Error fetching company overview for {symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve company overview for {symbol}: {str(e)}"}

    async def get_daily_series(self, symbol: str, outputsize: str = "compact"):
        """Fetches daily unadjusted OHLCV data.

        Args:
            symbol (str): The stock symbol.
            outputsize (str): 'compact' for the last 100 data points,
                              'full' for the entire history.

        Returns:
            Dict: A dictionary of daily OHLCV data.
        """
        try:
            ticker = yf.Ticker(symbol)
            period = "max"
            df = await self._run_sync(ticker.history, period=period, interval="1d", auto_adjust=False, actions=False)
            if df.empty:
                return {}
            
            df = df.sort_index(ascending=False)
            if outputsize == 'compact':
                df = df.head(100)
            
            return self._format_history_data(df.sort_index(ascending=True), interval_is_daily=True)
        except Exception as e:
            print(f"Error fetching daily series for {symbol} from yfinance: {e}")
            return {}

    def _format_financial_statement(self, df_statement: pd.DataFrame, report_type: str):
        """Formats a financial statement DataFrame into a list of reports.

        Args:
            df_statement (pd.DataFrame): DataFrame containing financial data.
            report_type (str): The type of report (e.g., "Income Statement").

        Returns:
            List[Dict]: A list of dictionaries, each representing a
                        periodic report.
        """
        reports = []
        if df_statement.empty:
            return reports
        
        df_transposed = df_statement.transpose()

        for date_col, row_data in df_transposed.iterrows():
            report_data_dict = {item: str(value) if pd.notna(value) else "N/A" for item, value in row_data.items()}
            reports.append({
                "fiscalDateEnding": date_col.strftime('%Y-%m-%d') if isinstance(date_col, pd.Timestamp) else str(date_col),
                "reportedCurrency": "N/A (typically USD for US companies, check source for specifics)",
                **report_data_dict
            })
        return reports


    async def get_income_statement(self, symbol: str):
        """Fetches annual and quarterly income statements for a company.

        Args:
            symbol (str): The stock symbol.

        Returns:
            Dict: A dictionary with the symbol and lists of annual and
                  quarterly reports.
        """
        try:
            ticker = yf.Ticker(symbol)
            annual_is = await self._run_sync(lambda: ticker.income_stmt)
            quarterly_is = await self._run_sync(lambda: ticker.quarterly_income_stmt)
            
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

    async def get_balance_sheet(self, symbol: str):
        """Fetches annual and quarterly balance sheets for a company.

        Args:
            symbol (str): The stock symbol.

        Returns:
            Dict: A dictionary with the symbol and lists of annual and
                  quarterly reports.
        """
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
        """Fetches annual and quarterly cash flow statements for a company.

        Args:
            symbol (str): The stock symbol.

        Returns:
            Dict: A dictionary with the symbol and lists of annual and
                  quarterly reports.
        """
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
        """Fetches historical annual and quarterly earnings data.

        This data is extracted from the income statements.

        Args:
            symbol (str): The stock symbol.

        Returns:
            Dict: A dictionary containing annual and quarterly earnings reports.
        """
        try:
            ticker = yf.Ticker(symbol)
            
            annual_is_df = await self._run_sync(lambda: ticker.income_stmt)
            quarterly_is_df = await self._run_sync(lambda: ticker.quarterly_income_stmt)

            annual_reports = []
            if annual_is_df is not None and not annual_is_df.empty:
                for report_date_col, report_data in annual_is_df.transpose().iterrows():
                    fiscal_date_str = report_date_col.strftime('%Y-%m-%d') if isinstance(report_date_col, pd.Timestamp) else str(report_date_col)
                    
                    reported_eps = report_data.get('Diluted EPS', report_data.get('Basic EPS', 'N/A'))
                    net_income = report_data.get('Net Income', report_data.get('Net Income Common Stockholders', 'N/A'))
                    revenue = report_data.get('Total Revenue', report_data.get('Operating Revenue', 'N/A'))

                    annual_reports.append({
                        "fiscalDateEnding": fiscal_date_str,
                        "reportedEPS": str(reported_eps), 
                        "netIncome": str(net_income),
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

                    quarterly_reports.append({
                        "fiscalDateEnding": fiscal_date_str,
                        "reportedEPS": str(reported_eps),
                        "netIncome": str(net_income),
                        "reportedRevenue": str(revenue)
                    })
            else:
                print(f"Warning: Quarterly income statement for {symbol} (for earnings extraction) is None or empty.")

            if not annual_reports and not quarterly_reports:
                print(f"Warning: No earnings data could be extracted from income statements for {symbol}.")

            return {
                "symbol": symbol.upper(),
                "annualEarnings": sorted(annual_reports, key=lambda x: x['fiscalDateEnding'], reverse=True),
                "quarterlyEarnings": sorted(quarterly_reports, key=lambda x: x['fiscalDateEnding'], reverse=True)
            } 
        except Exception as e:
            print(f"Error processing earnings from income statements for {symbol} from yfinance: {e}")
            traceback.print_exc()
            return {"Error Message": f"Failed to retrieve/process earnings data for {symbol}: {str(e)}"}
        
    async def get_latest_news_for_stock_web(self, symbol: str, limit: int = 5):
        """Uses a general web search to find the latest news for a stock.

        Args:
            symbol (str): The stock symbol.
            limit (int): The maximum number of news articles to return.

        Returns:
            str: A formatted string containing the news, or a 'not found' message.
        """
        news_query = f"latest financial news for {symbol} stock"
        news_context = await web_search_service.get_search_context(
            news_query, max_results=limit,
            include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", "finance.yahoo.com"]
        )
        return news_context if news_context and "No relevant information" not in news_context else f"No specific news found via web search for {symbol}."

    async def get_alpha_vantage_news_sentiment(self, tickers: str = None, topics: str = None, time_from: str = None, time_to: str = None, sort: str = "LATEST", limit: int = 50):
        """Fetches news articles for a given ticker from yfinance.

        Note: The name is based on the Alpha Vantage API but the source is yfinance.
        Sentiment data is not provided.

        Args:
            tickers (str): A comma-separated list of stock symbols. Only the first
                           is used.
            limit (int): The maximum number of news articles to return.

        Returns:
            Dict: A dictionary containing a list of news articles (feed).
        """
        if not tickers:
            return {"Error Message": "Ticker symbol must be provided."}

        symbol = tickers.split(',')[0].strip().upper()

        try:
            ticker = yf.Ticker(symbol)
            raw_news_list = await self._run_sync(lambda: ticker.news) 

            if not raw_news_list:
                return {"items": "0", "feed": [], "Note": f"No news found for {symbol} via yfinance."}

            feed_items = []
            for raw_item in raw_news_list[:limit]:
                content_data = raw_item.get('content', {})

                title = content_data.get('title')
                
                canonical_url_data = content_data.get('canonicalUrl', {})
                url = canonical_url_data.get('url')

                provider_data = content_data.get('provider', {})
                publisher_name = provider_data.get('displayName')
                
                summary = content_data.get('summary', title)

                thumbnail_data = content_data.get('thumbnail', {})
                banner_image_url = None
                if thumbnail_data:
                    resolutions = thumbnail_data.get('resolutions', [])
                    if resolutions:
                        original_res = next((res for res in resolutions if res.get('tag') == 'original'), None)
                        if original_res:
                            banner_image_url = original_res.get('url')
                        elif resolutions:
                            banner_image_url = resolutions[0].get('url')
                    else:
                        banner_image_url = thumbnail_data.get('originalUrl')

                publish_time_str = "N/A"
                pub_date_raw = content_data.get('pubDate')
                
                if pub_date_raw:
                    try:
                        dt_obj = datetime.fromisoformat(pub_date_raw.replace('Z', '+00:00'))
                        publish_time_str = dt_obj.strftime('%Y%m%dT%H%M%S')
                    except ValueError:
                        publish_time_str = str(pub_date_raw)
                elif 'providerPublishTime' in raw_item and raw_item['providerPublishTime']:
                    try:
                        publish_time_str = datetime.fromtimestamp(int(raw_item['providerPublishTime'])).strftime('%Y%m%dT%H%M%S')
                    except Exception:
                        publish_time_str = str(raw_item['providerPublishTime'])

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
                    "authors": [publisher_name] if publisher_name else ['N/A'],
                    "summary": summary,
                    "banner_image": banner_image_url,
                    "source": publisher_name or "N/A",
                    "category_within_source": "N/A",
                    "source_domain": source_domain,
                    "topics": [],
                    "overall_sentiment_score": "N/A",
                    "overall_sentiment_label": "N/A",
                    "ticker_sentiment": [{"ticker": symbol, "relevance_score": "N/A", "ticker_sentiment_score": "N/A", "ticker_sentiment_label": "N/A"}]
                })
            
            return {
                "items": str(len(feed_items)),
                "feed": feed_items
            }
        except Exception as e:
            print(f"Error fetching yfinance news for ticker {symbol}: {e}")
            traceback.print_exc()
            return {"Error Message": f"Failed to retrieve news for {symbol}: {str(e)}"}

    async def get_crypto_exchange_rate(self, from_currency_symbol: str, to_currency_symbol: str = None):
        """Fetches the current exchange rate for a cryptocurrency pair.

        Args:
            from_currency_symbol (str): The base cryptocurrency symbol (e.g., "BTC").
            to_currency_symbol (str): The quote currency symbol (e.g., "USD").
                                      Defaults to a configured value.

        Returns:
            Dict: A dictionary containing the real-time exchange rate info.
        """
        effective_to_currency = to_currency_symbol or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT
        yf_symbol = f"{from_currency_symbol.upper()}-{effective_to_currency.upper()}"

        try:
            ticker = yf.Ticker(yf_symbol)
            info = await self._run_sync(lambda: ticker.info)
            if info and info.get('regularMarketPrice'):
                 last_refreshed_ts = info.get('regularMarketTime')
                 last_refreshed_str = datetime.fromtimestamp(last_refreshed_ts).strftime('%Y-%m-%d %H:%M:%S %Z') if last_refreshed_ts else "N/A"
                 return {
                    "Realtime Currency Exchange Rate": {
                        "1. From_Currency Code": from_currency_symbol.upper(),
                        "2. From_Currency Name": info.get('fromCurrency', from_currency_symbol.upper()),
                        "3. To_Currency Code": effective_to_currency.upper(),
                        "4. To_Currency Name": info.get('toCurrency', effective_to_currency.upper()),
                        "5. Exchange Rate": str(info.get('regularMarketPrice')),
                        "6. Last Refreshed": last_refreshed_str,
                        "7. Time Zone": "UTC",
                        "8. Bid Price": str(info.get('bid', 'N/A')),
                        "9. Ask Price": str(info.get('ask', 'N/A')),
                    }
                 }
            
            df_hist = await self._run_sync(ticker.history, period="2d", interval="1m")
            if df_hist.empty:
                df_hist = await self._run_sync(ticker.history, period="2d", interval="5m")
            
            if df_hist.empty:
                return {"Error Message": f"No recent history found for crypto {yf_symbol} on yfinance to determine exchange rate."}

            latest_data = df_hist.iloc[-1]
            return {
                "from_currency": from_currency_symbol.upper(),
                "to_currency": effective_to_currency.upper(),
                "exchange_rate": str(latest_data.get('Close', 'N/A')),
                "last_refreshed": latest_data.name.strftime('%Y-%m-%d %H:%M:%S %Z') if latest_data.name and hasattr(latest_data.name, 'strftime') else "N/A",
                "bid_price": "N/A",
                "ask_price": "N/A",
                "Note": "Data from recent history, not live quote."
            }
        except Exception as e:
            print(f"Error fetching crypto exchange rate for {yf_symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve exchange rate for {yf_symbol}: {str(e)}"}

    async def get_daily_crypto_data(self, symbol: str, market: str):
        """Fetches daily time series data for a cryptocurrency.

        Args:
            symbol (str): The cryptocurrency symbol (e.g., "BTC").
            market (str): The market/quote currency (e.g., "USD").

        Returns:
            Dict: A dictionary containing metadata and daily crypto data.
        """
        yf_symbol = f"{symbol.upper()}-{market.upper()}"
        try:
            ticker = yf.Ticker(yf_symbol)
            df = await self._run_sync(ticker.history, period="max", interval="1d", auto_adjust=False)
            if df.empty:
                return {"Error Message": f"No daily crypto data found for {yf_symbol}."}

            df = df.sort_index(ascending=False)

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
                    "5. Market Name": market.upper(),
                    "6. Last Refreshed": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "7. Time Zone": "UTC"
                },
                time_series_key: self._format_history_data(df.sort_index(ascending=True), interval_is_daily=True, is_crypto=True, symbol_meta=yf_symbol)
            }
        except Exception as e:
            print(f"Error fetching daily crypto data for {yf_symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve daily crypto data for {yf_symbol}: {str(e)}"}
            
    async def get_crypto_rating(self, symbol: str):
        """Placeholder for crypto rating. Not supported by yfinance.

        Args:
            symbol (str): The crypto symbol.

        Returns:
            Dict: A note indicating the feature is not available.
        """
        print(f"Function 'get_crypto_rating' for {symbol} is not supported by yfinance.")
        return {"Note": f"Crypto ratings (FCAS) are not available through yfinance for {symbol}."}

    async def get_daily_fx_rates(self, from_symbol: str, to_symbol: str, outputsize: str = 'compact'):
        """Fetches daily time series for a foreign exchange pair.

        Args:
            from_symbol (str): The base currency symbol (e.g., "EUR").
            to_symbol (str): The quote currency symbol (e.g., "USD").
            outputsize (str): 'compact' for last 100 points, 'full' for all data.

        Returns:
            Dict: A dictionary with metadata and daily FX time series.
        """
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
                    "5. Last Refreshed": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "6. Time Zone": "UTC"
                },
                time_series_key: self._format_history_data(df.sort_index(ascending=True), interval_is_daily=True, is_fx=True)
            }
        except Exception as e:
            print(f"Error fetching daily FX rates for {yf_symbol} from yfinance: {e}")
            return {"Error Message": f"Failed to retrieve daily FX rates for {yf_symbol}: {str(e)}"}

    async def get_sma(self, symbol: str, interval: str = 'daily', time_period: int = 20, series_type: str = 'close'):
        """Placeholder for SMA calculation. Not implemented.

        Returns:
            Dict: A note indicating the feature needs to be implemented.
        """
        return {"Note": "SMA calculation needs to be implemented separately using historical data from yfinance."}

    async def get_ema(self, symbol: str, interval: str = 'daily', time_period: int = 20, series_type: str = 'close'):
        """Placeholder for EMA calculation. Not implemented.

        Returns:
            Dict: A note indicating the feature needs to be implemented.
        """
        return {"Note": "EMA calculation needs to be implemented separately using historical data from yfinance."}

    async def get_real_gdp(self, interval: str = 'quarterly'):
        """Placeholder for Real GDP data. Not provided by yfinance.

        Returns:
            Dict: A note indicating an alternative data source should be used.
        """
        return {"Note": "Real GDP data is not directly available via yfinance. Check sources like FRED."}

    async def get_cpi(self, interval: str = 'monthly'):
        """Placeholder for CPI data. Not provided by yfinance.

        Returns:
            Dict: A note indicating an alternative data source should be used.
        """
        return {"Note": "CPI data is not directly available via yfinance. Check sources like FRED."}

    async def get_inflation(self):
        """Placeholder for inflation data. Not provided by yfinance.

        Returns:
            Dict: A note indicating an alternative data source should be used.
        """
        return {"Note": "Inflation data is not directly available via yfinance. Check sources like FRED."}

    async def get_treasury_yield(self, interval: str = 'daily', maturity: str = '10year'):
        """Fetches historical data for a specific US Treasury yield.

        Args:
            interval (str): The data interval ('daily', 'weekly', 'monthly').
            maturity (str): The treasury maturity ('3month', '2year', '5year',
                            '7year', '10year', '30year').

        Returns:
            Dict: A dictionary containing a list of treasury yield data points.
        """
        maturity_map_yf = {
            '3month': '^IRX',
            '2year': '^UST2Y',
            '5year': '^FVX',
            '7year': None,
            '10year': '^TNX',
            '30year': '^TYX'
        }
        yf_treasury_symbol = maturity_map_yf.get(maturity)

        if not yf_treasury_symbol:
            return {"Error Message": f"Treasury yield for maturity '{maturity}' does not have a direct common yfinance symbol or is not supported."}
        
        yf_hist_interval_map = {'daily': '1d', 'weekly': '1wk', 'monthly': '1mo'}
        yf_hist_interval = yf_hist_interval_map.get(interval, '1d')

        try:
            ticker = yf.Ticker(yf_treasury_symbol)
            df = await self._run_sync(ticker.history, period="5y", interval=yf_hist_interval, auto_adjust=False)
            if df.empty:
                return {"Error Message": f"No data found for Treasury Yield {maturity} ({yf_treasury_symbol})."}

            df = df.sort_index(ascending=False)
            data_points = []
            for index_date, row in df.iterrows():
                date_key = index_date.strftime("%Y-%m-%d")
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
        """Calculates the price change for a symbol over the last 24 hours.

        This method fetches recent historical data and finds the closest data
        point to 24 hours ago to compute the change. It works for stocks,
        crypto, and FX pairs.

        Args:
            symbol (str): The asset symbol (e.g., "AAPL", "BTC-USD", "EURUSD=X").

        Returns:
            Optional[Dict[str, Any]]: A dictionary with the price change details
                                      or an error message.
        """
        try:
            ticker = yf.Ticker(symbol)
            hist_df = await self._run_sync(ticker.history, period="2d", interval="1h", auto_adjust=False, prepost=True)

            if hist_df.empty or len(hist_df) < 2:
                hist_df = await self._run_sync(ticker.history, period="2d", interval="15m", auto_adjust=False, prepost=True)
                if hist_df.empty or len(hist_df) < 2:
                    hist_df = await self._run_sync(ticker.history, period="2d", interval="1d", auto_adjust=False)
                    if hist_df.empty or len(hist_df) < 2:
                        return {"Error Message": f"Not enough historical data for {symbol} in the last 2 days to calculate 24h change accurately."}
            
            hist_df = hist_df.sort_index()

            if hist_df.index.tz is None:
                hist_df.index = hist_df.index.tz_localize('UTC')
            else:
                hist_df.index = hist_df.index.tz_convert('UTC')

            latest_data_point = hist_df.iloc[-1]
            latest_price = latest_data_point['Close']
            latest_timestamp_utc = latest_data_point.name

            target_timestamp_24h_ago_utc = latest_timestamp_utc - timedelta(hours=24)
            
            price_24h_ago_series = hist_df['Close'].asof(target_timestamp_24h_ago_utc)

            if pd.isna(price_24h_ago_series):
                price_24h_ago = hist_df['Close'].iloc[0]
                timestamp_of_price_24h_ago_utc = hist_df.index[0]
                note = "Used earliest available price in the fetched window as 24h ago reference due to sparse data."
            else:
                price_24h_ago = price_24h_ago_series
                idx_loc = hist_df.index.get_indexer([target_timestamp_24h_ago_utc], method='ffill')[0]
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
            return {"Error Message": f"An error occurred calculating 24h price change for {symbol}: {str(e)}"}

financial_data_service = FinancialDataService()
