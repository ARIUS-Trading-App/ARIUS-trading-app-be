import json
from app.services.financial_data_service import financial_data_service
from app.services.web_search_service import web_search_service
from app.services.vector_db_service import vector_db_service # Assuming this is used by one of the tools
from app.core.config import settings

# Ensure settings are loaded if financial_data_service relies on them at import
# For example, ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT might be used.

async def get_stock_price(symbol: str):
    """Fetches the current trading price for a specific stock symbol."""
    data = await financial_data_service.get_stock_quote(symbol)
    if data and data.get('05. price') and data.get('05. price') != '0.0000': # Added check for valid price
        return f"The current price of {symbol.upper()} is ${data.get('05. price')}. Latest trading day: {data.get('07. latest trading day', 'N/A')}."
    
    error_message = f"Primary API could not retrieve a valid current stock price for {symbol.upper()}."
    if data and ("Error Message" in data or "Note" in data or not data.get('05. price') or data.get('05. price') == '0.0000'):
        api_msg = data.get('Error Message', data.get('Note', 'No specific API error message.'))
        error_message += f" API Message: {api_msg}"

    search_query = f"current price of {symbol.upper()} stock in USD"
    web_search_result = await web_search_service.get_search_context(search_query, max_results=1)
    if web_search_result and "No relevant information" not in web_search_result:
        return f"{error_message} Web search for '{search_query}' found: {web_search_result}"
    return f"{error_message} Web search fallback also did not find price information for {symbol.upper()}."


async def get_crypto_price(symbol: str, market: str = None):
    """Fetches the current price for a specific cryptocurrency symbol."""
    effective_market = market or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT
    price_data = await financial_data_service.get_crypto_exchange_rate(from_currency_symbol=symbol, to_currency_symbol=effective_market)
    
    if price_data and price_data.get('exchange_rate'):
        return f"The current exchange rate for {symbol.upper()}/{effective_market.upper()} is {price_data['exchange_rate']}. Last refreshed: {price_data.get('last_refreshed', 'N/A')}."
    
    error_message = f"Primary API could not retrieve crypto price for {symbol.upper()}/{effective_market.upper()}."
    if price_data and "Error Message" in price_data:
        error_message += f" API Message: {price_data['Error Message']}"
    elif price_data is None or not price_data.get('exchange_rate'):
        error_message += " (API call failed, returned no data, or no exchange rate found)."

    search_query = f"current price of {symbol.upper()} cryptocurrency in {effective_market.upper()}"
    web_search_result = await web_search_service.get_search_context(search_query, max_results=1)
    if web_search_result and "No relevant information" not in web_search_result:
        return f"{error_message} Web search for '{search_query}' found: {web_search_result}"
    return f"{error_message} Web search fallback also did not find price information for {symbol.upper()}/{effective_market.upper()}."

async def get_company_overview(symbol: str):
    """Retrieves detailed information about a publicly traded company."""
    data = await financial_data_service.get_company_overview(symbol)
    # Check if API returned data for the *correct* symbol, as Alpha Vantage might return data for a different symbol if the requested one is not found
    if data and data.get('Description') and data.get('Symbol', '').upper() == symbol.upper():
        overview = (
            f"Name: {data.get('Name', 'N/A')}\n"
            f"Symbol: {data.get('Symbol', 'N/A')}\n"
            f"Description: {data.get('Description', 'N/A')[:500]}...\n" 
            f"Industry: {data.get('Industry', 'N/A')}\n"
            f"Sector: {data.get('Sector', 'N/A')}\n"
            f"Market Cap: {data.get('MarketCapitalization', 'N/A')}"
        )
        return overview
    elif data and "Error Message" in data:
        return f"Could not retrieve company overview for {symbol.upper()}. API Error: {data['Error Message']}"
    elif data and data.get('Symbol', '').upper() != symbol.upper() and data.get('Description'): # API returned data for a different symbol
        return f"API did not find company overview for {symbol.upper()}. It might have matched a different symbol: {data.get('Symbol')}."
    return f"Could not retrieve company overview for {symbol.upper()}, or the symbol was not found by the API."


async def get_financial_news(query: str, limit: int = 3):
    """Searches for recent financial news and articles."""
    validated_limit = max(1, min(limit, 5)) # Ensure limit is within a sensible range, e.g. 1-5
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
    """Explains a financial concept, term, or metric."""
    pinecone_context = ""
    # Ensure vector_db_service and its method are available
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
    """Performs a general web search. Useful for finding lists of items (e.g. stocks, cryptos) or information not covered by other tools."""
    search_results = await web_search_service.get_search_context(query, max_results=3) 
    if search_results and "No relevant information" not in search_results:
        return f"Web search results for '{query}':\n{search_results}"
    return f"No specific information found via web search for '{query}'."


TOOL_FUNCTIONS = {
    "get_stock_price": get_stock_price,
    "get_crypto_price": get_crypto_price,
    "get_company_overview": get_company_overview,
    "get_financial_news": get_financial_news,
    "explain_financial_concept": explain_financial_concept,
    "general_web_search": general_web_search,
}