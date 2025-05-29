# app/llm_tools/tool_functions.py
import json
from typing import Optional, Dict, Any, List

from app.services.financial_data_service import financial_data_service
from app.services.web_search_service import web_search_service
from app.services.vector_db_service import vector_db_service
from app.core.config import settings
from app.db.session import SessionLocal
from app.crud import portfolio as crud_portfolio, user as crud_user
from app.services import portfolio_service as portfolio_service_module # renamed to avoid conflict
from app.services import portfolio_pnl_service

# --- Existing Tool Functions (Ensure they use the updated financial_data_service correctly) ---
async def get_stock_price(symbol: str):
    """Fetches the current trading price for a specific stock symbol."""
    data = await financial_data_service.get_stock_quote(symbol)
    if data and "Error Message" not in data and data.get('05. price') and data.get('05. price') != 'N/A':
        return f"The current price of {symbol.upper()} is ${data.get('05. price')}. Latest trading day: {data.get('07. latest trading day', 'N/A')}."
    
    error_message = f"Primary API could not retrieve a valid current stock price for {symbol.upper()}."
    if data and ("Error Message" in data or not data.get('05. price') or data.get('05. price') == 'N/A'):
        api_msg = data.get('Error Message', 'No specific API error message or invalid price.')
        error_message += f" API Message: {api_msg}"

    search_query = f"current price of {symbol.upper()} stock in USD"
    web_search_result = await web_search_service.get_search_context(search_query, max_results=1)
    if web_search_result and "No relevant information" not in web_search_result:
        return f"{error_message} Web search for '{search_query}' found: {web_search_result}"
    return f"{error_message} Web search fallback also did not find price information for {symbol.upper()}."

async def get_crypto_price(symbol: str, market: str = None):
    """Fetches the current price for a specific cryptocurrency symbol."""
    effective_market = market or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT # Can still use this as default target currency
    # financial_data_service.get_crypto_exchange_rate now returns a dict potentially with "Error Message" or "Realtime Currency Exchange Rate"
    price_data_response = await financial_data_service.get_crypto_exchange_rate(from_currency_symbol=symbol, to_currency_symbol=effective_market)
    
    if price_data_response and "Error Message" not in price_data_response:
        # Check structure from yfinance adapter
        if "Realtime Currency Exchange Rate" in price_data_response:
            data = price_data_response["Realtime Currency Exchange Rate"]
            rate = data.get("5. Exchange Rate")
            last_refreshed = data.get("6. Last Refreshed")
            from_code = data.get("1. From_Currency Code")
            to_code = data.get("3. To_Currency Code")
            if rate and rate != 'N/A':
                 return f"The current exchange rate for {from_code}/{to_code} is {rate}. Last refreshed: {last_refreshed}."
        elif "exchange_rate" in price_data_response : # Fallback structure
            rate = price_data_response.get("exchange_rate")
            last_refreshed = price_data_response.get("last_refreshed")
            from_code = price_data_response.get("from_currency")
            to_code = price_data_response.get("to_currency")
            if rate and rate != 'N/A':
                 return f"The current exchange rate for {from_code}/{to_code} is {rate}. Last refreshed: {last_refreshed}."


    error_message = f"Primary API could not retrieve crypto price for {symbol.upper()}/{effective_market.upper()}."
    if price_data_response and "Error Message" in price_data_response:
        error_message += f" API Message: {price_data_response['Error Message']}"
    else:
        error_message += " (API call failed, returned no data, or no exchange rate found)."

    search_query = f"current price of {symbol.upper()} cryptocurrency in {effective_market.upper()}"
    web_search_result = await web_search_service.get_search_context(search_query, max_results=1)
    if web_search_result and "No relevant information" not in web_search_result:
        return f"{error_message} Web search for '{search_query}' found: {web_search_result}"
    return f"{error_message} Web search fallback also did not find price information for {symbol.upper()}/{effective_market.upper()}."

