from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import Optional, Literal # For literal types in query params
from app.services.financial_data_service import financial_data_service as financial_service
from app.core.config import settings
from app.schemas.portfolio import PriceChange24hResponse

# Create a router
router = APIRouter(
    prefix="/financials",
    tags=["Financial Data"],
)

# Helper function for dependency injection (optional but good practice)
# async def get_financial_service():
#     return financial_service

@router.get("/stock/{symbol}/quote", summary="Get Real-Time Stock Quote")
async def get_stock_quote_endpoint(symbol: str = Path(..., title="Stock Symbol", description="The stock ticker symbol (e.g., AAPL, MSFT)")):
    """
    Fetches a real-time quote for a given stock symbol.
    Includes price, volume, change, etc.
    """
    data = await financial_service.get_stock_quote(symbol)
    if data and not ("Error Message" in data or "Information" in data or not data.get("01. symbol")): # Check for actual data
        return data
    raise HTTPException(status_code=404, detail=f"Stock quote not found for symbol {symbol} or API error: {data}")

@router.get("/stock/{symbol}/history/daily-adjusted", summary="Get Daily Adjusted Stock Time Series")
async def get_daily_adjusted_stock_data_endpoint(
    symbol: str = Path(..., title="Stock Symbol", description="The stock ticker symbol"),
    outputsize: Literal['compact', 'full'] = Query('compact', description="Number of data points: 'compact' for 100, 'full' for full history.")
):
    """
    Fetches daily time series (date, open, high, low, close, adjusted close, volume, dividend, split coefficient)
    for a stock.
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
    """
    Fetches intraday time series (date, open, high, low, close, volume) for a stock.
    """
    key_name = f"Time Series ({interval})"
    data = await financial_service.get_intraday_stock_data(symbol, interval, outputsize)
    if data and key_name in data:
        return data
    raise HTTPException(status_code=404, detail=f"Intraday stock data not found for {symbol} with interval {interval} or API error: {data}")


@router.get("/stock/{symbol}/overview", summary="Get Company Overview")
async def get_company_overview_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """
    Fetches company information, financial ratios, and other key metrics for a stock.
    """
    data = await financial_service.get_company_overview(symbol)
    if data: # Check if symbol in response matches request
        return data
    raise HTTPException(status_code=404, detail=f"Company overview not found for {symbol} or API error: {data}")

@router.get("/stock/{symbol}/financials/income-statement", summary="Get Income Statement")
async def get_income_statement_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """Fetches annual and quarterly income statements for a stock."""
    data = await financial_service.get_income_statement(symbol)
    if data and (data.get("symbol") == symbol.upper() or (isinstance(data, dict) and not data)): # Empty dict is a valid response for no data
        return data
    elif isinstance(data, list) and data: # Sometimes it returns a list of reports
        return data
    raise HTTPException(status_code=404, detail=f"Income statement not found for {symbol} or API error: {data}")

@router.get("/stock/{symbol}/financials/balance-sheet", summary="Get Balance Sheet")
async def get_balance_sheet_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """Fetches annual and quarterly balance sheets for a stock."""
    data = await financial_service.get_balance_sheet(symbol)
    if data and (data.get("symbol") == symbol.upper() or (isinstance(data, dict) and not data)):
        return data
    elif isinstance(data, list) and data:
        return data
    raise HTTPException(status_code=404, detail=f"Balance sheet not found for {symbol} or API error: {data}")

@router.get("/stock/{symbol}/financials/cash-flow", summary="Get Cash Flow Statement")
async def get_cash_flow_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """Fetches annual and quarterly cash flow statements for a stock."""
    data = await financial_service.get_cash_flow(symbol)
    if data and (data.get("symbol") == symbol.upper() or (isinstance(data, dict) and not data)):
        return data
    elif isinstance(data, list) and data:
        return data
    raise HTTPException(status_code=404, detail=f"Cash flow statement not found for {symbol} or API error: {data}")

@router.get("/stock/{symbol}/financials/earnings", summary="Get Company Earnings (EPS)")
async def get_earnings_endpoint(symbol: str = Path(..., title="Stock Symbol")):
    """Fetches annual and quarterly earnings (EPS) for a stock."""
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
    """
    Fetches latest financial news for a stock symbol using a web search service.
    (Note: This uses the mock web_search_service in this example).
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
    limit: int = Query(50, ge=1, le=200, description="Number of results (max 200 for free tier, 1000 for premium).") # Adjusted limit
):
    """
    Fetches market news and sentiment data from Alpha Vantage.
    Provide either 'tickers' or 'topics'.
    """
    if not tickers and not topics:
        raise HTTPException(status_code=400, detail="Either 'tickers' or 'topics' query parameter must be provided.")
    data = await financial_service.get_alpha_vantage_news_sentiment(tickers, topics, time_from, time_to, sort, limit)
    if data and "feed" in data:
        return data
    elif data and "Information" in data: # Alpha Vantage sometimes returns an "Information" note for no data or limits
        return {"message": data["Information"]}
    elif data and "Error Message" in data:
         raise HTTPException(status_code=400, detail=f"API Error: {data['Error Message']}")
    raise HTTPException(status_code=404, detail=f"News & sentiment data not found or API error: {data}")


