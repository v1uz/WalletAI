from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Simple settings class without pydantic to avoid import issues"""
    
    def __init__(self):
        # Bot configuration - REQUIRED
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        
        # Database - with SQLite as default for easy start
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./walletai.db")
        
        # Redis - optional for development
        self.REDIS_URL = os.getenv("REDIS_URL", None)
        self.USE_REDIS = os.getenv("USE_REDIS", "false").lower() == "true"
        
        # OpenAI - optional initially
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
        
        # Security - will generate if not provided
        self.ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", None)
        
        # Environment
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        self.DEBUG = os.getenv("DEBUG", "true").lower() == "true"
        
        # Validate bot token
        if not self.BOT_TOKEN:
            raise ValueError(
                "\n\n❌ BOT_TOKEN is not set!\n"
                "Please add your bot token to .env file:\n"
                "BOT_TOKEN=your_bot_token_here\n"
            )

# Create settings instance
settings = Settings()