async def get_company_overview(symbol: str):
    """Retrieves detailed information about a publicly traded company."""
    data = await financial_data_service.get_company_overview(symbol)
    if data and "Error Message" not in data and data.get('Description'): # yf wrapper returns dict or dict with "Error Message"
        overview = (
            f"Name: {data.get('Name', 'N/A')}\n"
            f"Symbol: {data.get('Symbol', symbol.upper())}\n" # Use input symbol as fallback
            f"Description: {data.get('Description', 'N/A')[:500]}...\n" 
            f"Industry: {data.get('Industry', 'N/A')}\n"
            f"Sector: {data.get('Sector', 'N/A')}\n"
            f"Market Cap: {data.get('MarketCapitalization', 'N/A')}"
        )
        return overview
    elif data and "Error Message" in data:
        return f"Could not retrieve company overview for {symbol.upper()}. API Error: {data['Error Message']}"
    return f"Could not retrieve company overview for {symbol.upper()}, or the symbol was not found/valid."

async def get_financial_news(query: str, limit: int = 3):
    """Searches for recent financial news and articles using general web search, filtered for financial domains."""
    validated_limit = max(1, min(limit, 5)) 
    news_context = await web_search_service.get_search_context(
        query, 
        max_results=validated_limit,
        include_domains=[
            "reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", 
            "finance.yahoo.com", "ft.com", "cnbc.com",
            "coindesk.com", "cointelegraph.com", "theblockcrypto.com" 
            ]
    )
    if news_context and "No relevant information" not in news_context:
        return f"News found for '{query}' (limit {validated_limit}):\n{news_context}"
    return f"No specific news found via web search for the query: '{query}' from preferred financial news domains."

async def explain_financial_concept(concept_name: str):
    """Explains a financial concept, term, or metric using knowledge base and web search."""
    pinecone_context = ""
    if vector_db_service and hasattr(vector_db_service, 'get_pinecone_context'): 
        try:
            pinecone_context = await vector_db_service.get_pinecone_context(f"explain {concept_name}", top_k=1)
        except Exception as e:
            print(f"Error querying vector DB for '{concept_name}': {e}")
            pinecone_context = "" 

    if pinecone_context and "No relevant documents found" not in pinecone_context and len(pinecone_context.strip()) > 10:
        return f"From Knowledge Base for '{concept_name}':\n{pinecone_context}"
    
    web_search_context = await web_search_service.get_search_context(f"what is {concept_name} in finance", max_results=1)
    if web_search_context and "No relevant information" not in web_search_context:
        source_prefix = "Web explanation"
        if not (pinecone_context and "No relevant documents found" not in pinecone_context and len(pinecone_context.strip()) > 10):
            source_prefix = "Could not find specific information in Knowledge Base. Web explanation"
        return f"{source_prefix} for '{concept_name}':\n{web_search_context}"
    
    return f"Could not find a clear explanation for '{concept_name}' from available sources (Knowledge Base or Web Search)."

async def general_web_search(query: str):
    """Performs a general web search. Useful for finding lists of items or information not covered by other tools."""
    search_results = await web_search_service.get_search_context(query, max_results=3) 
    if search_results and "No relevant information" not in search_results:
        return f"Web search results for '{query}':\n{search_results}"
    return f"No specific information found via web search for '{query}'."

# --- New Tool Functions to be added ---

async def get_historical_stock_data(symbol: str, outputsize: str = "compact"):
    """Fetches daily historical stock data (date, open, high, low, close, adjusted close, volume, dividend, split coefficient) for a stock symbol."""
    data = await financial_data_service.get_daily_adjusted_stock_data(symbol, outputsize)
    if data and "Error Message" not in data:
        # Data is already a dict, ready to be returned or summarized.
        # For LLM, returning the full structure might be too verbose for direct chat.
        # Consider returning a summary or a limited number of recent entries.
        # For now, let's return it as is, assuming RAG synthesis will handle it.
        return data 
    return data.get("Error Message", f"Could not retrieve historical stock data for {symbol}.")

