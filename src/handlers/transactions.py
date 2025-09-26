from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from decimal import Decimal, InvalidOperation
from datetime import datetime
import re

from src.models.base import User, Transaction, Category, TransactionType

router = Router()

class AddTransaction(StatesGroup):
    selecting_type = State()
    entering_amount = State()
    selecting_category = State()
    entering_description = State()
    confirming = State()

@router.message(Command("add"))
async def cmd_add_transaction(message: Message, state: FSMContext):
    """Start adding a new transaction"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Income", callback_data="trans_type:income"),
            InlineKeyboardButton(text="💸 Expense", callback_data="trans_type:expense")
        ],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])
    
    await state.set_state(AddTransaction.selecting_type)
    await message.answer(
        "📝 <b>New Transaction</b>\n\n"
        "Select transaction type:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("trans_type:"))
async def process_transaction_type(callback: CallbackQuery, state: FSMContext):
    """Process transaction type selection"""
    trans_type = callback.data.split(":")[1]
    await state.update_data(transaction_type=trans_type)
    await state.set_state(AddTransaction.entering_amount)
    
    await callback.message.edit_text(
        f"💵 <b>Enter amount</b>\n\n"
        f"Type: {'💰 Income' if trans_type == 'income' else '💸 Expense'}\n\n"
        f"Please enter the amount (e.g., 100.50):",
        parse_mode="HTML"
    )

@router.message(AddTransaction.entering_amount)
async def process_amount(message: Message, state: FSMContext, session: AsyncSession):
    """Process amount entry"""
    # Clean and validate amount
    amount_text = message.text.strip().replace('$', '').replace(',', '')
    
    try:
        amount = Decimal(amount_text)
        if amount <= 0:
            await message.answer("❌ Amount must be positive. Please enter again:")
            return
    except (InvalidOperation, ValueError):
        await message.answer("❌ Invalid amount. Please enter a valid number:")
        return
    
    await state.update_data(amount=float(amount))
    data = await state.get_data()
    trans_type = TransactionType.INCOME if data['transaction_type'] == 'income' else TransactionType.EXPENSE
    
    # Get user categories
    result = await session.execute(
        select(Category).where(
            Category.user_id == message.from_user.id,
            Category.transaction_type == trans_type
        ).order_by(Category.name)
    )
    categories = result.scalars().all()
    
    if not categories:
        # No categories yet, create defaults
        from src.core.database import database
        await database.init_default_categories(message.from_user.id)
        # Re-fetch categories
        result = await session.execute(
            select(Category).where(
                Category.user_id == message.from_user.id,
                Category.transaction_type == trans_type
            ).order_by(Category.name)
        )
        categories = result.scalars().all()
    
    # Create category keyboard
    keyboard_buttons = []
    for i in range(0, len(categories), 2):
        row = []
        row.append(InlineKeyboardButton(
            text=categories[i].name,
            callback_data=f"cat:{categories[i].id}"
        ))
        if i + 1 < len(categories):
            row.append(InlineKeyboardButton(
                text=categories[i + 1].name,
                callback_data=f"cat:{categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await state.set_state(AddTransaction.selecting_category)
    await message.answer(
        f"💵 Amount: <b>${amount}</b>\n\n"
        f"Select category:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(AddTransaction.selecting_category, F.data.startswith("cat:"))
async def process_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Process category selection"""
    category_id = int(callback.data.split(":")[1])
    
    # Get category info
    result = await session.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one()
    
    await state.update_data(category_id=category_id, category_name=category.name)
    await state.set_state(AddTransaction.entering_description)
    
    await callback.message.edit_text(
        f"📝 <b>Transaction Details</b>\n\n"
        f"Amount: ${(await state.get_data())['amount']}\n"
        f"Category: {category.name}\n\n"
        f"Enter description (or send /skip to skip):",
        parse_mode="HTML"
    )

@router.message(AddTransaction.entering_description)
async def process_description(message: Message, state: FSMContext, session: AsyncSession):
    """Process description and save transaction"""
    description = None if message.text == "/skip" else message.text
    await state.update_data(description=description)
    
    # Get all data
    data = await state.get_data()
    
    # Save transaction
    trans_type = TransactionType.INCOME if data['transaction_type'] == 'income' else TransactionType.EXPENSE
    
    # Get or create user
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        session.add(user)
        await session.flush()
    
    # Create transaction
    transaction = Transaction(
        user_id=user.id,
        category_id=data['category_id'],
        amount=Decimal(str(data['amount'])),
        transaction_type=trans_type,
        description=description,
        date=datetime.now()
    )
    session.add(transaction)
    await session.commit()
    
    # Clear state
    await state.clear()
    
    # Send confirmation
    emoji = "💰" if trans_type == TransactionType.INCOME else "💸"
    await message.answer(
        f"✅ <b>Transaction Added!</b>\n\n"
        f"{emoji} Amount: ${data['amount']}\n"
        f"📂 Category: {data['category_name']}\n"
        f"📝 Description: {description or 'None'}\n"
        f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Use /balance to check your current balance\n"
        f"Use /add to add another transaction",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "cancel")
async def cancel_operation(callback: CallbackQuery, state: FSMContext):
    """Cancel current operation"""
    await state.clear()
    await callback.message.edit_text("❌ Operation cancelled")
