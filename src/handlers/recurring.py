from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from models.base import User, Category, TransactionType
from models.recurring import RecurringTransaction
from decimal import Decimal
from datetime import datetime, timedelta
import asyncio

router = Router()

class RecurringStates(StatesGroup):
    selecting_type = State()
    entering_amount = State()
    selecting_category = State()
    entering_description = State()
    selecting_frequency = State()
    confirming = State()

@router.callback_query(F.data == "recurring_transactions")
async def recurring_menu(callback: CallbackQuery, session: AsyncSession):
    """Show recurring transactions menu"""
    # Get user
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Please use /start first")
        return
    
    # Get recurring transactions
    recurring = await session.execute(
        select(RecurringTransaction).where(
            RecurringTransaction.user_id == user.id,
            RecurringTransaction.is_active == True
        )
    )
    recurring_trans = recurring.scalars().all()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Add Recurring", callback_data="add_recurring")
        ],
        [
            InlineKeyboardButton(text="📋 View All", callback_data="view_recurring")
        ],
        [
            InlineKeyboardButton(text="🗑️ Remove", callback_data="remove_recurring")
        ],
        [
            InlineKeyboardButton(text="◀️ Back", callback_data="settings")
        ]
    ])
    
    count = len(recurring_trans)
    await callback.message.edit_text(
        f"🔄 <b>Recurring Transactions</b>\n\n"
        f"You have {count} active recurring transaction(s).\n\n"
        f"Examples:\n"
        f"• Monthly salary\n"
        f"• Rent payment\n"
        f"• Subscription services\n"
        f"• Insurance payments",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "add_recurring")