@router.get("/crypto/{from_currency_symbol}/exchange-rate", summary="Get Cryptocurrency Exchange Rate")
async def get_crypto_exchange_rate_endpoint(
    from_currency_symbol: str = Path(..., title="From Cryptocurrency Symbol", description="e.g., BTC, ETH"),
    to_currency_symbol: Optional[str] = Query(None, title="To Currency Symbol", description="e.g., USD, EUR. Defaults to system default (USD).")
):
    """
    Fetches the real-time exchange rate for a cryptocurrency pair (e.g., BTC to USD).
    """
    data = await financial_service.get_crypto_exchange_rate(from_currency_symbol, to_currency_symbol)
    if data and data.get("exchange_rate"):
        return data
    elif data and data.get("message"): # Handle service-returned messages (e.g. "invalid pair")
        raise HTTPException(status_code=404, detail=data["message"])
    raise HTTPException(status_code=404, detail=f"Crypto exchange rate not found for {from_currency_symbol} to {to_currency_symbol or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT} or API error: {data}")

@router.get("/crypto/{symbol}/history/daily", summary="Get Daily Cryptocurrency Time Series")
async def get_daily_crypto_data_endpoint(
    symbol: str = Path(..., title="Cryptocurrency Symbol", description="e.g., BTC, ETH"),
    market: str = Query(..., title="Market Currency", description="The market currency (e.g., USD, EUR)")
):
    """
    Fetches daily time series (date, open, high, low, close, volume, market cap) for a digital currency.
    """
    key_name = f"Time Series (Digital Currency Daily)"
    data = await financial_service.get_daily_crypto_data(symbol, market)
    if data and key_name in data:
        return data
    raise HTTPException(status_code=404, detail=f"Daily crypto data not found for {symbol} in market {market} or API error: {data}")

@router.get("/crypto/{symbol}/rating", summary="Get Cryptocurrency Rating (FCAS)")
async def get_crypto_rating_endpoint(symbol: str = Path(..., title="Cryptocurrency Symbol")):
    """Fetches the FCAS Crypto Rating for a given cryptocurrency symbol (e.g., BTC, ETH)."""
    data = await financial_service.get_crypto_rating(symbol)
    # FCAS data has a specific structure, e.g. "Rating"
    if data and "FCAS Rating" in data:
        return data
    raise HTTPException(status_code=404, detail=f"Crypto rating not found for {symbol} or API error: {data}")


@router.get("/fx/{from_symbol}/{to_symbol}/daily", summary="Get Daily Foreign Exchange (FX) Rates")
async def get_daily_fx_rates_endpoint(
    from_symbol: str = Path(..., title="From Currency Symbol", description="e.g., EUR, USD"),
    to_symbol: str = Path(..., title="To Currency Symbol", description="e.g., USD, JPY"),
    outputsize: Literal['compact', 'full'] = Query('compact', description="Number of data points.")
):
    """Fetches daily FX rates for a currency pair."""
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
    """Fetches Simple Moving Average (SMA) values for a stock."""
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
    """Fetches Exponential Moving Average (EMA) values for a stock."""
    key_name = "Technical Analysis: EMA"
    data = await financial_service.get_ema(symbol, interval, time_period, series_type)
    if data and key_name in data:
        return data
    raise HTTPException(status_code=404, detail=f"EMA data not found for {symbol} or API error: {data}")


@router.get("/economic/real-gdp", summary="Get Real GDP Data (US)")
async def get_real_gdp_endpoint(interval: Literal['annual', 'quarterly'] = Query('quarterly')):
    """Fetches Real GDP data for the United States."""
    data = await financial_service.get_real_gdp(interval)
    if data and "data" in data:
        return data
    raise HTTPException(status_code=404, detail=f"Real GDP data not found for interval {interval} or API error: {data}")

@router.get("/economic/cpi", summary="Get Consumer Price Index (CPI) Data (US)")
async def get_cpi_endpoint(interval: Literal['monthly', 'semiannual'] = Query('monthly')):
    """Fetches Consumer Price Index (CPI) data for the United States."""
    data = await financial_service.get_cpi(interval)
    if data and "data" in data:
        return data
    raise HTTPException(status_code=404, detail=f"CPI data not found for interval {interval} or API error: {data}")

@router.get("/economic/inflation", summary="Get Inflation Data (US Annual)")
async def get_inflation_endpoint():
    """Fetches annual Inflation data for the United States."""
    data = await financial_service.get_inflation()
    if data and "data" in data:
        return data
    raise HTTPException(status_code=404, detail=f"Inflation data not found or API error: {data}")

@router.get("/economic/treasury-yield", summary="Get Treasury Yield Data (US)")
async def get_treasury_yield_endpoint(
    interval: Literal['daily', 'weekly', 'monthly'] = Query('monthly'),
    maturity: Literal['3month', '2year', '5year', '7year', '10year', '30year'] = Query('10year')
):
    """Fetches Treasury Yield data for the United States."""
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
    """
    Provides the current price, the price approximately 24 hours ago,
    the absolute change, and the percentage change for the given symbol.
    It uses 1-hour interval data over the last 2 days, falling back to 5-minute intervals if needed.
    Timestamps are in UTC.
    """
    change_data = await financial_service.get_price_change_24h(symbol)
    if not change_data:
        raise HTTPException(
            status_code=404,
            detail=f"Could not retrieve 24-hour price change data for symbol '{symbol}'. The symbol may be invalid, or recent intraday data might be unavailable."
        )
    return PriceChange24hResponse(**change_data)