async def get_intraday_stock_data_tool(symbol: str, interval: str = '5min', outputsize: str = 'compact'):
    """Fetches intraday stock data (date, open, high, low, close, volume) for a stock symbol at specified intervals."""
    # Renamed to avoid conflict with financial_data_service.get_intraday_stock_data
    data = await financial_data_service.get_intraday_stock_data(symbol, interval, outputsize)
    if data and "Error Message" not in data:
        return data
    return data.get("Error Message", f"Could not retrieve intraday stock data for {symbol} with interval {interval}.")

async def get_income_statement_tool(symbol: str):
    """Fetches annual and quarterly income statements for a given stock symbol."""
    data = await financial_data_service.get_income_statement(symbol)
    if data and "Error Message" not in data:
        return data
    return data.get("Error Message", f"Could not retrieve income statement for {symbol}.")

async def get_balance_sheet_tool(symbol: str):
    """Fetches annual and quarterly balance sheets for a given stock symbol."""
    data = await financial_data_service.get_balance_sheet(symbol)
    if data and "Error Message" not in data:
        return data
    return data.get("Error Message", f"Could not retrieve balance sheet for {symbol}.")

async def get_cash_flow_statement_tool(symbol: str):
    """Fetches annual and quarterly cash flow statements for a given stock symbol."""
    data = await financial_data_service.get_cash_flow(symbol)
    if data and "Error Message" not in data:
        return data
    return data.get("Error Message", f"Could not retrieve cash flow statement for {symbol}.")

async def get_company_earnings_tool(symbol: str):
    """Fetches historical annual and quarterly earnings (EPS and Revenue) for a given stock symbol."""
    data = await financial_data_service.get_earnings(symbol)
    if data and "Error Message" not in data:
        return data
    return data.get("Error Message", f"Could not retrieve earnings data for {symbol}.")

async def get_asset_price_change_24h(symbol: str):
    """Fetches the price change for an asset (stock, crypto, FX) over the last 24 hours."""
    data = await financial_data_service.get_price_change_24h(symbol)
    if data and "Error Message" not in data:
        return (f"24h Price Change for {data.get('symbol', symbol.upper())}: "
                f"Current Price: {data.get('current_price', 'N/A')}, "
                f"Price 24h Ago: {data.get('price_24h_ago', 'N/A')}, "
                f"Change: {data.get('change_amount', 'N/A')} ({data.get('change_percent', 'N/A'):.2f}%)"
                if isinstance(data.get('change_percent'), float) else 
                f"Change: {data.get('change_amount', 'N/A')} ({data.get('change_percent', 'N/A')})")
    return data.get("Error Message", f"Could not retrieve 24h price change for {symbol}.") if isinstance(data, dict) else str(data)



async def get_ticker_specific_news(symbol: str, limit: int = 5):
    """Fetches recent news articles specifically related to a ticker symbol from financial data provider (yfinance)."""
    # Assuming you've renamed the service method for clarity:
    # data = await financial_data_service.get_yfinance_ticker_news(tickers=symbol, limit=limit)
    # If still using the old name:
    data = await financial_data_service.get_alpha_vantage_news_sentiment(tickers=symbol, limit=limit)
    
    if data and "Error Message" not in data and "feed" in data:
        news_feed = data.get("feed", [])
        
        # print(f"DEBUG: Processed news_feed for {symbol} in tool function: {news_feed}") # For debugging

        if not news_feed:
            return f"No specific news found for {symbol.upper()} directly from the financial data provider."

        valid_news_items = []
        for item in news_feed:
            title = item.get('title') # This will now get the correctly extracted title
            url = item.get('url')     # This will now get the correctly extracted URL
            
            if title and url: 
                formatted_item = (
                    f"Title: {title}\n"
                    f"URL: {url}\n"
                    f"Published: {item.get('time_published', 'N/A')}\n"
                    f"Source: {item.get('source', 'N/A')}"
                )
                valid_news_items.append(formatted_item)
        
        if not valid_news_items:
            return f"News entries were found for {symbol.upper()}, but they currently lack essential details (like title or URL) after processing."
            
        return f"Recent news for {symbol.upper()} (limit {len(valid_news_items)} of {limit} requested):\n\n" + "\n\n".join(valid_news_items)
    
    if isinstance(data, dict) and "Error Message" in data:
        return data["Error Message"]
    elif isinstance(data, dict) and "Note" in data:
        return data["Note"]
    
    return f"Could not retrieve or parse specific news feed for {symbol.upper()}."

