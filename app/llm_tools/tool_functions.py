import json
from app.services.financial_data_service import financial_data_service
from app.services.web_search_service import web_search_service
from app.services.vector_db_service import vector_db_service
from app.core.config import settings

async def get_stock_price(symbol: str):
    data = await financial_data_service.get_stock_quote(symbol)
    if data and data.get('05. price'):
        return f"The current price of {symbol} is ${data.get('05. price')}. Latest trading day: {data.get('07. latest trading day', 'N/A')}."
    
    search_query = f"current price of {symbol.upper()} stock in USD"
    web_search_result = await web_search_service.get_search_context(search_query, max_results=1)
    if web_search_result and "No relevant information" not in web_search_result:
        return f"Could not fetch direct API price for {symbol.upper()}. Web search result for '{search_query}': {web_search_result}"
    return f"Could not retrieve stock price information for {symbol.upper()}/USD via API or web search."

async def get_crypto_price(symbol: str, market: str = None):
    effective_market = market or settings.ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT
    price_data = await financial_data_service.get_crypto_quote(symbol, market=effective_market)
    if price_data: 
         return f"The current exchange rate for {symbol.upper()}/{effective_market.upper()} is {price_data}."
    
    search_query = f"current price of {symbol.upper()} crypto in {effective_market.upper()}"
    web_search_result = await web_search_service.get_search_context(search_query, max_results=1)
    if web_search_result and "No relevant information" not in web_search_result:
        return f"Could not fetch direct API price for {symbol.upper()}. Web search result for '{search_query}': {web_search_result}"
    return f"Could not retrieve cryptocurrency price information for {symbol.upper()}/{effective_market.upper()} via API or web search."

async def get_company_overview(symbol: str):
    data = await financial_data_service.get_company_overview(symbol)
    if data and data.get('Description'):
        overview = (
            f"Name: {data.get('Name', 'N/A')}\n"
            f"Symbol: {data.get('Symbol', 'N/A')}\n"
            f"Description: {data.get('Description', 'N/A')[:500]}...\n"
            f"Industry: {data.get('Industry', 'N/A')}\n"
            f"Sector: {data.get('Sector', 'N/A')}\n"
            f"Market Cap: {data.get('MarketCapitalization', 'N/A')}"
        )
        return overview
    return f"Could not retrieve company overview for {symbol}."

async def get_financial_news(query: str, limit: int = 3):
    news_context = await web_search_service.get_search_context(
        query, 
        max_results=limit,
        include_domains=["reuters.com", "bloomberg.com", "wsj.com", "marketwatch.com", "finance.yahoo.com", "coindesk.com", "cointelegraph.com"]
    )
    if news_context and "No relevant information" not in news_context:
        return f"News found for '{query}':\n{news_context}"
    return f"No specific news found via web search for the query: '{query}'."

async def explain_financial_concept(concept_name: str):
    pinecone_context = await vector_db_service.get_pinecone_context(f"explain {concept_name}", top_k=1)
    if pinecone_context and "No relevant documents found" not in pinecone_context:
        return f"From Knowledge Base for '{concept_name}':\n{pinecone_context}"
    
    web_search_context = await web_search_service.get_search_context(f"what is {concept_name} finance", max_results=1)
    if web_search_context and "No relevant information" not in web_search_context:
        return f"Web explanation for '{concept_name}':\n{web_search_context}"
    return f"Could not find a clear explanation for '{concept_name}' from available sources."

async def general_web_search(query: str):
    search_results = await web_search_service.get_search_context(query, max_results=2)
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