# handlers/transactions_fixed.py
"""
Fixed Transaction Handler with User-Managed Categories
Replaces the old transaction handler with proper category management integration
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
    waiting_for_new_category = State()  # For inline category creation

# ============= UTILITY FUNCTIONS =============

def get_currency_symbol(currency: str) -> str:
    """Get currency symbol from currency code"""
    symbols = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
        'RUB': '₽', 'INR': '₹', 'BRL': 'R$', 'CAD': 'C$'
    }
    return symbols.get(currency, currency)

async def get_user_categories(session, user_id: int, transaction_type: str):
    """Get user's active categories for a specific transaction type"""
    result = await session.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.type == transaction_type,
            Category.is_active == True
        ).order_by(Category.name)
    )
    return result.scalars().all()

async def create_category_keyboard(categories, transaction_type: str, show_cancel: bool = True):
    """Create keyboard for category selection with management buttons"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Add existing categories (if any)
    if categories:
        for i in range(0, len(categories), 2):
            row = []
            for j in range(2):
                if i + j < len(categories):
                    cat = categories[i + j]
                    icon = cat.icon if cat.icon else "📁"
                    row.append(
                        InlineKeyboardButton(
                            text=f"{icon} {cat.name}",
                            callback_data=f"select_cat:{cat.id}"
                        )
                    )
            keyboard.inline_keyboard.append(row)
    
    # Always add management buttons
    management_row = []
    management_row.append(
        InlineKeyboardButton(text="➕ Add Category", callback_data=f"add_cat:{transaction_type}")
    )
    
    if categories:  # Only show manage if there are categories to manage
        management_row.append(
            InlineKeyboardButton(text="⚙️ Manage", callback_data="manage_cats")
        )
    
    keyboard.inline_keyboard.append(management_row)
    
    # Add cancel button if requested
    if show_cancel:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_transaction")
        ])
    
    return keyboard

# ============= MAIN COMMAND =============

@router.message(Command("add"))
async def cmd_add_transaction(message: Message, state: FSMContext):
    """Start adding a new transaction"""
    try:
        # Clear any existing state
        await state.clear()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Income", callback_data="type:income"),
                InlineKeyboardButton(text="💸 Expense", callback_data="type:expense")
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_transaction")
            ]
        ])
        
        await message.answer(
            "📝 <b>New Transaction</b>\n\n"
            "Select transaction type:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(TransactionStates.selecting_type)
        
    except Exception as e:
        logger.error(f"Error in /add command: {e}")
        await message.answer("❌ Error starting transaction. Please try again.")

# ============= CALLBACK: ADD TRANSACTION =============

@router.callback_query(F.data == "add_transaction")
async def callback_add_transaction(callback: CallbackQuery, state: FSMContext):
    """Handle add transaction button from main menu"""
    try:
        await callback.answer()
        await state.clear()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Income", callback_data="type:income"),
                InlineKeyboardButton(text="💸 Expense", callback_data="type:expense")
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_transaction")
            ]
        ])
        
        await callback.message.edit_text(
            "📝 <b>New Transaction</b>\n\n"
            "Select transaction type:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(TransactionStates.selecting_type)
        
    except Exception as e:
        logger.error(f"Error in add transaction callback: {e}")
        await callback.message.answer("❌ Error. Please try again.")

# ============= TRANSACTION TYPE SELECTION =============

@router.callback_query(F.data.startswith("type:"))
async def handle_transaction_type(callback: CallbackQuery, state: FSMContext):
    """Handle transaction type selection"""
    try:
        await callback.answer()
        
        transaction_type = callback.data.split(":")[1]
        await state.update_data(transaction_type=transaction_type)
        await state.set_state(TransactionStates.waiting_for_amount)
        
        emoji = "💰" if transaction_type == "income" else "💸"
        
        await callback.message.edit_text(
            f"{emoji} <b>Amount</b>\n\n"
            f"Enter the amount for this {transaction_type}:\n"
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
            amount_str = message.text.replace(',', '').replace('$', '').replace('€', '').strip()
            amount = Decimal(amount_str)
            
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            # Limit to 2 decimal places
            amount = amount.quantize(Decimal('0.01'))
            
        except (InvalidOperation, ValueError):
            await message.answer(
                "❌ Invalid amount. Please enter a valid positive number:\n"
                "(Examples: 100, 50.99, 1500)"
            )
            return
        
        # Store amount and get user
        await state.update_data(amount=float(amount))
        
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ User not found. Please use /start first")
            await state.clear()
            return
        
        # Get transaction type and categories
        state_data = await state.get_data()
        transaction_type = state_data['transaction_type']
        
        categories = await get_user_categories(session, user.id, transaction_type)
        
        # Create keyboard
        keyboard = await create_category_keyboard(categories, transaction_type)
        
        # Prepare message
        currency_symbol = get_currency_symbol(user.currency)
        
        if not categories:
            message_text = (
                f"💵 Amount: {currency_symbol}{amount}\n\n"
                f"📁 <b>No categories yet!</b>\n\n"
                f"You need to create at least one {transaction_type} category.\n"
                f"Click 'Add Category' to create your first category."
            )
        else:
            message_text = (
                f"💵 Amount: {currency_symbol}{amount}\n\n"
                f"Select category:"
            )
        
        await message.answer(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(TransactionStates.selecting_category)
        
    except Exception as e:
        logger.error(f"Error processing amount: {e}")
        await message.answer("❌ Error processing amount. Please try again.")

# ============= CATEGORY SELECTION =============

@router.callback_query(F.data.startswith("select_cat:"))
async def handle_category_selection(callback: CallbackQuery, state: FSMContext):
    """Handle category selection for transaction"""
    try:
        await callback.answer()
        
        category_id = int(callback.data.split(":")[1])
        await state.update_data(category_id=category_id)
        await state.set_state(TransactionStates.waiting_for_description)
        
        await callback.message.edit_text(
            "📝 <b>Description (Optional)</b>\n\n"
            "Enter a description for this transaction\n"
            "or type 'skip' to skip:\n\n"
            "Type /cancel to cancel",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error selecting category: {e}")
        await callback.message.answer("❌ Error selecting category")

# ============= ADD CATEGORY INLINE =============

@router.callback_query(F.data.startswith("add_cat:"))
async def handle_add_category_inline(callback: CallbackQuery, state: FSMContext):
    """Handle inline category addition during transaction"""
    try:
        await callback.answer()
        
        transaction_type = callback.data.split(":")[1]
        
        # Store that we're adding a category inline
        current_state = await state.get_data()
        await state.update_data(
            adding_category_inline=True,
            category_type=transaction_type,
            # Preserve transaction data
            transaction_type=current_state.get('transaction_type'),
            amount=current_state.get('amount')
        )
        
        await state.set_state(TransactionStates.waiting_for_new_category)
        
        await callback.message.edit_text(
            f"➕ <b>New {transaction_type.capitalize()} Category</b>\n\n"
            f"Enter a name for your new category:\n"
            f"(Examples: Groceries, Salary, Entertainment, Rent)\n\n"
            f"Type /cancel to cancel",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error adding category inline: {e}")
        await callback.message.answer("❌ Error. Please try again.")

@router.message(TransactionStates.waiting_for_new_category)
async def process_new_category_name(message: Message, state: FSMContext, session):
    """Process new category name during transaction flow"""
    try:
        if message.text == "/cancel":
            await state.clear()
            await message.answer("❌ Operation cancelled")
            return
        
        category_name = message.text.strip()
        
        # Validate
        if len(category_name) < 2:
            await message.answer("❌ Category name must be at least 2 characters")
            return
        
        if len(category_name) > 50:
            await message.answer("❌ Category name must be less than 50 characters")
            return
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ User not found")
            await state.clear()
            return
        
        state_data = await state.get_data()
        category_type = state_data['category_type']
        
        # Check for duplicate
        existing = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.name == category_name,
                Category.type == category_type,
                Category.is_active == True
            )
        )
        
        if existing.scalar_one_or_none():
            await message.answer(f"❌ Category '{category_name}' already exists!")
            return
        
        # Create category
        new_category = Category(
            user_id=user.id,
            name=category_name,
            type=category_type,
            is_active=True
        )
        
        session.add(new_category)
        await session.commit()
        await session.refresh(new_category)
        
        await message.answer(
            f"✅ Category '<b>{category_name}</b>' created!\n\n"
            f"Now selecting it for your transaction...",
            parse_mode="HTML"
        )
        
        # Auto-select the new category and continue with transaction
        await state.update_data(category_id=new_category.id, adding_category_inline=False)
        await state.set_state(TransactionStates.waiting_for_description)
        
        await message.answer(
            "📝 <b>Description (Optional)</b>\n\n"
            "Enter a description for this transaction\n"
            "or type 'skip' to skip:\n\n"
            "Type /cancel to cancel",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error creating category: {e}")
        await message.answer("❌ Error creating category")

# ============= MANAGE CATEGORIES =============

@router.callback_query(F.data == "manage_cats")
async def handle_manage_categories(callback: CallbackQuery, session):
    """Show category management options"""
    try:
        await callback.answer()
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ User not found")
            return
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Rename Category", callback_data="rename_cat"),
                InlineKeyboardButton(text="🗑 Delete Category", callback_data="delete_cat")
            ],
            [
                InlineKeyboardButton(text="📋 View All Categories", callback_data="view_all_cats")
            ],
            [
                InlineKeyboardButton(text="⬅️ Back", callback_data="back_to_categories")
            ]
        ])
        
        await callback.message.edit_text(
            "⚙️ <b>Category Management</b>\n\n"
            "What would you like to do?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error in manage categories: {e}")
        await callback.message.answer("❌ Error")

# ============= DESCRIPTION INPUT =============

@router.message(TransactionStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext, session):
    """Process transaction description and save"""
    try:
        if message.text == "/cancel":
            await state.clear()
            await message.answer("❌ Transaction cancelled")
            return
        
        description = None if message.text.lower() == "skip" else message.text.strip()
        
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
        
        # Get category for confirmation
        cat_result = await session.execute(
            select(Category).where(Category.id == state_data['category_id'])
        )
        category = cat_result.scalar_one_or_none()
        
        emoji = "💰" if state_data['transaction_type'] == "income" else "💸"
        currency_symbol = get_currency_symbol(user.currency)
        
        # Confirmation message
        confirmation_text = (
            f"✅ <b>Transaction Added!</b>\n\n"
            f"{emoji} Type: {state_data['transaction_type'].capitalize()}\n"
            f"💵 Amount: {currency_symbol}{state_data['amount']:.2f}\n"
        )
        
        if category:
            icon = category.icon if category.icon else "📁"
            confirmation_text += f"📁 Category: {icon} {category.name}\n"
        
        if description:
            confirmation_text += f"📝 Description: {description}\n"
        
        confirmation_text += f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Quick action buttons
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Add Another", callback_data="add_transaction"),
                InlineKeyboardButton(text="💰 Check Balance", callback_data="show_balance")
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
        
    except Exception as e:
        logger.error(f"Error saving transaction: {e}")
        await message.answer("❌ Error saving transaction. Please try again.")
        await state.clear()

# ============= CANCEL HANDLER =============

@router.callback_query(F.data == "cancel_transaction")
async def handle_cancel_transaction(callback: CallbackQuery, state: FSMContext):
    """Handle transaction cancellation"""
    try:
        await callback.answer("Transaction cancelled")
        await state.clear()
        await callback.message.edit_text("❌ Transaction cancelled")
    except Exception as e:
        logger.error(f"Error cancelling transaction: {e}")

# ============= SHOW BALANCE CALLBACK =============

@router.callback_query(F.data == "show_balance")
async def handle_show_balance(callback: CallbackQuery, session):
    """Handle show balance callback"""
    try:
        await callback.answer()
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ User not found")
            return
        
        # Calculate balance
        from sqlalchemy import func, and_
        
        # Total income
        income_result = await session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.transaction_type == "income"
                )
            )
        )
        total_income = income_result.scalar() or Decimal('0')
        
        # Total expenses
        expense_result = await session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.transaction_type == "expense"
                )
            )
        )
        total_expense = expense_result.scalar() or Decimal('0')
        
        balance = total_income - total_expense
        currency_symbol = get_currency_symbol(user.currency)
        
        balance_emoji = "🟢" if balance >= 0 else "🔴"
        
        # Add transaction history button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 Transaction History", callback_data="transaction_history")],
            [InlineKeyboardButton(text="➕ Add Transaction", callback_data="add_transaction")]
        ])
        
        await callback.message.answer(
            f"💰 <b>Your Balance</b>\n\n"
            f"{balance_emoji} Current Balance: <b>{currency_symbol}{balance:.2f}</b>\n\n"
            f"💚 Total Income: {currency_symbol}{total_income:.2f}\n"
            f"💔 Total Expenses: {currency_symbol}{total_expense:.2f}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing balance: {e}")
        await callback.message.answer("❌ Error retrieving balance")