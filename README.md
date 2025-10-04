<div align="center">

# ARIUS — AI Trading Assistant (Backend)

[](https://www.python.org/)
[](https://fastapi.tiangolo.com/)
[](https://ollama.com/)
[](https://www.pinecone.io/)
[](https://www.sqlalchemy.org/)
[](https://www.google.com/search?q=../LICENSE)

</div>

High-performance, asynchronous backend powering the **Arius AI Trading Assistant**. This isn't just a simple REST API; it's a sophisticated system built around a custom LLM agent that leverages advanced techniques like **Retrieval-Augmented Generation (RAG)**, dynamic **function calling**, and intelligent **caching** to provide a stateful, tool-augmented conversational experience.

The core of the application is a **ReAct-style agent** that can reason, plan, and execute a wide range of financial data queries, portfolio management actions, and knowledge retrievals in real-time.

-----

## ✨ Key Features & Technical Highlights

This backend was engineered with a focus on intelligence, performance, and robustness. Here are some of the key technical features that make it stand out.

### LLM Agentic Workflow (ReAct Engine) 🧠

Instead of simple prompt-response chains, the chatbot is powered by a multi-step **Reason-Act (ReAct) agent**. This enables the LLM to perform complex tasks by breaking them down into a series of sub-problems and executing tools to solve them.

1.  **Dynamic Reasoning Loop:** For each user query, the agent enters an iterative loop. In each step, it analyzes the original query, the full conversation history, and all the data it has gathered so far. It then "reasons" about the next logical step—either calling another tool to get missing information or synthesizing a final answer.
2.  **Function Calling & Tool Use:** The agent has access to a rich set of over 15 financial tools (see `tool_functions.py`). It dynamically selects the appropriate tool and infers the required arguments (e.g., extracting `"Apple"` -\> `symbol="AAPL"`). It's also smart enough to chain tools; for instance, it might first use `list_my_portfolios` to clarify which portfolio the user means before calling `get_portfolio_pnl` on the correct one.
3.  **Contextual Synthesis:** Once the agent determines it has gathered all necessary information from its tools, it enters a final synthesis step. It compiles all tool outputs into a comprehensive context and prompts the LLM one last time to generate a fluid, natural language response, avoiding technical jargon like *"the tool returned..."*.
4.  **Cost & Latency Optimization:** Simple conversational queries (greetings, thanks) are intelligently routed to a smaller, faster LLM (`phi3` or similar), bypassing the complex agentic loop. This reduces operational costs and significantly improves response time for casual interactions.

### Advanced RAG & Knowledge Retrieval 📚

The agent's intelligence is augmented through a hybrid **Retrieval-Augmented Generation (RAG)** system that combines real-time data with a static knowledge base.

  * **Structured Data RAG via Tools:** The primary RAG method is through the agent's function-calling capability. It retrieves fresh, structured data from financial APIs (`yfinance` wrapper) and user-specific database records (portfolios, positions).
  * **Unstructured Data RAG via Vector DB:** For explaining financial concepts, the agent queries a **Pinecone vector database**. Our ingestion pipeline (`ingest_docs.py`) chunks financial documents, generates embeddings using `Sentence-Transformers`, and stores them in Pinecone. The `explain_financial_concept` tool then performs a similarity search on this knowledge base to provide detailed, context-aware explanations.

### Intelligent Caching Strategy ⚡

To minimize latency and avoid redundant API calls, the `RAGService` implements a smart caching layer for tool executions.

  * **Time-to-Live (TTL) Cache:** We use `cachetools.TTLCache` to store the results of tool calls for 60 seconds. If the LLM requests the exact same data within this window (e.g., asking for AAPL's price twice in a row), the result is served instantly from memory.
  * **Robust Cache Keying:** The cache key is a tuple of the `tool_name` and a frozenset of its arguments. This ensures that `get_stock_price(symbol='AAPL')` and `get_stock_price(symbol='GOOG')` are treated as distinct calls.

### Hybrid Time-Series Forecasting 📈

The backend provides personalized, short-term price forecasts that blend quantitative models with alternative data.

  * **Prophet Model:** We use Meta's `prophet` library to model historical price data, capturing trends and seasonalities.
  * **Sentiment as a Regressor:** To improve the model's predictive power, we don't just rely on price. We compute a daily **sentiment score** for the asset (from news and tweets using NLTK's VADER) and include it as an **exogenous regressor** in the Prophet model. This allows the forecast to react to market sentiment.
  * **Personalized Confidence Intervals:** The forecast isn't one-size-fits-all. The confidence bands (`yhat_lower`, `yhat_upper`) are dynamically adjusted based on the user's saved **risk appetite** and **investment goals**, providing a forecast tailored to their profile.

### Asynchronous Performance & Concurrency 🚀

The entire application is built on **FastAPI** and designed to be fully asynchronous to handle concurrent users efficiently.

  * **Bridging Blocking Libraries:** Many core data libraries (`yfinance`, `pinecone-client`, `ollama`) are blocking. We safely integrate them into our async event loop using `asyncio.run_in_executor`, which runs them in a separate thread pool to prevent blocking the entire application.
  * **Concurrent Fan-Out:** When calculating portfolio values, the system fetches quotes for all positions *concurrently* using `asyncio.gather`, dramatically speeding up the process for large portfolios.
  * **Streaming Architecture:** The connection to the Ollama LLM is managed in a separate thread, feeding tokens into an `asyncio.Queue`. This allows the main application to stream responses back to the user token-by-token over WebSocket or HTTP, providing a responsive, real-time feel.

-----

## 🧱 Tech Stack

  * **Framework:** FastAPI, Uvicorn
  * **LLM Orchestration:** Custom ReAct Agent, Ollama (`llama3`, `phi3`)
  * **RAG & Embeddings:** Pinecone (Vector DB), Sentence-Transformers, NLTK
  * **Database & ORM:** PostgreSQL, SQLAlchemy (Async)
  * **Data & Analysis:** `yfinance` wrapper, Pandas, Prophet
  * **Authentication:** JWT Tokens, Passlib
  * **Tooling:** Pydantic, `python-dotenv`, `cachetools`


-----

## 🗂️ Project Structure

The codebase is organized into a clean, service-oriented architecture, separating concerns like API routing, business logic, and data access.

```txt
fml-llm-project-be/
├── alembic/            # Database migration scripts (Alembic)
├── app/
│   ├── core/           # Configuration, settings, and core dependencies
│   ├── crud/           # Database Create, Read, Update, Delete (CRUD) operations
│   ├── db/             # Database session management and base models
│   ├── llm_tools/      # Schemas and implementation of tools for the LLM
│   ├── models/         # SQLAlchemy ORM models (database table definitions)
│   ├── routes/         # FastAPI routers containing API endpoints
│   ├── schemas/        # Pydantic models for data validation and serialization
│   ├── services/       # Core business logic for each domain
│   │   ├─ rag_service.py         # The core ReAct agent and RAG logic
│   │   ├─ llm_provider_service.py# Wrapper for Ollama communication
│   │   ├─ financial_data_service.py # Wrapper for yfinance API
│   │   ├─ vector_db_service.py   # Wrapper for Pinecone operations
│   │   ├─ prediction_service.py  # Prophet forecasting logic
│   │   └─ portfolio_pnl_service.py# FIFO P&L calculation logic
│   ├── utils/          # Utility functions (e.g., text processing)
│   └── main.py         # FastAPI application entry point
├── data/               # Local data storage (e.g., NLTK downloads)
├── requirements.txt    # Project dependencies
└── alembic.ini         # Alembic configuration file
```

-----

## ⚙️ Configuration & Setup

1.  **Prerequisites:**

      * Python 3.10+
      * PostgreSQL database
      * Ollama running locally with `llama3` and `phi3` models pulled.
      * API keys for Pinecone and Tavily Search.

2.  **Environment Variables:**
    Create a `.env` file in the root directory and populate it based on `.env.example`.

    ```bash
    # .env
    DATABASE_URL="postgresql+asyncpg://user:password@host:port/dbname"
    SECRET_KEY="..."
    OLLAMA_HOST="http://localhost:11434"
    LLM_MODEL="llama3"
    SMALLER_LLM_MODEL="phi3"
    PINECONE_API_KEY="..."
    PINECONE_ENVIRONMENT="..." # e.g., "us-east-1"
    TAVILY_API_KEY="..."
    # ... and other settings
    ```

3.  **Installation & Running:**

    ```bash
    # Clone the repo and navigate to the api directory
    cd api

    # Create a virtual environment and activate it
    python -m venv venv
    source venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt

    # Apply database migrations
    alembic upgrade head

    # Run the development server
    uvicorn app.main:app --reload
    ```

    The API will be available at `http://localhost:8000`.

4.  **Ingest Knowledge Base Documents:**
    To enable the `explain_financial_concept` tool, place your `.txt` or `.md` files in a designated folder and run the ingestion script.

    ```bash
    # (Update the path in the script first)
    python scripts/ingest_docs.py
    ```

-----

## 📡 Key API Endpoints

  * `/users/`: User creation and profile management.
  * `/auth/`: JWT token-based authentication.
  * `/portfolios/`: CRUD operations for portfolios and positions.
  * `/transactions/`: Log and view buy/sell transactions.
  * `/chat/`: The main endpoint for interacting with the Arius AI assistant.
  * `/data/`: Endpoints for direct financial data queries (quotes, history, etc.).
  * `/forecast/`: Access to the personalized time-series forecasts.

-----

## 🤝 Contributing

This is a personal project for my portfolio, but feel free to open issues for bugs or feature suggestions.

## 📄 License

Licensed under the **GPL-3.0**. See the `LICENSE` file for details.
