# src/bot/factory.py
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import redis.asyncio as redis

class BotFactory:
    def __init__(self, config):
        self.config = config
        self.bot = None
        self.dp = None
        self.db_session = None
        self.redis_client = None
        
    async def create_bot(self) -> Bot:
        """Create bot with security-hardened configuration"""
        return Bot(
            token=self.config.BOT_TOKEN,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                link_preview_is_disabled=True,
                protect_content=True  # Prevent forwarding sensitive data
            )
        )
    
    async def create_dispatcher(self) -> Dispatcher:
        """Initialize dispatcher with Redis FSM storage"""
        self.redis_client = redis.from_url(
            self.config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        
        storage = RedisStorage(
            redis=self.redis_client,
            state_ttl=timedelta(hours=1),
            data_ttl=timedelta(hours=2)
        )
        
        return Dispatcher(storage=storage)
    
    async def setup_database(self):
        """Configure async database with connection pooling"""
        engine = create_async_engine(
            self.config.DATABASE_URL,
            pool_size=25,
            max_overflow=50,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=False
        )
        
        self.db_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        return engine, self.db_session