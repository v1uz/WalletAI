"""
Analytics and reporting service for WalletAI.
"""
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from models.base import Transaction, Category, TransactionType, User

class ReportService:
    """Service for generating financial reports"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def generate_monthly_report(self, user_id: int) -> Dict:
        """Generate monthly financial report"""
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get total income
        income_result = await self.session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == TransactionType.INCOME,
                    Transaction.date >= start_of_month
                )
            )
        )
        total_income = income_result.scalar() or Decimal('0')
        
        # Get total expenses
        expense_result = await self.session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == TransactionType.EXPENSE,
                    Transaction.date >= start_of_month
                )
            )
        )
        total_expense = expense_result.scalar() or Decimal('0')
        
        # Get expenses by category
        category_expenses = await self._get_category_breakdown(
            user_id, start_of_month
        )
        
        # Calculate savings rate
        savings_rate = 0
        if total_income > 0:
            savings_rate = ((total_income - total_expense) / total_income * 100)
        
        # Get daily average
        days_in_month = (now - start_of_month).days + 1
        daily_average = total_expense / days_in_month if days_in_month > 0 else Decimal('0')
        
        return {
            'period': f"{now.strftime('%B %Y')}",
            'total_income': float(total_income),
            'total_expense': float(total_expense),
            'balance': float(total_income - total_expense),
            'savings_rate': float(savings_rate),
            'daily_average': float(daily_average),
            'category_breakdown': category_expenses,
            'days_analyzed': days_in_month
        }
    
    async def generate_weekly_report(self, user_id: int) -> Dict:
        """Generate weekly financial report"""
        now = datetime.now()
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get income and expenses
        income = await self._get_total_amount(
            user_id, TransactionType.INCOME, start_of_week
        )
        expense = await self._get_total_amount(
            user_id, TransactionType.EXPENSE, start_of_week
        )
        
        # Get top expenses
        top_expenses = await self._get_top_transactions(
            user_id, TransactionType.EXPENSE, start_of_week, limit=5
        )
        
        return {
            'period': 'Current Week',
            'start_date': start_of_week.strftime('%Y-%m-%d'),
            'end_date': now.strftime('%Y-%m-%d'),
            'total_income': float(income),
            'total_expense': float(expense),
            'balance': float(income - expense),
            'top_expenses': top_expenses
        }
    
    async def get_spending_trends(self, user_id: int, days: int = 30) -> List[Dict]:
        """Get spending trends for specified period"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get daily spending
        result = await self.session.execute(
            select(
                func.date(Transaction.date).label('date'),
                func.sum(Transaction.amount).label('amount')
            ).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == TransactionType.EXPENSE,
                    Transaction.date >= start_date
                )
            ).group_by(func.date(Transaction.date))
            .order_by(func.date(Transaction.date))
        )
        
        daily_spending = [
            {
                'date': str(row.date),
                'amount': float(row.amount)
            }
            for row in result.all()
        ]
        
        return daily_spending
    
    async def _get_category_breakdown(
        self,
        user_id: int,
        start_date: datetime
    ) -> Dict[str, float]:
        """Get expense breakdown by category"""
        result = await self.session.execute(
            select(
                Category.name,
                Category.icon,
                func.sum(Transaction.amount).label('total')
            ).join(
                Transaction, Transaction.category_id == Category.id
            ).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == TransactionType.EXPENSE,
                    Transaction.date >= start_date
                )
            ).group_by(Category.name, Category.icon)
            .order_by(func.sum(Transaction.amount).desc())
        )
        
        return {
            f"{row.icon} {row.name}": float(row.total)
            for row in result.all()
        }
    
    async def _get_total_amount(
        self,
        user_id: int,
        transaction_type: TransactionType,
        start_date: Optional[datetime] = None
    ) -> Decimal:
        """Get total amount for transaction type"""
        query = select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == transaction_type
            )
        )
        
        if start_date:
            query = query.where(Transaction.date >= start_date)
        
        result = await self.session.execute(query)
        return result.scalar() or Decimal('0')
    
    async def _get_top_transactions(
        self,
        user_id: int,
        transaction_type: TransactionType,
        start_date: Optional[datetime] = None,
        limit: int = 5
    ) -> List[Dict]:
        """Get top transactions by amount"""
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_type == transaction_type
            )
        )
        
        if start_date:
            query = query.where(Transaction.date >= start_date)
        
        query = query.order_by(Transaction.amount.desc()).limit(limit)
        
        result = await self.session.execute(query)
        transactions = result.scalars().all()
        
        return [
            {
                'amount': float(t.amount),
                'description': t.description or 'No description',
                'date': t.date.strftime('%Y-%m-%d %H:%M')
            }
            for t in transactions
        ]
    
    async def get_comparison_report(
        self,
        user_id: int,
        current_period_days: int = 30
    ) -> Dict:
        """Compare current period with previous period"""
        now = datetime.now()
        current_start = now - timedelta(days=current_period_days)
        previous_start = current_start - timedelta(days=current_period_days)
        
        # Current period
        current_expense = await self._get_period_amount(
            user_id, TransactionType.EXPENSE, current_start, now
        )
        current_income = await self._get_period_amount(
            user_id, TransactionType.INCOME, current_start, now
        )
        
        # Previous period
        previous_expense = await self._get_period_amount(
            user_id, TransactionType.EXPENSE, previous_start, current_start
        )
        previous_income = await self._get_period_amount(
            user_id, TransactionType.INCOME, previous_start, current_start
        )
        
        # Calculate changes
        expense_change = 0
        if previous_expense > 0:
            expense_change = ((current_expense - previous_expense) / previous_expense * 100)
        
        income_change = 0
        if previous_income > 0:
            income_change = ((current_income - previous_income) / previous_income * 100)
        
        return {
            'current_expense': float(current_expense),
            'previous_expense': float(previous_expense),
            'expense_change': float(expense_change),
            'current_income': float(current_income),
            'previous_income': float(previous_income),
            'income_change': float(income_change)
        }
    
    async def _get_period_amount(
        self,
        user_id: int,
        transaction_type: TransactionType,
        start_date: datetime,
        end_date: datetime
    ) -> Decimal:
        """Get total amount for a specific period"""
        result = await self.session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == transaction_type,
                    Transaction.date >= start_date,
                    Transaction.date <= end_date
                )
            )
        )
        
        return result.scalar() or Decimal('0')