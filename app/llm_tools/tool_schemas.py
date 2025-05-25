TOOL_GET_STOCK_PRICE = {
    "name": "get_stock_price",
    "description": "Fetches the current trading price for a specific publicly traded company's stock symbol. Use this for real-time stock prices ONLY for company stocks (e.g., AAPL, MSFT). Do NOT use for cryptocurrencies.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "The stock ticker symbol for a company (e.g., AAPL for Apple, MSFT for Microsoft, TSLA for Tesla). Do not use cryptocurrency symbols here."
            }
        },
        "required": ["symbol"]
    }
}

TOOL_GET_CRYPTO_PRICE = {
    "name": "get_crypto_price",
    "description": "Fetches the current price for a specific cryptocurrency symbol (e.g., BTC for Bitcoin, ETH for Ethereum) against a market currency (defaults to USD). Use this ONLY for cryptocurrencies.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "The cryptocurrency symbol (e.g., BTC, ETH, SOL). Do not use company stock symbols here."
            },
            "market": {
                "type": "string",
                "description": "The market currency to quote against (e.g., USD, EUR). Defaults to USD if not specified.",
                "optional": True
            }
        },
        "required": ["symbol"]
    }
}

TOOL_GET_COMPANY_OVERVIEW = {
    "name": "get_company_overview",
    "description": "Retrieves detailed information about a publicly traded company, such as its business description, sector, industry, and market capitalization. Use this for company stocks (e.g., AAPL, MSFT).",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "The stock ticker symbol for the company (e.g., AAPL, MSFT)."
            }
        },
        "required": ["symbol"]
    }
}

TOOL_GET_FINANCIAL_NEWS = {
    "name": "get_financial_news",
    "description": "Searches for recent financial news and articles related to specific companies, stocks, cryptocurrencies, or general market topics. Useful for understanding recent developments, sentiment, and analysis.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A specific query for the news search (e.g., 'Tesla Q3 earnings', 'Bitcoin adoption news', 'semiconductor industry outlook'). Be specific for better results."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of news articles to return. Defaults to 3.",
                "optional": True
            }
        },
        "required": ["query"]
    }
}

TOOL_EXPLAIN_FINANCIAL_CONCEPT = {
    "name": "explain_financial_concept",
    "description": "Explains a financial concept, term, or metric (e.g., P/E ratio, inflation, ETF, diversification). Uses knowledge base and web search for comprehensive explanations.",
    "parameters": {
        "type": "object",
        "properties": {
            "concept_name": {
                "type": "string",
                "description": "The financial concept or term to be explained (e.g., 'Price to Earnings Ratio', 'Market Capitalization')."
            }
        },
        "required": ["concept_name"]
    }
}

TOOL_GENERAL_WEB_SEARCH = {
    "name": "general_web_search",
    "description": "Performs a general web search when other specialized tools are not suitable or have failed. Useful for broad queries, current events not strictly financial, or as a fallback for information not found in financial databases.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query."
            }
        },
        "required": ["query"]
    }
}


AVAILABLE_TOOLS_SCHEMAS = [
    TOOL_GET_STOCK_PRICE,
    TOOL_GET_CRYPTO_PRICE,
    TOOL_GET_COMPANY_OVERVIEW,
    TOOL_GET_FINANCIAL_NEWS,
    TOOL_EXPLAIN_FINANCIAL_CONCEPT,
    TOOL_GENERAL_WEB_SEARCH,
]

def get_tool_schemas_for_llm():
    import json
    return json.dumps(AVAILABLE_TOOLS_SCHEMAS, indent=2)