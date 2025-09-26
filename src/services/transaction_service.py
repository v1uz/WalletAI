"""
Transaction business logic for WalletAI.
"""
from decimal import Decimal
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from models.base import Transaction, User, Category, TransactionType

class TransactionService:
    """Service for handling transaction operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_transaction(
        self,
        user_id: int,
        amount: Decimal,
        transaction_type: TransactionType,
        category_id: int,
        description: Optional[str] = None,
        date: Optional[datetime] = None
    ) -> Transaction:
        """Create a new transaction"""
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=transaction_type,
            category_id=category_id,
            description=description,
            date=date or datetime.now()
        )
        
        self.session.add(transaction)
        await self.session.commit()
        await self.session.refresh(transaction)
        
        return transaction
    
    async def get_user_transactions(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
        transaction_type: Optional[TransactionType] = None
    ) -> List[Transaction]:
        """Get user transactions with optional filtering"""
        query = select(Transaction).where(
            Transaction.user_id == user_id
        ).options(selectinload(Transaction.category))
        
        if transaction_type:
            query = query.where(Transaction.transaction_type == transaction_type)
        
        query = query.order_by(Transaction.date.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_balance(self, user_id: int) -> Dict[str, Decimal]:
        """Calculate user's balance"""
        # Total income
        income_result = await self.session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == TransactionType.INCOME
                )
            )
        )
        total_income = income_result.scalar() or Decimal('0')
        
        # Total expenses
        expense_result = await self.session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == TransactionType.EXPENSE
                )
            )
        )
        total_expense = expense_result.scalar() or Decimal('0')
        
        return {
            'income': total_income,
            'expense': total_expense,
            'balance': total_income - total_expense
        }
    
    async def get_period_transactions(
        self,
        user_id: int,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> List[Transaction]:
        """Get transactions for a specific period"""
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.date >= start_date
            )
        ).options(selectinload(Transaction.category))
        
        if end_date:
            query = query.where(Transaction.date <= end_date)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_category_spending(
        self,
        user_id: int,
        category_id: int,
        period_days: int = 30
    ) -> Decimal:
        """Get total spending for a category in given period"""
        start_date = datetime.now() - timedelta(days=period_days)
        
        result = await self.session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.category_id == category_id,
                    Transaction.transaction_type == TransactionType.EXPENSE,
                    Transaction.date >= start_date
                )
            )
        )
        
        return result.scalar() or Decimal('0')
    
    async def update_transaction(
        self,
        transaction_id: int,
        user_id: int,
        **kwargs
    ) -> Optional[Transaction]:
        """Update an existing transaction"""
        result = await self.session.execute(
            select(Transaction).where(
                and_(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id
                )
            )
        )
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            return None
        
        for key, value in kwargs.items():
            if hasattr(transaction, key):
                setattr(transaction, key, value)
        
        await self.session.commit()
        await self.session.refresh(transaction)
        
        return transaction
    
    async def delete_transaction(
        self,
        transaction_id: int,
        user_id: int
    ) -> bool:
        """Delete a transaction"""
        result = await self.session.execute(
            select(Transaction).where(
                and_(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id
                )
            )
        )
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            return False
        
        await self.session.delete(transaction)
        await self.session.commit()
        
        return True
    
    async def get_spending_by_categories(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Decimal]:
        """Get spending breakdown by categories"""
        query = select(
            Category.name,
            func.sum(Transaction.amount)
        ).join(
            Transaction, Transaction.category_id == Category.id
        ).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE
            )
        )
        
        if start_date:
            query = query.where(Transaction.date >= start_date)
        if end_date:
            query = query.where(Transaction.date <= end_date)
        
        query = query.group_by(Category.name)
        
        result = await self.session.execute(query)
        return dict(result.all())