async def add_recurring_start(callback: CallbackQuery, state: FSMContext):
    """Start adding recurring transaction"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Income", callback_data="rec_type:income"),
            InlineKeyboardButton(text="💸 Expense", callback_data="rec_type:expense")
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="recurring_transactions")
        ]
    ])
    
    await state.set_state(RecurringStates.selecting_type)
    await callback.message.edit_text(
        "🔄 <b>New Recurring Transaction</b>\n\n"
        "Select transaction type:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("rec_type:"))
async def recurring_type_selected(callback: CallbackQuery, state: FSMContext):
    """Process recurring type selection"""
    trans_type = callback.data.split(":")[1]
    await state.update_data(transaction_type=trans_type)
    await state.set_state(RecurringStates.entering_amount)
    
    await callback.message.edit_text(
        f"💵 <b>Enter Amount</b>\n\n"
        f"Type: {'💰 Income' if trans_type == 'income' else '💸 Expense'}\n\n"
        f"Please enter the amount (e.g., 50000 for salary, 1500 for subscription):",
        parse_mode="HTML"
    )

@router.message(RecurringStates.entering_amount)
async def recurring_amount_entered(message: Message, state: FSMContext, session: AsyncSession):
    """Process amount for recurring transaction"""
    try:
        amount = Decimal(message.text.strip().replace(',', ''))
        if amount <= 0:
            await message.answer("❌ Amount must be positive. Please enter again:")
            return
    except:
        await message.answer("❌ Invalid amount. Please enter a valid number:")
        return
    
    await state.update_data(amount=float(amount))
    data = await state.get_data()
    trans_type = TransactionType.INCOME if data['transaction_type'] == 'income' else TransactionType.EXPENSE
    
    # Get user categories
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one()
    
    categories = await session.execute(
        select(Category).where(
            Category.user_id == user.id,
            Category.transaction_type == trans_type
        ).order_by(Category.name)
    )
    categories = categories.scalars().all()
    
    # Create category keyboard
    keyboard_buttons = []
    for i in range(0, len(categories), 2):
        row = []
        row.append(InlineKeyboardButton(
            text=f"{categories[i].icon} {categories[i].name}",
            callback_data=f"rec_cat:{categories[i].id}"
        ))
        if i + 1 < len(categories):
            row.append(InlineKeyboardButton(
                text=f"{categories[i + 1].icon} {categories[i + 1].name}",
                callback_data=f"rec_cat:{categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await state.set_state(RecurringStates.selecting_category)
    await message.answer(
        f"💵 Amount: <b>{amount}</b>\n\n"
        f"Select category:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("rec_cat:"))
async def recurring_category_selected(callback: CallbackQuery, state: FSMContext):
    """Process category selection"""
    category_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=category_id)
    await state.set_state(RecurringStates.entering_description)
    
    await callback.message.edit_text(
        f"📝 <b>Description</b>\n\n"
        f"Enter a description for this recurring transaction\n"
        f"(e.g., 'Monthly salary', 'Netflix subscription', 'Rent payment')\n\n"
        f"Send /skip to skip",
        parse_mode="HTML"
    )

@router.message(RecurringStates.entering_description)
async def recurring_description_entered(message: Message, state: FSMContext):
    """Process description"""
    description = None if message.text == "/skip" else message.text
    await state.update_data(description=description)
    await state.set_state(RecurringStates.selecting_frequency)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Daily", callback_data="freq:daily"),
            InlineKeyboardButton(text="📅 Weekly", callback_data="freq:weekly")
        ],
        [
            InlineKeyboardButton(text="📅 Monthly", callback_data="freq:monthly"),
            InlineKeyboardButton(text="📅 Yearly", callback_data="freq:yearly")
        ]
    ])
    
    await message.answer(
        "⏰ <b>Frequency</b>\n\n"
        "How often should this transaction repeat?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("freq:"))
async def save_recurring(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Save recurring transaction"""
    frequency = callback.data.split(":")[1]
    data = await state.get_data()
    
    # Get user
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one()
    
    # Create recurring transaction
    trans_type = TransactionType.INCOME if data['transaction_type'] == 'income' else TransactionType.EXPENSE
    
    recurring = RecurringTransaction(
        user_id=user.id,
        category_id=data['category_id'],
        amount=Decimal(str(data['amount'])),
        transaction_type=trans_type,
        description=data.get('description'),
        frequency=frequency,
        next_execution=datetime.now() + timedelta(days=1),
        is_active=True
    )
    
    session.add(recurring)
    await session.commit()
    
    await state.clear()
    
    frequency_text = {
        'daily': 'Every day',
        'weekly': 'Every week', 
        'monthly': 'Every month',
        'yearly': 'Every year'
    }
    
    await callback.answer("✅ Recurring transaction created!")
    await callback.message.edit_text(
        f"✅ <b>Recurring Transaction Added!</b>\n\n"
        f"Amount: {data['amount']}\n"
        f"Type: {'Income' if data['transaction_type'] == 'income' else 'Expense'}\n"
        f"Frequency: {frequency_text[frequency]}\n"
        f"Description: {data.get('description', 'None')}\n\n"
        f"This transaction will be automatically recorded {frequency_text[frequency].lower()}.",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "view_recurring")
async def view_recurring(callback: CallbackQuery, session: AsyncSession):
    """View all recurring transactions"""
    # Get user
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one()
    
    # Get recurring transactions with categories
    recurring = await session.execute(
        select(RecurringTransaction, Category).join(
            Category, RecurringTransaction.category_id == Category.id
        ).where(
            RecurringTransaction.user_id == user.id,
            RecurringTransaction.is_active == True
        )
    )
    
    transactions = recurring.all()
    
    if not transactions:
        await callback.answer("No recurring transactions found")
        return
    
    text = "📋 <b>Your Recurring Transactions</b>\n\n"
    
    for trans, category in transactions:
        emoji = "💰" if trans.transaction_type == TransactionType.INCOME else "💸"
        freq_text = {
            'daily': 'Daily',
            'weekly': 'Weekly',
            'monthly': 'Monthly',
            'yearly': 'Yearly'
        }
        
        text += (
            f"{emoji} <b>{trans.amount}</b> - {category.icon} {category.name}\n"
            f"   {freq_text[trans.frequency]} • {trans.description or 'No description'}\n\n"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back", callback_data="recurring_transactions")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")