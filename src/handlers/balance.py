from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from models.base import User, Transaction, TransactionType

router = Router()

@router.message(Command("balance"))
async def cmd_balance(message: Message, session: AsyncSession):
    """Show user's balance and summary"""
    # Get user
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("You don't have any transactions yet. Use /add to start!")
        return
    
    # Calculate totals
    # Total income
    income_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user.id,
                Transaction.transaction_type == TransactionType.INCOME
            )
        )
    )
    total_income = income_result.scalar() or 0
    
    # Total expenses
    expense_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user.id,
                Transaction.transaction_type == TransactionType.EXPENSE
            )
        )
    )
    total_expense = expense_result.scalar() or 0
    
    # This month's expenses
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_expense_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user.id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.date >= start_of_month
            )
        )
    )
    month_expense = month_expense_result.scalar() or 0
    
    # Today's expenses
    start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_expense_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user.id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.date >= start_of_day
            )
        )
    )
    today_expense = today_expense_result.scalar() or 0
    
    # Calculate balance
    balance = total_income - total_expense
    
    # Format message
    balance_emoji = "🟢" if balance >= 0 else "🔴"
    
    await message.answer(
        f"💰 <b>Your Financial Summary</b>\n\n"
        f"{balance_emoji} Balance: <b>${balance:.2f}</b>\n\n"
        f"📊 <b>All Time:</b>\n"
        f"💚 Total Income: ${total_income:.2f}\n"
        f"💔 Total Expenses: ${total_expense:.2f}\n\n"
        f"📅 <b>This Month:</b>\n"
        f"💸 Spent: ${month_expense:.2f}\n\n"
        f"📆 <b>Today:</b>\n"
        f"💸 Spent: ${today_expense:.2f}\n\n"
        f"Use /report for detailed breakdown\n"
        f"Use /add to add new transaction",
        parse_mode="HTML"
    )

# Add this function to your handlers/balance.py file

async def show_balance_for_user(user_telegram_id: int, message: Message, session):
    """
    Helper function to show balance for a specific user
    Used when balance is requested from callbacks where message.from_user may not be available
    """
    try:
        # Get user from database
        result = await session.execute(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Please use /start first to initialize your account.")
            return
        
        # Calculate balance
        from services.transaction_service import TransactionService
        
        transaction_service = TransactionService(session)
        balance = await transaction_service.get_user_balance(user.id)
        
        # Get currency symbol
        from main import get_currency_symbol
        currency_symbol = get_currency_symbol(user.currency)
        
        # Format balance message
        balance_text = (
            f"💰 <b>Your Balance</b>\n\n"
            f"Current Balance: <b>{currency_symbol}{balance:.2f}</b>\n"
        )
        
        # Get recent transactions
        recent_transactions = await transaction_service.get_recent_transactions(user.id, limit=5)
        
        if recent_transactions:
            balance_text += "\n<b>Recent Transactions:</b>\n"
            for trans in recent_transactions:
                emoji = "➕" if trans.transaction_type == "income" else "➖"
                balance_text += f"{emoji} {currency_symbol}{trans.amount:.2f} - {trans.description[:30]}\n"
        
        await message.answer(balance_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing balance for user {user_telegram_id}: {e}")
        await message.answer("❌ Error retrieving balance. Please try again.")