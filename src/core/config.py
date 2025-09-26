from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    # Bot configuration - REQUIRED
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Database - with SQLite as default for easy start
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./walletai.db")
    
    # Redis - optional for development
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)
    USE_REDIS: bool = os.getenv("USE_REDIS", "false").lower() == "true"
    
    # OpenAI - optional initially
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    
    # Security - will generate if not provided
    ENCRYPTION_KEY: Optional[str] = os.getenv("ENCRYPTION_KEY", None)
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True

# Create settings instance
settings = Settings()

# Validate bot token
if not settings.BOT_TOKEN:
    raise ValueError(
        "\n\n❌ BOT_TOKEN is not set!\n"
        "Please add your bot token to .env file:\n"
        "BOT_TOKEN=your_bot_token_here\n"
    )
