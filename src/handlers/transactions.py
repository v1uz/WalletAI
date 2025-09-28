# handlers/transactions_updated.py
"""
Updated Transaction Handler with New Category System
"""

import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from models.base import User, Transaction, Category

logger = logging.getLogger(__name__)
router = Router()

# ============= STATES =============

class TransactionStates(StatesGroup):
    """States for transaction flow"""
    selecting_type = State()
    waiting_for_amount = State()
    selecting_category = State()
    waiting_for_description = State()

# ============= UTILITY FUNCTIONS =============

def get_currency_symbol(currency: str) -> str:
    """Get currency symbol from currency code"""
    symbols = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
        'RUB': '₽', 'INR': '₹', 'BRL': 'R$', 'CAD': 'C$'
    }
    return symbols.get(currency, currency)

def parse_amount(amount_str: str) -> Decimal:
    """Parse amount string to Decimal"""
    try:
        # Remove common currency symbols and spaces
        cleaned = amount_str.replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
        amount = Decimal(cleaned)
        
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Limit to 2 decimal places
        amount = amount.quantize(Decimal('0.01'))
        
        return amount
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Invalid amount format: {amount_str}")

# ============= COMMAND HANDLERS =============

@router.message(Command("add"))
async def cmd_add_transaction(message: Message, state: FSMContext):
    """Start adding a new transaction"""
    try:
        # Clear any existing state
        await state.clear()
        
        # Create inline keyboard for transaction type
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Income", callback_data="trans:income"),
                InlineKeyboardButton(text="📉 Expense", callback_data="trans:expense")
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="trans:cancel")
            ]
        ])
        
        await message.answer(
            "💰 <b>Add New Transaction</b>\n\n"
            "Select transaction type:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(TransactionStates.selecting_type)
        
    except Exception as e:
        logger.error(f"Error in /add command: {e}")
        await message.answer("❌ Error starting transaction. Please try again.")

# ============= TRANSACTION TYPE SELECTION =============

@router.callback_query(F.data.startswith("trans:"))
async def handle_transaction_type(callback: CallbackQuery, state: FSMContext):
    """Handle transaction type selection"""
    try:
        await callback.answer()
        
        action = callback.data.split(":")[1]
        
        if action == "cancel":
            await state.clear()
            await callback.message.edit_text("❌ Transaction cancelled")
            return
        
        # Store transaction type
        await state.update_data(transaction_type=action)
        await state.set_state(TransactionStates.waiting_for_amount)
        
        emoji = "📈" if action == "income" else "📉"
        
        await callback.message.edit_text(
            f"{emoji} <b>Adding {action.capitalize()}</b>\n\n"
            f"Enter the amount:\n"
            f"(Examples: 100, 50.99, 1500)\n\n"
            f"Type /cancel to cancel",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error handling transaction type: {e}")
        await callback.message.answer("❌ Error. Please try again.")

# ============= AMOUNT INPUT =============

@router.message(TransactionStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext, session):
    """Process transaction amount"""
    try:
        if message.text == "/cancel":
            await state.clear()
            await message.answer("❌ Transaction cancelled")
            return
        
        # Parse amount
        try:
            amount = parse_amount(message.text)
        except ValueError as e:
            await message.answer(
                f"❌ {str(e)}\n\n"
                "Please enter a valid amount (e.g., 100, 50.99)"
            )
            return
        
        # Store amount
        await state.update_data(amount=float(amount))
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ User not found. Please use /start")
            await state.clear()
            return
        
        # Get transaction type from state
        state_data = await state.get_data()
        transaction_type = state_data['transaction_type']
        
        # Get user's categories for this transaction type
        categories_result = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.type == transaction_type,
                Category.is_active == True
            ).order_by(Category.name)
        )
        categories = categories_result.scalars().all()
        
        # Create category selection keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        if not categories:
            # No categories exist, show only management buttons
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="➕ Add Category", callback_data="cat:add_new")
            ])
            
            message_text = (
                f"📁 <b>No {transaction_type} categories found!</b>\n\n"
                f"Amount: {get_currency_symbol(user.currency)}{amount}\n\n"
                f"You need to create at least one category first.\n"
                f"Click 'Add Category' to create your first {transaction_type} category."
            )
        else:
            # Show existing categories
            for i in range(0, len(categories), 2):
                row = []
                for j in range(2):
                    if i + j < len(categories):
                        cat = categories[i + j]
                        row.append(
                            InlineKeyboardButton(
                                text=f"📁 {cat.name}",
                                callback_data=f"trans:cat:{cat.id}"
                            )
                        )
                keyboard.inline_keyboard.append(row)
            
            # Add management buttons
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="➕ Add Category", callback_data="cat:add_new"),
                InlineKeyboardButton(text="⚙️ Manage", callback_data="cat:manage")
            ])
            
            message_text = (
                f"💰 <b>Transaction Details</b>\n\n"
                f"Type: {transaction_type.capitalize()}\n"
                f"Amount: {get_currency_symbol(user.currency)}{amount}\n\n"
                f"Select a category:"
            )
        
        # Add cancel button
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="❌ Cancel", callback_data="trans:cancel")
        ])
        
        await message.answer(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(TransactionStates.selecting_category)
        
    except Exception as e:
        logger.error(f"Error processing amount: {e}")
        await message.answer("❌ Error processing amount. Please try again.")
        await state.clear()

# ============= CATEGORY SELECTION =============

@router.callback_query(F.data.startswith("trans:cat:"))
async def handle_category_selection(callback: CallbackQuery, state: FSMContext):
    """Handle category selection for transaction"""
    try:
        await callback.answer()
        
        category_id = int(callback.data.split(":")[2])
        
        # Store category
        await state.update_data(category_id=category_id)
        await state.set_state(TransactionStates.waiting_for_description)
        
        await callback.message.edit_text(
            "📝 <b>Transaction Description</b>\n\n"
            "Enter a description for this transaction\n"
            "(or type 'skip' to skip):\n\n"
            "Type /cancel to cancel",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error selecting category: {e}")
        await callback.message.answer("❌ Error selecting category")

# ============= DESCRIPTION INPUT =============

@router.message(TransactionStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext, session):
    """Process transaction description and save"""
    try:
        if message.text == "/cancel":
            await state.clear()
            await message.answer("❌ Transaction cancelled")
            return
        
        description = message.text.strip()
        if description.lower() == "skip":
            description = ""
        
        # Get all transaction data
        state_data = await state.get_data()
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ User not found")
            await state.clear()
            return
        
        # Create transaction
        transaction = Transaction(
            user_id=user.id,
            category_id=state_data['category_id'],
            amount=Decimal(str(state_data['amount'])),
            transaction_type=state_data['transaction_type'],
            description=description,
            date=datetime.now()
        )
        
        session.add(transaction)
        await session.commit()
        
        # Get category name for confirmation
        cat_result = await session.execute(
            select(Category).where(Category.id == state_data['category_id'])
        )
        category = cat_result.scalar_one_or_none()
        
        emoji = "📈" if state_data['transaction_type'] == "income" else "📉"
        currency_symbol = get_currency_symbol(user.currency)
        
        # Confirmation message
        confirmation_text = (
            f"✅ <b>Transaction Added Successfully!</b>\n\n"
            f"{emoji} Type: {state_data['transaction_type'].capitalize()}\n"
            f"💰 Amount: {currency_symbol}{state_data['amount']:.2f}\n"
            f"📁 Category: {category.name if category else 'Unknown'}\n"
        )
        
        if description:
            confirmation_text += f"📝 Description: {description}\n"
        
        confirmation_text += f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Quick action buttons
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Add Another", callback_data="quick:add"),
                InlineKeyboardButton(text="💰 Check Balance", callback_data="quick:balance")
            ],
            [
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
            ]
        ])
        
        await message.answer(
            confirmation_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Clear state
        await state.clear()
        
        # Log transaction
        logger.info(f"Transaction added: User {user.telegram_id}, Amount {state_data['amount']}, Type {state_data['transaction_type']}")
        
    except Exception as e:
        logger.error(f"Error saving transaction: {e}")
        await message.answer("❌ Error saving transaction. Please try again.")
        await state.clear()

# ============= QUICK ACTIONS =============

@router.callback_query(F.data.startswith("quick:"))
async def handle_quick_actions(callback: CallbackQuery, state: FSMContext, session):
    """Handle quick action buttons after transaction"""
    try:
        await callback.answer()
        
        action = callback.data.split(":")[1]
        
        if action == "add":
            # Start new transaction
            await cmd_add_transaction(callback.message, state)
            
        elif action == "balance":
            # Show balance
            from handlers.balance import show_user_balance
            
            # Get user
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await callback.message.answer("❌ User not found")
                return
            
            # Calculate balance
            balance_result = await session.execute(
                select(Transaction).where(Transaction.user_id == user.id)
            )
            transactions = balance_result.scalars().all()
            
            total_income = sum(t.amount for t in transactions if t.transaction_type == "income")
            total_expense = sum(t.amount for t in transactions if t.transaction_type == "expense")
            balance = total_income - total_expense
            
            currency_symbol = get_currency_symbol(user.currency)
            
            await callback.message.answer(
                f"💰 <b>Your Balance</b>\n\n"
                f"📈 Total Income: {currency_symbol}{total_income:.2f}\n"
                f"📉 Total Expenses: {currency_symbol}{total_expense:.2f}\n"
                f"💵 Current Balance: <b>{currency_symbol}{balance:.2f}</b>",
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Error in quick actions: {e}")
        await callback.message.answer("❌ Error processing request")

# ============= CANCEL HANDLER =============

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current operation"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Nothing to cancel.")
        return
    
    await state.clear()
    await message.answer(
        "❌ Operation cancelled.\n\n"
        "Use /add to add a new transaction or /help for more commands."
    )