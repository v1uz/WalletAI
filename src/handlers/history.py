# handlers/history.py
"""
Transaction History Handler for WalletAI Bot
Shows all user transactions grouped by type
"""

import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import User, Transaction, Category

logger = logging.getLogger(__name__)
router = Router()

def get_currency_symbol(currency: str) -> str:
    """Get currency symbol from currency code"""
    symbols = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
        'RUB': '₽', 'INR': '₹', 'BRL': 'R$', 'CAD': 'C$'
    }
    return symbols.get(currency, currency)

@router.callback_query(F.data == "transaction_history")
async def show_transaction_history(callback: CallbackQuery, session: AsyncSession):
    """Show user's transaction history"""
    try:
        await callback.answer()
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ User not found. Please use /start")
            return
        
        # Get all transactions with categories
        transactions_result = await session.execute(
            select(Transaction, Category)
            .join(Category, Transaction.category_id == Category.id, isouter=True)
            .where(Transaction.user_id == user.id)
            .order_by(desc(Transaction.date))
        )
        
        transactions = transactions_result.all()
        
        if not transactions:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Back", callback_data="show_balance")]
            ])
            
            await callback.message.edit_text(
                "📊 <b>Transaction History</b>\n\n"
                "No transactions yet.\n"
                "Use /add to add your first transaction!",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return
        
        # Separate income and expense transactions
        income_transactions = []
        expense_transactions = []
        
        for trans, category in transactions:
            if trans.transaction_type == "income":
                income_transactions.append((trans, category))
            else:
                expense_transactions.append((trans, category))
        
        # Format message
        currency_symbol = get_currency_symbol(user.currency)
        message_text = "📊 <b>Transaction History</b>\n\n"
        
        # Income section
        if income_transactions:
            message_text += "💰 <b>INCOME</b>\n"
            message_text += "━━━━━━━━━━━━━━\n"
            
            total_income = 0
            for trans, category in income_transactions:
                cat_name = category.name if category else "No category"
                cat_icon = category.icon if category and category.icon else "📁"
                
                date_str = trans.date.strftime("%d.%m.%Y")
                
                message_text += f"➕ <b>{currency_symbol}{trans.amount:.2f}</b>\n"
                message_text += f"   {cat_icon} {cat_name}\n"
                
                if trans.description:
                    # Truncate long descriptions
                    desc = trans.description[:50] + "..." if len(trans.description) > 50 else trans.description
                    message_text += f"   📝 {desc}\n"
                
                message_text += f"   📅 {date_str}\n\n"
                
                total_income += float(trans.amount)
            
            message_text += f"<b>Total Income: {currency_symbol}{total_income:.2f}</b>\n\n"
        
        # Expense section
        if expense_transactions:
            message_text += "💸 <b>EXPENSES</b>\n"
            message_text += "━━━━━━━━━━━━━━\n"
            
            total_expense = 0
            for trans, category in expense_transactions:
                cat_name = category.name if category else "No category"
                cat_icon = category.icon if category and category.icon else "📁"
                
                date_str = trans.date.strftime("%d.%m.%Y")
                
                message_text += f"➖ <b>{currency_symbol}{trans.amount:.2f}</b>\n"
                message_text += f"   {cat_icon} {cat_name}\n"
                
                if trans.description:
                    # Truncate long descriptions
                    desc = trans.description[:50] + "..." if len(trans.description) > 50 else trans.description
                    message_text += f"   📝 {desc}\n"
                
                message_text += f"   📅 {date_str}\n\n"
                
                total_expense += float(trans.amount)
            
            message_text += f"<b>Total Expenses: {currency_symbol}{total_expense:.2f}</b>\n\n"
        
        # Add summary
        balance = sum(float(t.amount) for t, _ in income_transactions) - sum(float(t.amount) for t, _ in expense_transactions)
        balance_emoji = "🟢" if balance >= 0 else "🔴"
        
        message_text += "━━━━━━━━━━━━━━\n"
        message_text += f"{balance_emoji} <b>Balance: {currency_symbol}{balance:.2f}</b>"
        
        # Navigation buttons
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Export to Excel", callback_data="export_data"),
                InlineKeyboardButton(text="🗑 Clear History", callback_data="clear_history")
            ],
            [
                InlineKeyboardButton(text="⬅️ Back to Balance", callback_data="show_balance")
            ]
        ])
        
        # Split message if too long (Telegram has 4096 character limit)
        if len(message_text) > 4000:
            # Show only recent transactions if message is too long
            message_text = "📊 <b>Transaction History (Recent)</b>\n\n"
            message_text += "⚠️ Showing last 20 transactions. Export to Excel for full history.\n\n"
            
            # Show only last 10 income and 10 expense transactions
            recent_income = income_transactions[:10]
            recent_expense = expense_transactions[:10]
            
            if recent_income:
                message_text += "💰 <b>RECENT INCOME</b>\n"
                message_text += "━━━━━━━━━━━━━━\n"
                for trans, category in recent_income:
                    cat_name = category.name if category else "No category"
                    cat_icon = category.icon if category and category.icon else "📁"
                    date_str = trans.date.strftime("%d.%m")
                    message_text += f"➕ {currency_symbol}{trans.amount:.2f} | {cat_icon} {cat_name} | {date_str}\n"
                message_text += "\n"
            
            if recent_expense:
                message_text += "💸 <b>RECENT EXPENSES</b>\n"
                message_text += "━━━━━━━━━━━━━━\n"
                for trans, category in recent_expense:
                    cat_name = category.name if category else "No category"
                    cat_icon = category.icon if category and category.icon else "📁"
                    date_str = trans.date.strftime("%d.%m")
                    message_text += f"➖ {currency_symbol}{trans.amount:.2f} | {cat_icon} {cat_name} | {date_str}\n"
                message_text += "\n"
            
            message_text += "━━━━━━━━━━━━━━\n"
            message_text += f"{balance_emoji} <b>Balance: {currency_symbol}{balance:.2f}</b>"
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing transaction history: {e}")
        await callback.message.answer("❌ Error loading transaction history")

@router.callback_query(F.data == "clear_history")
async def confirm_clear_history(callback: CallbackQuery):
    """Ask for confirmation before clearing history"""
    try:
        await callback.answer()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ Yes, Delete All", callback_data="confirm_clear_history"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="transaction_history")
            ]
        ])
        
        await callback.message.edit_text(
            "⚠️ <b>Delete All Transactions?</b>\n\n"
            "This action cannot be undone!\n"
            "All your transaction history will be permanently deleted.\n\n"
            "Are you sure?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in clear history confirmation: {e}")

@router.callback_query(F.data == "confirm_clear_history")
async def execute_clear_history(callback: CallbackQuery, session: AsyncSession):
    """Clear all user's transaction history"""
    try:
        await callback.answer("Deleting history...")
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ User not found")
            return
        
        # Delete all user's transactions
        from sqlalchemy import delete
        await session.execute(
            delete(Transaction).where(Transaction.user_id == user.id)
        )
        await session.commit()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Add Transaction", callback_data="add_transaction"),
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
            ]
        ])
        
        await callback.message.edit_text(
            "✅ <b>History Cleared</b>\n\n"
            "All transactions have been deleted.\n"
            "Your balance is now zero.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        await callback.message.answer("❌ Error clearing history")