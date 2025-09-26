# tests/test_transaction_service.py
import pytest
from decimal import Decimal
from datetime import datetime
import factory
from aiogram_tests import MockedBot
from aiogram_tests.handler import MessageHandler
from aiogram_tests.types.dataset import MESSAGE

class TransactionFactory(factory.Factory):
    class Meta:
        model = Transaction
    
    user_id = factory.Sequence(lambda n: n)
    amount = factory.Faker('pydecimal', left_digits=4, right_digits=2, positive=True)
    transaction_type = factory.Iterator([TransactionType.INCOME, TransactionType.EXPENSE])
    description = factory.Faker('sentence')
    date = factory.Faker('date_time')

@pytest.mark.asyncio
async def test_transaction_creation():
    """Test transaction creation with encryption"""
    transaction = TransactionFactory(
        amount=Decimal('100.50'),
        description='Test transaction',
        transaction_type=TransactionType.EXPENSE
    )
    
    assert transaction.amount == Decimal('100.50')
    assert transaction.description == 'Test transaction'
    assert transaction.encrypted_description != 'Test transaction'

@pytest.mark.asyncio
async def test_ai_categorization():
    """Test AI categorization service"""
    service = AICategorizationService(api_key='test', redis_cache=MockRedis())
    
    result = await service.categorize_transaction(
        "Uber ride to airport",
        Decimal('25.00')
    )
    
    assert result['category'] == 'Transportation'
    assert result['confidence'] > 0.7
    assert result['subcategory'] == 'Rideshare'

@pytest.mark.asyncio
async def test_budget_alert():
    """Test budget threshold alerts"""
    budget = Budget(
        user_id=1,
        category_id=1,
        amount_limit=Decimal('1000.00'),
        alert_threshold=0.8
    )
    
    # Add transactions totaling 850 (85% of budget)
    transactions = [
        TransactionFactory(amount=Decimal('850.00'), category_id=1)
    ]
    
    alert_service = NotificationService(bot=MockedBot(), db_session=None, redis=None)
    should_alert = await alert_service.check_budget_threshold(budget, transactions)
    
    assert should_alert is True

@pytest.mark.asyncio
async def test_financial_compliance():
    """Test PCI DSS compliance for sensitive data"""
    # Test card number masking
    handler = SecurityMiddleware(redis_client=None, encryption_key='test')
    masked = handler.mask_card_number("4111111111111111")
    
    assert masked == "****-****-****-1111"
    assert "4111111111111111" not in masked