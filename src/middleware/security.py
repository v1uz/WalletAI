# src/middleware/security.py
import time
import re
import html
from collections import defaultdict
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

class RateLimiter:
    """Simple rate limiter using sliding window"""
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.user_requests = defaultdict(list)
    
    async def check_rate_limit(self, user_id: int) -> bool:
        """Check if user has exceeded rate limit"""
        current_time = time.time()
        
        # Remove old requests outside the window
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if req_time > current_time - self.window
        ]
        
        # Check if limit exceeded
        if len(self.user_requests[user_id]) >= self.max_requests:
            return False
        
        # Add current request
        self.user_requests[user_id].append(current_time)
        return True

class SecurityMiddleware(BaseMiddleware):
    def __init__(self, encryption_key: Optional[str] = None):
        self.encryption_key = encryption_key
        self.rate_limiter = RateLimiter(max_requests=20, window_seconds=60)
        self.user_sessions = {}
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Get user from event
        user = None
        if hasattr(event, 'from_user'):
            user = event.from_user
        elif data.get("event_from_user"):
            user = data.get("event_from_user")
        
        if not user:
            return await handler(event, data)
        
        # Rate limiting
        if not await self.rate_limiter.check_rate_limit(user.id):
            if isinstance(event, Message):
                await event.answer("⚠️ Too many requests. Please wait a moment.")
            return
        
        # Input sanitization for messages
        if isinstance(event, Message) and event.text:
            event.text = self._sanitize_input(event.text)
        
        # Update user session
        self.user_sessions[user.id] = time.time()
        
        return await handler(event, data)
    
    def _sanitize_input(self, text: str) -> str:
        """Sanitize user input to prevent injections"""
        if not text:
            return text
        
        # Remove any HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Escape special characters
        text = html.escape(text)
        
        # Limit length
        max_length = 4096
        if len(text) > max_length:
            text = text[:max_length]
        
        return text
    
    async def _validate_session(self, user_id: int) -> bool:
        """Check if user session is valid"""
        session_timeout = 3600  # 1 hour
        last_activity = self.user_sessions.get(user_id, 0)
        
        if time.time() - last_activity > session_timeout:
            return False
        return True