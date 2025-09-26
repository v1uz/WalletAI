# src/services/ai_categorization.py
import asyncio
import aiohttp
from decimal import Decimal
import json
from typing import Optional, Dict, List
from asyncio import Semaphore
from time import time

class RateLimiter:
    def __init__(self, max_requests: int, window: int):
        self.max_requests = max_requests
        self.window = window
        self.requests = []
        self.semaphore = Semaphore(max_requests)
    
    async def acquire(self):
        async with self.semaphore:
            now = time()
            # Remove old requests outside the window
            self.requests = [req_time for req_time in self.requests if now - req_time < self.window]
            
            if len(self.requests) >= self.max_requests:
                # Wait until the oldest request expires
                sleep_time = self.window - (now - self.requests[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            
            self.requests.append(now)

class AICategorizationService:
    def __init__(self, api_key: str, redis_cache):
        self.api_key = api_key
        self.cache = redis_cache
        self.rate_limiter = RateLimiter(max_requests=100, window=60)
        
    async def categorize_transaction(self, description: str, amount: Decimal) -> Dict:
        """Categorize transaction using GPT-4 with caching"""
        
        # Check cache first
        cache_key = f"category:{hash(description + str(amount))}"
        cached = await self.cache.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Rate limiting
        await self.rate_limiter.acquire()
        
        # Prepare GPT request
        messages = [
            {
                "role": "system",
                "content": """You are a financial categorization expert. Categorize transactions into:
                - Housing (rent, mortgage, utilities)
                - Transportation (fuel, public transit, maintenance)
                - Food & Dining (groceries, restaurants)
                - Healthcare (medical, dental, insurance)
                - Entertainment (movies, hobbies, subscriptions)
                - Shopping (clothing, electronics, general retail)
                - Financial (bank fees, investments, loans)
                - Business (office supplies, professional services)
                - Other (miscellaneous expenses)
                
                Respond with JSON containing: category, subcategory, confidence (0-1), merchant (if identifiable)"""
            },
            {
                "role": "user",
                "content": f"Transaction: {description}, Amount: ${amount}"
            }
        ]
        
        functions = [{
            "type": "function",
            "function": {
                "name": "categorize_expense",
                "description": "Categorize a financial transaction",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["Housing", "Transportation", "Food & Dining", 
                                    "Healthcare", "Entertainment", "Shopping", 
                                    "Financial", "Business", "Other"]
                        },
                        "subcategory": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "merchant": {"type": "string"}
                    },
                    "required": ["category", "confidence"]
                },
                "strict": True
            }
        }]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "functions": functions,
                    "function_call": "auto",
                    "temperature": 0.3
                }
            ) as response:
                result = await response.json()
                
                if 'choices' in result and result['choices'][0].get('message', {}).get('function_call'):
                    categorization = json.loads(
                        result['choices'][0]['message']['function_call']['arguments']
                    )
                    
                    # Cache for 24 hours
                    await self.cache.setex(cache_key, 86400, json.dumps(categorization))
                    return categorization
                
                # Fallback to basic categorization
                return {"category": "Other", "confidence": 0.5}