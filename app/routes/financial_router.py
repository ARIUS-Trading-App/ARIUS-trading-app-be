from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import Optional, Literal
from app.services.financial_data_service import financial_data_service as financial_service
from app.core.config import settings
from app.schemas.portfolio import PriceChange24hResponse

router = APIRouter(
    prefix="/financials",
    tags=["Financial Data"],
)

@router.get("/stock/{symbol}/quote", summary="Get Real-Time Stock Quote")
async def get_stock_quote_endpoint(symbol: str = Path(..., title="Stock Symbol", description="The stock ticker symbol (e.g., AAPL, MSFT)")):
    """Fetches a real-time quote for a given stock symbol.

    Args:
        symbol (str): The stock ticker symbol passed in the URL path.

    Returns:
        dict: A dictionary containing the latest quote data, including price,
              volume, and daily change.

    Raises:
        HTTPException: 404 if the quote for the symbol cannot be found.
    """
    data = await financial_service.get_stock_quote(symbol)
    if data and not ("Error Message" in data or "Information" in data or not data.get("01. symbol")):
        return data
    raise HTTPException(status_code=404, detail=f"Stock quote not found for symbol {symbol} or API error: {data}")

@router.get("/stock/{symbol}/history/daily-adjusted", summary="Get Daily Adjusted Stock Time Series")
async def get_daily_adjusted_stock_data_endpoint(
    symbol: str = Path(..., title="Stock Symbol", description="The stock ticker symbol"),
    outputsize: Literal['compact', 'full'] = Query('compact', description="Number of data points: 'compact' for 100, 'full' for full history.")
):
    """Fetches daily time series data for a stock, adjusted for splits and dividends.

    Args:
        symbol (str): The stock ticker symbol.
        outputsize (Literal['compact', 'full']): Specifies the size of the
            returned time series. 'compact' returns the latest 100 data points.

    Returns:
        dict: An object containing metadata and the time series data.
    
    Raises:
        HTTPException: 404 if data for the symbol cannot be found.
    """
    data = await financial_service.get_daily_adjusted_stock_data(symbol, outputsize)
    if data and "Time Series (Daily)" in data:
        return data
    raise HTTPException(status_code=404, detail=f"Daily adjusted stock data not found for {symbol} or API error: {data}")

@router.get("/stock/{symbol}/history/intraday", summary="Get Intraday Stock Time Series")
async def get_intraday_stock_data_endpoint(
    symbol: str = Path(..., title="Stock Symbol"),
    interval: Literal['1min', '5min', '15min', '30min', '60min'] = Query('5min', description="Time interval between data points."),
    outputsize: Literal['compact', 'full'] = Query('compact', description="Number of data points.")
):
    """Fetches intraday time series data for a stock.

    Args:
        symbol (str): The stock ticker symbol.
        interval (Literal): The time interval between data points.
        outputsize (Literal): 'compact' for recent data or 'full' for
            more extensive historical data.

    Returns:
        dict: An object containing metadata and the intraday time series data.

    Raises:
        HTTPException: 404 if data for the symbol and interval cannot be found.
    """
    key_name = f"Time Series ({interval})"
    data = await financial_service.get_intraday_stock_data(symbol, interval, outputsize)
    if data and key_name in data:
        return data
    raise HTTPException(status_code=404, detail=f"Intraday stock data not found for {symbol} with interval {interval} or API error: {data}")


@router.get("/stock/{symbol}/overview", summary="Get Company Overview")
async def get_company_overview_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """Fetches company information, financial ratios, and other key metrics for a stock.
    
    Args:
        symbol (str): The stock ticker symbol.
        
    Returns:
        dict: A dictionary containing comprehensive company overview data.
        
    Raises:
        HTTPException: 404 if an overview for the symbol cannot be found.
    """
    data = await financial_service.get_company_overview(symbol)
    if data:
        return data
    raise HTTPException(status_code=404, detail=f"Company overview not found for {symbol} or API error: {data}")

