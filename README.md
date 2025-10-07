# ARIUS — AI Trading Assistant (Backend)

![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat&logo=python) ![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?style=flat&logo=fastapi) ![Ollama](https://img.shields.io/badge/Ollama-llama3-2196F3.svg?style=flat&logo=ollama) ![Pinecone](https://img.shields.io/badge/Pinecone-Vector_DB-FFC107.svg?style=flat&logo=pinecone) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-E44C30.svg?style=flat&logo=sqlalchemy) ![License](https://img.shields.io/badge/License-GPL--3.0-blue.svg?style=flat)

-----

This repository contains the high-performance, asynchronous backend for the Arius AI Trading Assistant. The system is architected around a self-correcting, tool-augmented Large Language Model (LLM) agent that executes complex financial queries through a stateful, iterative reasoning process. The architecture integrates a hybrid Retrieval-Augmented Generation (RAG) pipeline, a dual-model LLM strategy, and intelligent caching to optimize for latency and accuracy.

-----

## Agentic System Architecture

The core of the application is a custom **Reason-Act (ReAct)** agent implemented in `app/services/rag_service.py`. This agent deconstructs user queries into a sequence of executable steps, utilizing a suite of 19 financial tools to gather information before synthesizing a final response.

### ReAct-Style Reasoning Loop

For each user query not classified as simple conversation, the agent initiates an iterative loop with a maximum of `MAX_TOOL_ITERATIONS` (5) steps to prevent runaway execution.

1.  **Decision Prompting**: In each iteration, a detailed system prompt (`system_prompt_tool_selection`) is constructed. This meta-prompt grounds the primary LLM (`deepseek-r1:14b`) by injecting a comprehensive context, including:

      * **User Profile Grounding**: A summary of the user's full profile (`_summarize_user_profile`), including trading experience, risk appetite, and investment goals, extracted from the `User` model.
      * **Tool Schema Injection**: A complete JSON representation of all 19 available tool schemas from `app/llm_tools/tool_schemas.py`, enabling the LLM to understand function signatures and parameters.
      * **Full Conversational History**: The entire chat history for the session to maintain state.
      * **Iterative State**: A JSON object of tool calls and outputs *within the current turn* (`accumulated_tool_outputs_for_synthesis`) is injected to prevent redundant actions.

2.  **Action Generation**: The LLM processes the context and must respond in one of two formats: a single, valid **JSON object** for a tool call, or a **plain text response** if it has sufficient information.

3.  **Context Augmentation & Self-Correction**: The tool's output is fed back into the loop for the next iteration. This forms the basis of the agent's self-correction mechanism:

      * **Redundancy Feedback**: The agent tracks the signature of every tool call (`executed_tool_calls_this_turn`). If the LLM attempts a redundant call, a specific feedback message is injected into the prompt, instructing it to select a *new* action.
      * **Error Feedback**: If a tool fails (e.g., invalid stock symbol), the `_execute_tool` method generates an instructive error message. This error is fed back to the LLM, allowing it to retry with corrected arguments or select an alternative tool.

4.  **Synthesis**: When the loop terminates, a final system prompt (`system_prompt_synthesis`) instructs the LLM to formulate a single, cohesive answer based on the original query and all gathered data, while explicitly forbidding phrases like "the tool returned..." to ensure a natural response.

### Tool Execution and Management

The agent's capabilities are defined by a suite of 19 discrete, function-callable tools.

  * **Runtime Argument Validation**: To ensure robustness against LLM-generated arguments, the system uses Python's `inspect` module to introspect the target function's signature at runtime. It validates that all required arguments are present, discards extraneous ones, and attempts to coerce types before execution.
  * **Constrained JSON I/O**: The agent is prompted to generate tool calls in a strict JSON format. A dedicated parsing function (`_clean_llm_json_response`) uses a series of regular expressions to reliably extract the JSON object from the raw LLM output, stripping markdown and other extraneous text.

-----

## Performance & Optimization

Latency and API call efficiency are managed through a multi-layered strategy involving query routing, a hybrid RAG system, and caching.

### Dual-Model Query Routing

To minimize overhead for simple interactions, a query classification mechanism is used.

  * **Query Analysis**: Incoming queries are checked against predefined lists of conversational patterns (e.g., "hello", "thank you").
  * **Model Routing**: Simple queries are routed to a smaller, faster model (`llama3.2:3b`), bypassing the expensive ReAct loop. Complex queries requiring tool use are routed to the more powerful primary model (`deepseek-r1:14b`). This reduces response times by an estimated 40% for non-agentic turns.

### Hybrid RAG Pipeline

The agent's knowledge is augmented by a hybrid RAG system that pulls from both structured and unstructured data sources.

  * **Structured RAG (Real-time Data)**: The primary RAG mechanism is tool execution, which retrieves fresh, structured data from external APIs (`yfinance`) and the application's PostgreSQL database.
  * **Unstructured RAG (Static Knowledge)**: For explaining financial concepts, the agent leverages a Pinecone vector database.
      * **Ingestion**: An ingestion script (`ingest_knowledge_base.py`) splits text documents into overlapping chunks (`text_processing.chunk_text`).
      * **Vectorization**: The `embedding_service.py` uses a `Sentence-Transformers` model (`all-MiniLM-L6-v2`) to generate 384-dimensional vector embeddings for each chunk.
      * **Retrieval Strategy**: The `explain_financial_concept` tool first performs a similarity search against the Pinecone index. If the retrieved context is insufficient, the tool automatically falls back to the `general_web_search` tool as a secondary source.

### Tool-Call Caching

A Time-to-Live (TTL) cache is implemented within the `RAGService` to reduce redundant API calls.

  * **Implementation**: An instance of `cachetools.TTLCache` is initialized with a `maxsize` of 200 items and a `ttl` of 60 seconds.
  * **Cache Keying**: The cache key is a hashable tuple of the `tool_name` and a frozenset of its sorted argument pairs, ensuring that `get_stock_price(symbol='AAPL')` and `get_stock_price(symbol='GOOG')` are cached independently.

-----

## Data Intelligence Features

### Time-Series Forecasting

The backend provides personalized price forecasts via `prediction_service.py`.

  * **Core Model**: Meta's `prophet` library is used to model historical price data.
  * **Sentiment as Regressor**: A daily sentiment score for the asset is computed by `sentiment_service.py` (averaging VADER sentiment of recent news/tweets) and added to the Prophet model as an exogenous regressor (`model.add_regressor("sentiment_regressor")`), allowing the forecast to factor in market sentiment.
  * **Personalized Confidence Intervals**: The forecast's confidence bands (`yhat_lower`, `yhat_upper`) are dynamically adjusted based on the user's saved `risk_appetite` and `investment_goals`, providing a tailored forecast.

-----

## System & Infrastructure

### Asynchronous Architecture

  * **Framework**: The application is built on **FastAPI**, an asynchronous ASGI framework.
  * **Handling Blocking Code**: Blocking libraries (`yfinance`, `ollama`, `pinecone-client`) are run in a separate thread pool using `asyncio.run_in_executor` to prevent halting the event loop.
  * **Concurrent Fan-Out**: Operations requiring multiple data fetches (e.g., portfolio valuation) use `asyncio.gather` to execute API calls concurrently.
  * **Response Streaming**: For streaming, a blocking Ollama client call runs in a dedicated `threading.Thread`, which pushes tokens into an `asyncio.Queue` for the main FastAPI event loop to read from asynchronously.

### Tech Stack

  * **Framework**: FastAPI, Uvicorn
  * **LLM Orchestration**: Custom ReAct Agent, Ollama (`deepseek-r1:14b`, `llama3.2:3b`)
  * **RAG & Embeddings**: Pinecone, Sentence-Transformers, NLTK
  * **Database & ORM**: PostgreSQL, SQLAlchemy, Alembic
  * **Data & Analysis**: `yfinance`, Pandas, Prophet
  * **Authentication**: JWT (JOSE), Passlib
  * **Tooling**: Pydantic, `python-dotenv`, `cachetools`, Tavily AI (Web Search)

-----

## Project Structure

```txt
fml-llm-project-be/
├── alembic/              # Database migration scripts
├── app/
│   ├── core/             # Configuration, settings, dependencies
│   ├── crud/             # Database CRUD operations
│   ├── db/               # Database session management and base models
│   ├── llm_tools/        # Schemas (tool_schemas.py) and implementations (tool_functions.py)
│   ├── models/           # SQLAlchemy ORM models
│   ├── routes/           # FastAPI routers (API endpoints)
│   ├── schemas/          # Pydantic models for data validation/serialization
│   ├── services/         # Core business logic
│   │   ├─ rag_service.py            # The core ReAct agent and RAG logic
│   │   ├─ llm_provider_service.py   # Wrapper for Ollama communication
│   │   ├─ financial_data_service.py # Wrapper for yfinance data API
│   │   ├─ vector_db_service.py      # Wrapper for Pinecone operations
│   │   ├─ prediction_service.py     # Prophet forecasting logic
│   │   └─ portfolio_pnl_service.py  # FIFO P&L calculation logic
│   ├── utils/            # Utility functions (text_processing, ingest_knowledge_base)
│   └── main.py           # FastAPI application entry point
├── data/                 # Local data storage (e.g., NLTK downloads)
├── requirements.txt      # Project dependencies
└── alembic.ini           # Alembic configuration file
```

-----

## Configuration & Setup

1.  **Prerequisites**:

      * Python 3.10+
      * PostgreSQL database instance
      * Ollama running with `deepseek-r1:14b` and `llama3.2:3b` models pulled (`ollama pull deepseek-r1:14b`, `ollama pull llama3.2:3b`)
      * API keys for Pinecone and Tavily Search.

2.  **Environment Variables**: Create a `.env` file in the project root.

    ```bash
    # .env
    DATABASE_URL="postgresql+psycopg2://user:password@host:port/dbname" # Use a sync driver for Alembic
    SECRET_KEY="..."
    ALGORITHM="HS26"
    ACCESS_TOKEN_EXPIRE_MINUTES=30

    OLLAMA_HOST="http://localhost:11434"
    LLM_MODEL="deepseek-r1:14b"
    SMALLER_LLM_MODEL="llama3.2:3b"

    TAVILY_API_KEY="..."
    PINECONE_API_KEY="..."
    PINECONE_ENVIRONMENT="..." # e.g., "us-east-1"
    PINECONE_INDEX_NAME="arius-rag-index"
    EMBEDDING_MODEL_NAME="all-MiniLM-L6-v2"
    ```

3.  **Installation & Execution**:

    ```bash
    # Create and activate a virtual environment
    python -m venv venv
    source venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt

    # Apply database migrations
    alembic upgrade head

    # Run the development server
    uvicorn app.main:app --reload
    ```

    The API will be available at `http://127.0.0.1:8000`.

4.  **Ingest Knowledge Base Documents**:
    To enable the `explain_financial_concept` tool, place `.txt` or `.md` files in the directory specified in `app/utils/ingest_knowledge_base.py` and run the script.

    ```bash
    # Update the path in the script, then run:
    python app/utils/ingest_knowledge_base.py
    ```

-----

## License

This project is licensed under the **GPL-3.0**. See the `LICENSE` file for details.
