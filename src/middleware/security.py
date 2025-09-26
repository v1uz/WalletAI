# src/middleware/security.py
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
import hashlib
import hmac
import time
import redis.asyncio as redis
from typing import Callable, Dict, Any, Awaitable

class SecurityMiddleware(BaseMiddleware):
    def __init__(self, redis_client, encryption_key: str):
        self.redis = redis_client
        self.encryption_key = encryption_key
        self.rate_limiter = {}
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)
        
        # Rate limiting
        if not await self._check_rate_limit(user.id):
            await event.answer("⚠️ Too many requests. Please wait a moment.")
            return
        
        # Input sanitization
        if hasattr(event, 'text'):
            event.text = self._sanitize_input(event.text)
        
        # Session validation
        if not await self._validate_session(user.id):
            await event.answer("🔒 Session expired. Please use /start to begin.")
            return
        
        # Update last activity
        await self._update_activity(user.id)
        
        return await handler(event, data)
    
    async def _check_rate_limit(self, user_id: int) -> bool:
        """Implement sliding window rate limiting"""
        key = f"rate_limit:{user_id}"
        current_time = time.time()
        window = 60  # 1 minute window
        max_requests = 20
        
        # Get current window data
        pipeline = self.redis.pipeline()
        pipeline.zremrangebyscore(key, 0, current_time - window)
        pipeline.zcard(key)
        pipeline.zadd(key, {str(current_time): current_time})
        pipeline.expire(key, window)
        results = await pipeline.execute()
        
        request_count = results[1]
        return request_count < max_requests