# app/llm_tools/tool_schemas.py

# --- Existing Tool Schemas (ensure descriptions are accurate for yfinance) ---
TOOL_GET_STOCK_PRICE = {
    "name": "get_stock_price",
    "description": "Fetches the current trading price for a specific publicly traded company's stock symbol (e.g., AAPL, MSFT) using Yahoo Finance data. Use this for real-time stock prices ONLY for company stocks. Do NOT use for cryptocurrencies.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "The stock ticker symbol for a company (e.g., AAPL for Apple, MSFT for Microsoft). Case-insensitive but typically uppercase."
            }
        },
        "required": ["symbol"]
    }
}

TOOL_GET_CRYPTO_PRICE = {
    "name": "get_crypto_price",
    "description": "Fetches the current price for a specific cryptocurrency symbol (e.g., BTC for Bitcoin, ETH for Ethereum) against a market currency (defaults to USD) using Yahoo Finance data (e.g., symbol 'BTC', market 'USD' becomes 'BTC-USD' for lookup). Use this ONLY for cryptocurrencies.",
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
                "optional": True # Made optional in schema, handled by default in function
            }
        },
        "required": ["symbol"]
    }
}

TOOL_GET_COMPANY_OVERVIEW = {
    "name": "get_company_overview",
    "description": "Retrieves detailed information about a publicly traded company using Yahoo Finance data, such as its business description, sector, industry, financials (Market Cap, P/E, EPS), and key metrics. Use this for company stocks (e.g., AAPL, MSFT).",
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

TOOL_GET_FINANCIAL_NEWS = { # This tool uses general web search, not yfinance directly
    "name": "get_financial_news",
    "description": "Searches for recent financial news and articles from major financial news websites related to specific companies, stocks, cryptocurrencies, or general market topics. Useful for understanding recent developments, sentiment, and analysis.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A specific query for the news search (e.g., 'Tesla Q3 earnings', 'Bitcoin adoption news', 'semiconductor industry outlook'). Be specific for better results."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of news articles to return. Defaults to 3, max 5.",
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
    "description": "Performs a general web search when other specialized tools are not suitable or have failed. Useful for broad queries, current events not strictly financial, or as a fallback. Also highly useful for an initial search to identify specific items (e.g., 'best pharma stocks', 'top trending cryptocurrencies') which can then be used with other tools to get details like prices.",
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

# --- New Tool Schemas to be added ---

TOOL_GET_HISTORICAL_STOCK_DATA = {
    "name": "get_historical_stock_data",
    "description": "Fetches daily historical stock data (OHLCV, adjusted close, dividends, splits) for a given stock symbol from Yahoo Finance. Useful for analyzing past performance.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "The stock ticker symbol (e.g., AAPL)."},
            "outputsize": {
                "type": "string", "description": "Output size. 'compact' for the last 100 data points, 'full' for the complete history. Defaults to 'compact'.",
                "enum": ["compact", "full"], "optional": True
            }
        },
        "required": ["symbol"]
    }
}

TOOL_GET_INTRADAY_STOCK_DATA = {
    "name": "get_intraday_stock_data",
    "description": "Fetches intraday stock data (OHLCV) for a stock symbol at specified intervals from Yahoo Finance. Useful for short-term price movements.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "The stock ticker symbol (e.g., AAPL)."},
            "interval": {
                "type": "string", "description": "Data interval. Supported: '1min', '5min', '15min', '30min', '60min'. Defaults to '5min'.",
                "enum": ['1min', '5min', '15min', '30min', '60min'], "optional": True
            },
            "outputsize": {
                "type": "string", "description": "Output size. 'compact' for recent data (e.g., last 1-2 days), 'full' for max available (e.g., 7 days for 1min, 60 days for others). Defaults to 'compact'.",
                "enum": ["compact", "full"], "optional": True
            }
        },
        "required": ["symbol"]
    }
}

TOOL_GET_INCOME_STATEMENT = {
    "name": "get_income_statement",
    "description": "Retrieves annual and quarterly income statements for a publicly traded company from Yahoo Finance. Shows revenue, expenses, and profit.",
    "parameters": {
        "type": "object",
        "properties": {"symbol": {"type": "string", "description": "The stock ticker symbol (e.g., AAPL)."}},
        "required": ["symbol"]
    }
}

TOOL_GET_BALANCE_SHEET = {
    "name": "get_balance_sheet",
    "description": "Retrieves annual and quarterly balance sheets for a publicly traded company from Yahoo Finance. Shows assets, liabilities, and equity.",
    "parameters": {
        "type": "object",
        "properties": {"symbol": {"type": "string", "description": "The stock ticker symbol (e.g., AAPL)."}},
        "required": ["symbol"]
    }
}

TOOL_GET_CASH_FLOW_STATEMENT = {
    "name": "get_cash_flow_statement",
    "description": "Retrieves annual and quarterly cash flow statements for a publicly traded company from Yahoo Finance. Shows cash inflows and outflows.",
    "parameters": {
        "type": "object",
        "properties": {"symbol": {"type": "string", "description": "The stock ticker symbol (e.g., AAPL)."}},
        "required": ["symbol"]
    }
}

TOOL_GET_COMPANY_EARNINGS = {
    "name": "get_company_earnings",
    "description": "Retrieves historical annual and quarterly earnings (EPS and Revenue) data for a publicly traded company from Yahoo Finance.",
    "parameters": {
        "type": "object",
        "properties": {"symbol": {"type": "string", "description": "The stock ticker symbol (e.g., AAPL)."}},
        "required": ["symbol"]
    }
}