# --- Portfolio Related Tools (require user_id and portfolio context) ---

def _get_portfolio_id_from_params(db, user_id: int, portfolio_name: Optional[str] = None, portfolio_id: Optional[int] = None) -> Optional[int]:
    """Helper to resolve portfolio_id, checking ownership."""
    if portfolio_id:
        portfolio = crud_portfolio.get_portfolio(db, portfolio_id=portfolio_id)
        if portfolio and portfolio.user_id == user_id:
            return portfolio_id
        return None # Not found or not owned
    
    user_portfolios = crud_portfolio.get_portfolios(db, user_id=user_id)
    if not user_portfolios:
        return None # No portfolios for user

    if portfolio_name:
        for p in user_portfolios:
            if p.name.lower() == portfolio_name.lower():
                return p.id
        return None # Named portfolio not found
    
    if len(user_portfolios) == 1:
        return user_portfolios[0].id # Default to the only portfolio
    
    return None # Ambiguous or not found

async def list_my_portfolios(user_id: int):
    """Lists all portfolios for the current user."""
    db = SessionLocal()
    try:
        portfolios = crud_portfolio.get_portfolios(db, user_id=user_id)
        if not portfolios:
            return "You currently do not have any portfolios."
        return [{"portfolio_id": p.id, "name": p.name, "created_at": p.created_at.strftime('%Y-%m-%d')} for p in portfolios]
    except Exception as e:
        return f"Error listing portfolios: {str(e)}"
    finally:
        db.close()

async def get_portfolio_positions_tool(user_id: int, portfolio_name: Optional[str] = None, portfolio_id: Optional[int] = None):
    """Lists all positions in a specified portfolio for the current user."""
    db = SessionLocal()
    try:
        resolved_portfolio_id = _get_portfolio_id_from_params(db, user_id, portfolio_name, portfolio_id)
        if resolved_portfolio_id is None:
            portfolios = crud_portfolio.get_portfolios(db, user_id=user_id)
            if not portfolios: return "No portfolios found for user. Cannot get positions."
            if len(portfolios) > 1 and not portfolio_name and not portfolio_id:
                return f"You have multiple portfolios ({', '.join([p.name for p in portfolios])}). Please specify which portfolio by name or ID."
            return "Portfolio not found or user does not have access."

        positions = crud_portfolio.get_positions(db, portfolio_id=resolved_portfolio_id)
        if not positions:
            return f"No positions found in portfolio ID {resolved_portfolio_id}."
        return [{"symbol": pos.symbol, "quantity": pos.quantity, "average_price": pos.avg_price} for pos in positions]
    except Exception as e:
        return f"Error getting portfolio positions: {str(e)}"
    finally:
        db.close()

async def get_portfolio_market_value_tool(user_id: int, portfolio_name: Optional[str] = None, portfolio_id: Optional[int] = None):
    """Calculates the current total market value of a specified portfolio for the current user."""
    db = SessionLocal()
    try:
        resolved_portfolio_id = _get_portfolio_id_from_params(db, user_id, portfolio_name, portfolio_id)
        if resolved_portfolio_id is None:
            portfolios = crud_portfolio.get_portfolios(db, user_id=user_id)
            if not portfolios: return "No portfolios found for user. Cannot calculate value."
            if len(portfolios) > 1 and not portfolio_name and not portfolio_id:
                return f"You have multiple portfolios ({', '.join([p.name for p in portfolios])}). Please specify which portfolio by name or ID."
            return "Portfolio not found or user does not have access."

        market_value = await portfolio_service_module.compute_portfolio_value(db, portfolio_id=resolved_portfolio_id)
        return {"portfolio_id": resolved_portfolio_id, "total_market_value": market_value}
    except Exception as e:
        return f"Error calculating portfolio market value: {str(e)}"
    finally:
        db.close()