@router.get("/stock/{symbol}/financials/income-statement", summary="Get Income Statement")
async def get_income_statement_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """Fetches annual and quarterly income statements for a stock.
    
    Args:
        symbol (str): The stock ticker symbol.
        
    Returns:
        dict: An object containing annual and quarterly reports.
        
    Raises:
        HTTPException: 404 if the income statement cannot be found.
    """
    data = await financial_service.get_income_statement(symbol)
    if data and (data.get("symbol") == symbol.upper() or (isinstance(data, dict) and not data)):
        return data
    elif isinstance(data, list) and data:
        return data
    raise HTTPException(status_code=404, detail=f"Income statement not found for {symbol} or API error: {data}")

@router.get("/stock/{symbol}/financials/balance-sheet", summary="Get Balance Sheet")
async def get_balance_sheet_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """Fetches annual and quarterly balance sheets for a stock.
    
    Args:
        symbol (str): The stock ticker symbol.
        
    Returns:
        dict: An object containing annual and quarterly reports.
        
    Raises:
        HTTPException: 404 if the balance sheet cannot be found.
    """
    data = await financial_service.get_balance_sheet(symbol)
    if data and (data.get("symbol") == symbol.upper() or (isinstance(data, dict) and not data)):
        return data
    elif isinstance(data, list) and data:
        return data
    raise HTTPException(status_code=404, detail=f"Balance sheet not found for {symbol} or API error: {data}")

@router.get("/stock/{symbol}/financials/cash-flow", summary="Get Cash Flow Statement")
async def get_cash_flow_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """Fetches annual and quarterly cash flow statements for a stock.
    
    Args:
        symbol (str): The stock ticker symbol.
        
    Returns:
        dict: An object containing annual and quarterly reports.
        
    Raises:
        HTTPException: 404 if the cash flow statement cannot be found.
    """
    data = await financial_service.get_cash_flow(symbol)
    if data and (data.get("symbol") == symbol.upper() or (isinstance(data, dict) and not data)):
        return data
    elif isinstance(data, list) and data:
        return data
    raise HTTPException(status_code=404, detail=f"Cash flow statement not found for {symbol} or API error: {data}")

@router.get("/stock/{symbol}/financials/earnings", summary="Get Company Earnings (EPS)")
async def get_earnings_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """Fetches annual and quarterly earnings (EPS) for a stock.
    
    Args:
        symbol (str): The stock ticker symbol.
        
    Returns:
        dict: An object containing annual and quarterly earnings data.
        
    Raises:
        HTTPException: 404 if earnings data cannot be found.
    """
    data = await financial_service.get_earnings(symbol)
    if data and (data.get("symbol") == symbol.upper() or (isinstance(data, dict) and not data)):
        return data
    elif isinstance(data, list) and data:
        return data
    raise HTTPException(status_code=404, detail=f"Earnings data not found for {symbol} or API error: {data}")

@router.get("/news/web-search/{symbol}", summary="Get Latest Stock News (Web Search)")
async def get_latest_news_for_stock_web_endpoint(
    symbol: str = Path(..., title="Stock Symbol"),
    limit: int = Query(5, ge=1, le=20, description="Number of news articles to fetch.")
):
    """Fetches latest financial news for a stock symbol using a web search service.
    
    Args:
        symbol (str): The stock ticker symbol.
        limit (int): The maximum number of news articles to return.
        
    Returns:
        dict: A dictionary containing the news context.
        
    Raises:
        HTTPException: 404 if news cannot be fetched.
    """
    data = await financial_service.get_latest_news_for_stock_web(symbol, limit)
    if data and not data.get("error"):
        return data
    raise HTTPException(status_code=404, detail=data.get("message") or f"Could not fetch web news for {symbol}: {data}")

