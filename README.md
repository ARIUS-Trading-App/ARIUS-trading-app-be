# ARIUS - AI Trading Assistant (Backend)

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Ollama-llama3-lightgrey.svg)](https://ollama.com/)
[![Pinecone](https://img.shields.io/badge/Vector%20DB-Pinecone-blueviolet.svg)](https://www.pinecone.io/)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy-red.svg)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](../LICENSE)

</div>

## 1\. System Architecture and Core Components

This repository contains the backend for a tool-augmented LLM agent designed for financial analysis and portfolio management. The system is architected as an asynchronous FastAPI application that orchestrates a series of services to provide a stateful, multi-turn conversational experience. The core of the application is a custom-built, self-correcting reasoning agent.

### 1.1. Agentic Core: Self-Correcting Reasoning Loop

The agent operates on a multi-step reasoning loop, analogous to a ReAct (Reason-Act) framework, to deconstruct complex user queries into a sequence of executable actions.

  - **Iterative Reasoning**: For each user query, the agent enters a loop with a fixed maximum number of iterations (`MAX_TOOL_ITERATIONS`) to prevent runaways. It analyzes the original query, the full conversation history, and all data gathered within the current turn to decide the next action: execute a tool or synthesize a final response.
  - **Self-Correction Mechanism**: The loop is stateful and self-correcting. If the agent attempts a redundant tool call (identical function name and arguments to one already executed in the turn), the system intercepts it. It then provides explicit, text-based feedback to the LLM, instructing it to select a different tool or proceed to the final answer. This same feedback mechanism is used to inform the agent of tool execution errors (e.g., API failures, invalid symbols), allowing it to recover by trying an alternative tool or asking for clarification.

### 1.2. Dynamic Prompt Engineering

The agent's reasoning is guided by a dynamically constructed system prompt that is rebuilt at each step of the reasoning loop. This prompt aggregates all necessary context for the LLM to make an informed decision.

  - **Context Aggregation**: The primary system prompt is injected with several key pieces of real-time information:
      - **User Profile**: A summary of the user's trading experience, risk appetite, and investment goals is retrieved from the database and included in the prompt, enabling personalized and risk-aware responses.
      - **Tool Schemas**: The complete JSON schemas for all **19 available tools**, including function names, descriptions, and argument specifications, are provided to the LLM.
      - **Iterative State**: The outputs of all previously executed tools within the current conversational turn are appended to the context, allowing the agent to build upon gathered information.
  - **Synthesis Stage**: Once the loop concludes, a separate, final prompt is used for synthesis. This prompt instructs the LLM to formulate a single, cohesive natural-language answer based on the full history and all accumulated tool outputs, while explicitly forbidding it from mentioning the internal tool-use mechanics (e.g., "the tool returned...").

### 1.3. Tool Execution and Management

The agent's capabilities are defined by a suite of 19 discrete, function-callable tools.

  - **Available Tools**: The toolset covers financial data retrieval, portfolio management, and knowledge lookups. Functions include: `get_stock_price`, `get_crypto_price`, `get_company_overview`, `get_financial_news`, `get_historical_stock_data`, `get_income_statement`, `get_balance_sheet`, `explain_financial_concept`, `list_my_portfolios`, `get_portfolio_positions`, `get_portfolio_pnl`, and `general_web_search`.
  - **Runtime Argument Validation**: To ensure robustness against LLM hallucinations, the system does not trust the generated tool arguments. It uses Python's `inspect` module to introspect the target function's signature at runtime. It validates that all required arguments are present, discards extraneous ones, and attempts to coerce types (e.g., string to integer) before execution.
  - **Constrained JSON I/O**: The agent is prompted to generate tool calls in a strict JSON format. A dedicated parsing function (`_clean_llm_json_response`) uses a series of regular expressions to reliably extract the JSON object from the raw LLM output, stripping markdown code blocks and other extraneous text.

### 1.4. Hybrid Retrieval-Augmented Generation (RAG)

The system employs a multi-source RAG strategy to ground the LLM in both real-time data and a static knowledge base.

  - **Structured Data RAG**: The primary RAG mechanism is through tool calls that fetch real-time, structured data from external APIs (a wrapper around `yfinance`) and the application's internal PostgreSQL database (user portfolios, transaction history).
  - **Unstructured Data RAG**:
      - **Vector Database**: The system uses a Pinecone index as its vectorized database for unstructured knowledge.
      - **Ingestion Pipeline**: An ingestion script processes text documents (`.txt`, `.md`). It employs a sliding-window chunking strategy (`utils.text_processing.chunk_text`) to split documents into overlapping segments suitable for embedding. Each chunk is then converted into a vector using a `SentenceTransformer` model (`all-MiniLM-L6-v2`) and upserted into Pinecone in batches.
      - **Hybrid Retrieval Strategy**: Tools like `explain_financial_concept` first perform a similarity search against the Pinecone index. If the retrieved context is insufficient or not found, the tool automatically falls back to using the `general_web_search` tool to find an answer from the web.

### 1.5. Performance and Concurrency

The system is designed for low latency and efficient handling of concurrent requests.

  - **Hybrid-Model Routing**: Simple, conversational queries (e.g., "hello", "thank you") are identified via keyword matching. These queries are routed to a smaller, faster LLM (`settings.SMALLER_LLM_MODEL`), bypassing the computationally expensive reasoning loop. This strategy minimizes both latency and operational cost for non-complex interactions.
  - **TTL Caching**: All tool execution results are cached in memory for 60 seconds using `cachetools.TTLCache`. The cache key is a hashable tuple of the tool name and its sorted arguments, ensuring that repeated, identical data requests are served instantly without redundant API calls.
  - **Asynchronous Architecture**: The entire API is built on FastAPI. To prevent blocking the event loop, synchronous, I/O-bound libraries (`ollama`, `yfinance`, `pinecone-client`) are run in a separate thread pool using `asyncio.run_in_executor`. For real-time output, the blocking Ollama stream response is handled in a dedicated thread that pushes tokens into an `asyncio.Queue`, allowing the main async application to stream data back to the client token-by-token.

## 2\. Technical Stack

  - **Framework**: FastAPI
  - **LLM Orchestration**: Custom Agentic Loop, Ollama
  - **Vector DB & Embeddings**: Pinecone, Sentence-Transformers
  - **Database & ORM**: PostgreSQL, SQLAlchemy, Alembic
  - **Data & Analysis**: `yfinance` wrapper, Pandas, NLTK
  - **Authentication**: JWT (JOSE), Passlib
  - **Core Libraries**: Pydantic, `python-dotenv`, `cachetools`

## 3\. Project Structure

```
.
├── alembic/              # Database migration scripts
├── app/
│   ├── core/             # Application settings and dependencies
│   ├── crud/             # Database CRUD operations
│   ├── db/               # SQLAlchemy session and model base
│   ├── llm_tools/        # Schemas and functions for all agent tools
│   ├── models/           # SQLAlchemy ORM table definitions
│   ├── routes/           # FastAPI API endpoint routers
│   ├── schemas/          # Pydantic data validation models
│   ├── services/         # Core business logic and service abstractions
│   │   ├── rag_service.py          # Core agent, reasoning loop, and prompt logic
│   │   ├── llm_provider_service.py # Ollama client wrapper and streaming logic
│   │   ├── vector_db_service.py    # Pinecone client wrapper and RAG logic
│   │   └── ...
│   ├── utils/            # Helper functions (e.g., text chunking)
│   └── main.py           # FastAPI application entry point
└── .env                  # Environment variable configuration (local)
```

## 4\. Configuration and Execution

### Prerequisites

  - Python 3.10+
  - PostgreSQL Server
  - Ollama installed and running. Pull required models:
    ```sh
    ollama pull llama3.2:3b
    ```
  - API keys for Pinecone and Tavily Search.

### Setup

1.  **Clone the repository.**

2.  **Create and populate `.env` file** in the project root. Use `.env.example` as a template for required variables.

3.  **Install dependencies:**

    ```sh
    pip install -r requirements.txt
    ```

4.  **Apply database migrations:**

    ```sh
    alembic upgrade head
    ```

5.  **Run the application:**

    ```sh
    uvicorn app.main:app --reload
    ```

    The API will be accessible at `http://127.0.0.1:8000`.

### Data Ingestion

To populate the vector database for the `explain_financial_concept` tool, place knowledge documents (`.txt`, `.md`) in a directory and run the ingestion script after updating the source path within the file.

```sh
python app/utils/ingest_knowledge_base.py
```
