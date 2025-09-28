# handlers/balance.py
import logging  # Added missing import
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from models.base import User, Transaction

# Initialize logger
logger = logging.getLogger(__name__)

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
                Transaction.transaction_type == "income"  # Changed from enum
            )
        )
    )
    total_income = income_result.scalar() or 0
    
    # Total expenses
    expense_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user.id,
                Transaction.transaction_type == "expense"  # Changed from enum
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
                Transaction.transaction_type == "expense",  # Changed from enum
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
                Transaction.transaction_type == "expense",  # Changed from enum
                Transaction.date >= start_of_day
            )
        )
    )
    today_expense = today_expense_result.scalar() or 0
    
    # Calculate balance
    balance = total_income - total_expense
    
    # Get currency symbol
    def get_currency_symbol(currency: str) -> str:
        """Get currency symbol from currency code"""
        symbols = {
            'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
            'RUB': '₽', 'INR': '₹', 'BRL': 'R$', 'CAD': 'C$'
        }
        return symbols.get(currency, currency)
    
    currency_symbol = get_currency_symbol(user.currency)
    
    # Format message
    balance_emoji = "🟢" if balance >= 0 else "🔴"
    
    # Add buttons for transaction history
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Transaction History", callback_data="transaction_history")],
        [InlineKeyboardButton(text="➕ Add Transaction", callback_data="add_transaction")]
    ])
    
    await message.answer(
        f"💰 <b>Your Financial Summary</b>\n\n"
        f"{balance_emoji} Balance: <b>{currency_symbol}{balance:.2f}</b>\n\n"
        f"📊 <b>All Time:</b>\n"
        f"💚 Total Income: {currency_symbol}{total_income:.2f}\n"
        f"💔 Total Expenses: {currency_symbol}{total_expense:.2f}\n\n"
        f"📅 <b>This Month:</b>\n"
        f"💸 Spent: {currency_symbol}{month_expense:.2f}\n\n"
        f"📆 <b>Today:</b>\n"
        f"💸 Spent: {currency_symbol}{today_expense:.2f}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def show_balance_for_user(user_telegram_id: int, message: Message, session: AsyncSession):
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
        # Total income
        income_result = await session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.transaction_type == "income"
                )
            )
        )
        total_income = income_result.scalar() or 0
        
        # Total expenses
        expense_result = await session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.transaction_type == "expense"
                )
            )
        )
        total_expense = expense_result.scalar() or 0
        
        balance = total_income - total_expense
        
        # Get currency symbol
        def get_currency_symbol(currency: str) -> str:
            """Get currency symbol from currency code"""
            symbols = {
                'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
                'RUB': '₽', 'INR': '₹', 'BRL': 'R$', 'CAD': 'C$'
            }
            return symbols.get(currency, currency)
        
        currency_symbol = get_currency_symbol(user.currency)
        
        # Format balance message
        balance_emoji = "🟢" if balance >= 0 else "🔴"
        
        balance_text = (
            f"💰 <b>Your Balance</b>\n\n"
            f"{balance_emoji} Current Balance: <b>{currency_symbol}{balance:.2f}</b>\n\n"
            f"💚 Total Income: {currency_symbol}{total_income:.2f}\n"
            f"💔 Total Expenses: {currency_symbol}{total_expense:.2f}"
        )
        
        # Add button for transaction history
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 Transaction History", callback_data="transaction_history")],
            [InlineKeyboardButton(text="➕ Add Transaction", callback_data="add_transaction")]
        ])
        
        await message.answer(balance_text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing balance for user {user_telegram_id}: {e}")
        await message.answer("❌ Error retrieving balance. Please try again.")