@router.get("/news/alpha-vantage", summary="Get Market News & Sentiment (Alpha Vantage)")
async def get_alpha_vantage_news_sentiment_endpoint(
    tickers: Optional[str] = Query(None, description="Comma-separated stock tickers (e.g., AAPL,MSFT)."),
    topics: Optional[str] = Query(None, description="Comma-separated topics (e.g., technology,ipo)."),
    time_from: Optional[str] = Query(None, description="Start time YYYYMMDDTHHMM (e.g., 20220410T0130)."),
    time_to: Optional[str] = Query(None, description="End time YYYYMMDDTHHMM."),
    sort: Literal["LATEST", "EARLIEST", "RELEVANCE"] = Query("LATEST", description="Sort order."),
    limit: int = Query(50, ge=1, le=200, description="Number of results (max 200 for free tier, 1000 for premium).")
):
    """Fetches market news and sentiment data. Provide either 'tickers' or 'topics'.
    
    Args:
        tickers (Optional[str]): Comma-separated stock symbols.
        topics (Optional[str]): Comma-separated topics of interest.
        time_from (Optional[str]): Start time for the search.
        time_to (Optional[str]): End time for the search.
        sort (Literal): The sorting order for the results.
        limit (int): The maximum number of results to return.
        
    Returns:
        dict: An object containing a feed of news articles.
        
    Raises:
        HTTPException: 400 if neither tickers nor topics are provided, or 404 on other errors.
    """
    if not tickers and not topics:
        raise HTTPException(status_code=400, detail="Either 'tickers' or 'topics' query parameter must be provided.")
    data = await financial_service.get_alpha_vantage_news_sentiment(tickers, topics, time_from, time_to, sort, limit)
    if data and "feed" in data:
        return data
    elif data and "Information" in data:
        return {"message": data["Information"]}
    elif data and "Error Message" in data:
         raise HTTPException(status_code=400, detail=f"API Error: {data['Error Message']}")
    raise HTTPException(status_code=404, detail=f"News & sentiment data not found or API error: {data}")


@router.get("/crypto/{from_currency_symbol}/exchange-rate", summary="Get Cryptocurrency Exchange Rate")
async def get_crypto_exchange_rate_endpoint(
    from_currency_symbol: str = Path(..., title="From Cryptocurrency Symbol", description="e.g., BTC, ETH"),
    to_currency_symbol: Optional[str] = Query(None, title="To Currency Symbol", description="e.g., USD, EUR. Defaults to system default (USD).")
):
    """Fetches the real-time exchange rate for a cryptocurrency pair.
    
    Args:
        from_currency_symbol (str): The base cryptocurrency symbol (e.g., BTC).
        to_currency_symbol (Optional[str]): The quote currency symbol (e.g., USD).
        
    Returns:
        dict: An object containing the exchange rate information.
        
    Raises:
        HTTPException: 404 if the exchange rate cannot be found.
    """
    data = await financial_service.get_crypto_exchange_rate(from_currency_symbol, to_currency_symbol)
    if data and data.get("exchange_rate"):
        return data
    elif data and data.get("message"):
        raise HTTPException(status_code=404, detail=data["message"])
    raise HTTPException(status_code=404, detail=f"Crypto exchange rate not found for {from_currency_symbol} to {to_currency_symbol or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT} or API error: {data}")

@router.get("/crypto/{symbol}/history/daily", summary="Get Daily Cryptocurrency Time Series")
async def get_daily_crypto_data_endpoint(
    symbol: str = Path(..., title="Cryptocurrency Symbol", description="e.g., BTC, ETH"),
    market: str = Query(..., title="Market Currency", description="The market currency (e.g., USD, EUR)")
):
    """Fetches daily time series for a digital currency.
    
    Args:
        symbol (str): The cryptocurrency symbol.
        market (str): The market currency for the pair (e.g., USD).
        
    Returns:
        dict: An object containing metadata and the daily time series data.
        
    Raises:
        HTTPException: 404 if data for the crypto pair cannot be found.
    """
    key_name = f"Time Series (Digital Currency Daily)"
    data = await financial_service.get_daily_crypto_data(symbol, market)
    if data and key_name in data:
        return data
    raise HTTPException(status_code=404, detail=f"Daily crypto data not found for {symbol} in market {market} or API error: {data}")

