from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DABASE_URL", "sqlite:///./default.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a-secret-key")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "your-sendgrid-api-key")
    EMAIL_SENDER: str = os.getenv("EMAIL_SENDER", "no-reply@yourdomain.com")
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        
settings = Settings()