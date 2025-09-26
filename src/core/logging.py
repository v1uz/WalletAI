# src/core/logging.py
import logging
import json
import os
import uuid
from datetime import datetime
from functools import wraps
from typing import Optional

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

def setup_logging(use_sentry: bool = False):
    """Setup logging with optional Sentry integration"""
    
    # Configure Sentry if DSN is provided
    if use_sentry and os.getenv('SENTRY_DSN'):
        try:
            import sentry_sdk
            from sentry_sdk.integrations.asyncio import AsyncioIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration
            
            sentry_sdk.init(
                dsn=os.getenv('SENTRY_DSN'),
                integrations=[
                    AsyncioIntegration(),
                    LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
                ],
                traces_sample_rate=0.1,
                profiles_sample_rate=0.1,
                environment=os.getenv('ENVIRONMENT', 'development')
            )
        except ImportError:
            logging.warning("Sentry SDK not installed, skipping Sentry integration")
    
    # Configure structured logging
    handler = logging.StreamHandler()
    
    # Use simpler format for development
    if os.getenv('ENVIRONMENT') == 'development':
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        formatter = StructuredFormatter()
    
    handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO if os.getenv('DEBUG') != 'true' else logging.DEBUG)
    logger.addHandler(handler)
    
    return logger

def financial_transaction(logger):
    """Decorator for financial transaction error handling"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            transaction_id = str(uuid.uuid4())
            
            logger.info(f"Starting financial transaction: {func.__name__}", 
                       extra={'transaction_id': transaction_id})
            
            try:
                result = await func(*args, **kwargs)
                logger.info(f"Transaction completed: {func.__name__}",
                           extra={'transaction_id': transaction_id})
                return result
                
            except Exception as e:
                logger.error(f"Transaction failed: {func.__name__}: {str(e)}",
                            exc_info=True,
                            extra={'transaction_id': transaction_id})
                raise
        
        return wrapper
    return decorator