@router.get("/crypto/{symbol}/rating", summary="Get Cryptocurrency Rating (FCAS)")
async def get_crypto_rating_endpoint(symbol: str = Path(..., title="Cryptocurrency Symbol")):
    """Fetches the FCAS Crypto Rating for a given cryptocurrency symbol.
    
    Args:
        symbol (str): The cryptocurrency symbol.
        
    Returns:
        dict: An object containing the rating data.
        
    Raises:
        HTTPException: 404 if the rating cannot be found.
    """
    data = await financial_service.get_crypto_rating(symbol)
    if data and "FCAS Rating" in data:
        return data
    raise HTTPException(status_code=404, detail=f"Crypto rating not found for {symbol} or API error: {data}")


@router.get("/fx/{from_symbol}/{to_symbol}/daily", summary="Get Daily Foreign Exchange (FX) Rates")
async def get_daily_fx_rates_endpoint(
    from_symbol: str = Path(..., title="From Currency Symbol", description="e.g., EUR, USD"),
    to_symbol: str = Path(..., title="To Currency Symbol", description="e.g., USD, JPY"),
    outputsize: Literal['compact', 'full'] = Query('compact', description="Number of data points.")
):
    """Fetches daily FX rates for a currency pair.
    
    Args:
        from_symbol (str): The base currency symbol.
        to_symbol (str): The quote currency symbol.
        outputsize (Literal): 'compact' for 100 data points, 'full' for complete history.
        
    Returns:
        dict: An object containing metadata and the daily FX time series.
        
    Raises:
        HTTPException: 404 if data for the currency pair cannot be found.
    """
    key_name = "Time Series FX (Daily)"
    data = await financial_service.get_daily_fx_rates(from_symbol, to_symbol, outputsize)
    if data and key_name in data:
        return data
    raise HTTPException(status_code=404, detail=f"Daily FX rates not found for {from_symbol}/{to_symbol} or API error: {data}")

@router.get("/technical/{symbol}/sma", summary="Get Simple Moving Average (SMA)")
async def get_sma_endpoint(
    symbol: str = Path(..., title="Stock Symbol"),
    interval: Literal['1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly'] = Query('daily'),
    time_period: int = Query(20, ge=1),
    series_type: Literal['open', 'high', 'low', 'close'] = Query('close')
):
    """Fetches Simple Moving Average (SMA) values for a stock.
    
    Args:
        symbol (str): The stock ticker symbol.
        interval (Literal): The time interval for the calculation.
        time_period (int): The number of data points to include in the moving average.
        series_type (Literal): The price type (e.g., 'close') to use for the calculation.
        
    Returns:
        dict: An object containing the SMA data.
        
    Raises:
        HTTPException: 404 if the data cannot be computed.
    """
    key_name = "Technical Analysis: SMA"
    data = await financial_service.get_sma(symbol, interval, time_period, series_type)
    if data and key_name in data:
        return data
    raise HTTPException(status_code=404, detail=f"SMA data not found for {symbol} or API error: {data}")

@router.get("/technical/{symbol}/ema", summary="Get Exponential Moving Average (EMA)")
async def get_ema_endpoint(
    symbol: str = Path(..., title="Stock Symbol"),
    interval: Literal['1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly'] = Query('daily'),
    time_period: int = Query(20, ge=1),
    series_type: Literal['open', 'high', 'low', 'close'] = Query('close')
):
    """Fetches Exponential Moving Average (EMA) values for a stock.
    
    Args:
        symbol (str): The stock ticker symbol.
        interval (Literal): The time interval for the calculation.
        time_period (int): The number of data points to include in the moving average.
        series_type (Literal): The price type (e.g., 'close') to use for the calculation.
        
    Returns:
        dict: An object containing the EMA data.
        
    Raises:
        HTTPException: 404 if the data cannot be computed.
    """
    key_name = "Technical Analysis: EMA"
    data = await financial_service.get_ema(symbol, interval, time_period, series_type)
    if data and key_name in data:
        return data
    raise HTTPException(status_code=404, detail=f"EMA data not found for {symbol} or API error: {data}")


