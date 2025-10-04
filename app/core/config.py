from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    """Defines and validates all environment variables for the application.
    
    Pydantic automatically reads variables from the environment or a .env file,
    validates their types, and provides default values if they are not set.
    """
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./default.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a-secret-key")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "your-sendgrid-api-key")
    EMAIL_SENDER: str = os.getenv("EMAIL_SENDER", "no-reply@yourdomain.com")
    
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3.2:3b")
    SMALLER_LLM_MODEL: str = os.getenv("SMALLER_LLM_MODEL", "llama3.2:3b")
    
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")

    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "trading-app-rag")
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    
    ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT: str = os.getenv("ALPHA_VANTAGE_CRYPTO_MARKET_DEFAULT", "USD")
    FINNHUB_CRYPTO_EXCHANGE_DEFAULT: str = os.getenv("FINNHUB_CRYPTO_EXCHANGE_DEFAULT", "BINANCE")
    FINNHUB_FX_PROVIDER_DEFAULT: str = os.getenv("FINNHUB_FX_PROVIDER_DEFAULT", "OANDA")


    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "your-newsapi-key")

    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()