TOOL_GET_ASSET_PRICE_CHANGE_24H = {
    "name": "get_asset_price_change_24h",
    "description": "Fetches the approximate price change (amount and percentage) for an asset (stock, crypto, or FX) over the last 24 hours using Yahoo Finance. For crypto, use format like 'BTC-USD'. For FX, use 'EURUSD=X'.",
    "parameters": {
        "type": "object",
        "properties": {"symbol": {"type": "string", "description": "The asset symbol (e.g., AAPL, BTC-USD, EURUSD=X)."}},
        "required": ["symbol"]
    }
}

TOOL_GET_TICKER_SPECIFIC_NEWS = {
    "name": "get_ticker_specific_news",
    "description": "Fetches recent news articles specifically related to a ticker symbol (stock or crypto) directly from Yahoo Finance news feed. This is different from general financial news search.",
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "The stock or cryptocurrency ticker symbol (e.g., AAPL, BTC-USD)."},
            "limit": {"type": "integer", "description": "Maximum number of news articles to return. Defaults to 5.", "optional": True}
        },
        "required": ["symbol"]
    }
}

TOOL_LIST_MY_PORTFOLIOS = {
    "name": "list_my_portfolios",
    "description": "Lists all investment portfolios belonging to the current user, showing their names and IDs. The 'user_id' is automatically inferred.",
    "parameters": {"type": "object", "properties": {}} # No parameters needed from LLM, user_id is injected
}

TOOL_GET_PORTFOLIO_POSITIONS = {
    "name": "get_portfolio_positions",
    "description": "Lists all positions (assets held, quantity, average price) in a specific portfolio of the current user. Requires portfolio identifier. The 'user_id' is automatically inferred.",
    "parameters": {
        "type": "object",
        "properties": {
            "portfolio_name": {"type": "string", "description": "The name of the portfolio. Use if portfolio_id is not known.", "optional": True},
            "portfolio_id": {"type": "integer", "description": "The unique ID of the portfolio. Preferred if known.", "optional": True}
        },
        # LLM should provide at least one, function logic will handle preference. Tool description guides this.
    }
}

TOOL_GET_PORTFOLIO_MARKET_VALUE = {
    "name": "get_portfolio_market_value",
    "description": "Calculates the current total market value of a specific portfolio belonging to the current user. Requires portfolio identifier. The 'user_id' is automatically inferred.",
    "parameters": {
        "type": "object",
        "properties": {
            "portfolio_name": {"type": "string", "description": "The name of the portfolio. Use if portfolio_id is not known.", "optional": True},
            "portfolio_id": {"type": "integer", "description": "The unique ID of the portfolio. Preferred if known.", "optional": True}
        },
    }
}

TOOL_GET_PORTFOLIO_DAILY_CHANGE_PERCENTAGE = {
    "name": "get_portfolio_daily_change_percentage",
    "description": "Calculates the overall 24-hour percentage change of a specific portfolio for the current user. Requires portfolio identifier. The 'user_id' is automatically inferred.",
    "parameters": {
        "type": "object",
        "properties": {
            "portfolio_name": {"type": "string", "description": "The name of the portfolio. Use if portfolio_id is not known.", "optional": True},
            "portfolio_id": {"type": "integer", "description": "The unique ID of the portfolio. Preferred if known.", "optional": True}
        },
    }
}

TOOL_GET_PORTFOLIO_PNL = {
    "name": "get_portfolio_pnl",
    "description": "Calculates the Profit and Loss (realized, unrealized, current market value, cost basis) for a specific portfolio of the current user. Requires portfolio identifier. The 'user_id' is automatically inferred.",
    "parameters": {
        "type": "object",
        "properties": {
            "portfolio_name": {"type": "string", "description": "The name of the portfolio. Use if portfolio_id is not known.", "optional": True},
            "portfolio_id": {"type": "integer", "description": "The unique ID of the portfolio. Preferred if known.", "optional": True}
        },
    }
}


AVAILABLE_TOOLS_SCHEMAS = [
    TOOL_GET_STOCK_PRICE,
    TOOL_GET_CRYPTO_PRICE,
    TOOL_GET_COMPANY_OVERVIEW,
    TOOL_GET_FINANCIAL_NEWS,
    TOOL_EXPLAIN_FINANCIAL_CONCEPT,
    TOOL_GENERAL_WEB_SEARCH,
    TOOL_GET_HISTORICAL_STOCK_DATA,
    TOOL_GET_INTRADAY_STOCK_DATA,
    TOOL_GET_INCOME_STATEMENT,
    TOOL_GET_BALANCE_SHEET,
    TOOL_GET_CASH_FLOW_STATEMENT,
    TOOL_GET_COMPANY_EARNINGS,
    TOOL_GET_ASSET_PRICE_CHANGE_24H,
    TOOL_GET_TICKER_SPECIFIC_NEWS,
    TOOL_LIST_MY_PORTFOLIOS,
    TOOL_GET_PORTFOLIO_POSITIONS,
    TOOL_GET_PORTFOLIO_MARKET_VALUE,
    TOOL_GET_PORTFOLIO_DAILY_CHANGE_PERCENTAGE,
    TOOL_GET_PORTFOLIO_PNL,
]

def get_tool_schemas_for_llm():
    import json
    # Exclude 'optional' field if not OpenAI standard, or ensure it's handled correctly by your LLM
    # For this exercise, keeping it as it might be useful for some models/parsers.
    # If using OpenAI, 'optional' is not a standard field in the function definition schema;
    # optionality is conveyed by not including the parameter in the 'required' list.
    
    # Simplified schemas for LLM if 'optional' field is an issue:
    # Remove 'optional: True' and rely on absence from 'required' list.
    # This step is skipped here to keep the provided structure, assuming the LLM or parser handles 'optional'.
    return json.dumps(AVAILABLE_TOOLS_SCHEMAS, indent=2)