@router.get("/economic/real-gdp", summary="Get Real GDP Data (US)")
async def get_real_gdp_endpoint(interval: Literal['annual', 'quarterly'] = Query('quarterly')):
    """Fetches Real GDP data for the United States.
    
    Args:
        interval (Literal): The frequency of the data ('annual' or 'quarterly').
        
    Returns:
        dict: An object containing the GDP data.
        
    Raises:
        HTTPException: 404 if the data cannot be found.
    """
    data = await financial_service.get_real_gdp(interval)
    if data and "data" in data:
        return data
    raise HTTPException(status_code=404, detail=f"Real GDP data not found for interval {interval} or API error: {data}")

@router.get("/economic/cpi", summary="Get Consumer Price Index (CPI) Data (US)")
async def get_cpi_endpoint(interval: Literal['monthly', 'semiannual'] = Query('monthly')):
    """Fetches Consumer Price Index (CPI) data for the United States.
    
    Args:
        interval (Literal): The frequency of the data ('monthly' or 'semiannual').
        
    Returns:
        dict: An object containing the CPI data.
        
    Raises:
        HTTPException: 404 if the data cannot be found.
    """
    data = await financial_service.get_cpi(interval)
    if data and "data" in data:
        return data
    raise HTTPException(status_code=404, detail=f"CPI data not found for interval {interval} or API error: {data}")

@router.get("/economic/inflation", summary="Get Inflation Data (US Annual)")
async def get_inflation_endpoint():
    """Fetches annual Inflation data for the United States.
    
    Returns:
        dict: An object containing the inflation data.
        
    Raises:
        HTTPException: 404 if the data cannot be found.
    """
    data = await financial_service.get_inflation()
    if data and "data" in data:
        return data
    raise HTTPException(status_code=404, detail=f"Inflation data not found or API error: {data}")

@router.get("/economic/treasury-yield", summary="Get Treasury Yield Data (US)")
async def get_treasury_yield_endpoint(
    interval: Literal['daily', 'weekly', 'monthly'] = Query('monthly'),
    maturity: Literal['3month', '2year', '5year', '7year', '10year', '30year'] = Query('10year')
):
    """Fetches Treasury Yield data for the United States.
    
    Args:
        interval (Literal): The frequency of the data points.
        maturity (Literal): The treasury maturity period.
        
    Returns:
        dict: An object containing the treasury yield data.
        
    Raises:
        HTTPException: 404 if the data cannot be found.
    """
    data = await financial_service.get_treasury_yield(interval, maturity)
    if data and "data" in data:
        return data
    raise HTTPException(status_code=404, detail=f"Treasury Yield data not found for {maturity} maturity, interval {interval} or API error: {data}")

@router.get(
    "/symbol/{symbol}/change-24h",
    response_model=PriceChange24hResponse,
    summary="Get 24-Hour Price Change",
    description="Fetches the approximate 24-hour price change for a given financial symbol (stock, crypto, FX)."
)
async def get_24h_symbol_change(
    symbol: str = Path(..., title="Stock Symbol")
):
    """Provides the 24-hour price change for a financial symbol.
    
    Calculates the current price, the price ~24 hours ago, and the
    absolute and percentage change. Timestamps are returned in UTC.

    Args:
        symbol (str): The financial symbol (e.g., AAPL, BTC-USD, EURUSD=X).

    Returns:
        PriceChange24hResponse: An object with the 24h change details.
        
    Raises:
        HTTPException: 404 if data for the symbol cannot be retrieved.
    """
    change_data = await financial_service.get_price_change_24h(symbol)
    if not change_data:
        raise HTTPException(
            status_code=404,
            detail=f"Could not retrieve 24-hour price change data for symbol '{symbol}'. The symbol may be invalid, or recent intraday data might be unavailable."
        )
    return PriceChange24hResponse(**change_data)