async def get_portfolio_daily_change_percentage_tool(user_id: int, portfolio_name: Optional[str] = None, portfolio_id: Optional[int] = None):
    """Calculates the overall 24-hour percentage change of a specified portfolio for the current user."""
    db = SessionLocal()
    try:
        resolved_portfolio_id = _get_portfolio_id_from_params(db, user_id, portfolio_name, portfolio_id)
        if resolved_portfolio_id is None:
            portfolios = crud_portfolio.get_portfolios(db, user_id=user_id)
            if not portfolios: return "No portfolios found for user. Cannot calculate daily change."
            if len(portfolios) > 1 and not portfolio_name and not portfolio_id:
                return f"You have multiple portfolios ({', '.join([p.name for p in portfolios])}). Please specify which portfolio by name or ID."
            return "Portfolio not found or user does not have access."

        change_percentage = await portfolio_service_module.get_portfolio_24h_change_percentage(db, portfolio_id=resolved_portfolio_id)
        return {"portfolio_id": resolved_portfolio_id, "daily_change_percentage": f"{change_percentage:.2f}%"}
    except Exception as e:
        return f"Error calculating portfolio daily change: {str(e)}"
    finally:
        db.close()

async def get_portfolio_pnl_tool(user_id: int, portfolio_name: Optional[str] = None, portfolio_id: Optional[int] = None):
    """Calculates the Profit and Loss (PnL) for a specified portfolio, including realized, unrealized, and current market value."""
    db = SessionLocal()
    try:
        resolved_portfolio_id = _get_portfolio_id_from_params(db, user_id, portfolio_name, portfolio_id)
        if resolved_portfolio_id is None:
            portfolios = crud_portfolio.get_portfolios(db, user_id=user_id)
            if not portfolios: return "No portfolios found for user. Cannot calculate PnL."
            if len(portfolios) > 1 and not portfolio_name and not portfolio_id:
                return f"You have multiple portfolios ({', '.join([p.name for p in portfolios])}). Please specify which portfolio by name or ID."
            return "Portfolio not found or user does not have access."

        pnl_data = await portfolio_pnl_service.compute_pnl(db, portfolio_id=resolved_portfolio_id)
        return {"portfolio_id": resolved_portfolio_id, **pnl_data}
    except Exception as e:
        return f"Error calculating portfolio PnL: {str(e)}"
    finally:
        db.close()


TOOL_FUNCTIONS = {
    "get_stock_price": get_stock_price,
    "get_crypto_price": get_crypto_price,
    "get_company_overview": get_company_overview,
    "get_financial_news": get_financial_news,
    "explain_financial_concept": explain_financial_concept,
    "general_web_search": general_web_search,
    # New tools
    "get_historical_stock_data": get_historical_stock_data,
    "get_intraday_stock_data": get_intraday_stock_data_tool, # Use the renamed wrapper
    "get_income_statement": get_income_statement_tool,
    "get_balance_sheet": get_balance_sheet_tool,
    "get_cash_flow_statement": get_cash_flow_statement_tool,
    "get_company_earnings": get_company_earnings_tool,
    "get_asset_price_change_24h": get_asset_price_change_24h,
    "get_ticker_specific_news": get_ticker_specific_news,
    "list_my_portfolios": list_my_portfolios,
    "get_portfolio_positions": get_portfolio_positions_tool,
    "get_portfolio_market_value": get_portfolio_market_value_tool,
    "get_portfolio_daily_change_percentage": get_portfolio_daily_change_percentage_tool,
    "get_portfolio_pnl": get_portfolio_pnl_tool,
}