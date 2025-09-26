from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.base import User

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    """Handle /start command"""
    user_id = message.from_user.id
    
    # Check if user exists
    result = await session.execute(
        select(User).where(User.telegram_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user
        user = User(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name
        )
        session.add(user)
        await session.commit()
        
        welcome_text = (
            f"🎉 Welcome to WalletAI, {message.from_user.first_name}!\n\n"
            "I'm your personal finance assistant. Here's what I can do:\n\n"
            "💰 Track income and expenses\n"
            "📊 Generate financial reports\n"
            "🎯 Set and monitor savings goals\n"
            "🤖 AI-powered insights\n\n"
            "Let's start managing your finances!"
        )
    else:
        welcome_text = f"Welcome back, {message.from_user.first_name}! 👋"
    
    # Create main menu
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Add Transaction", callback_data="add_transaction"),
            InlineKeyboardButton(text="💰 Balance", callback_data="show_balance")
        ],
        [
            InlineKeyboardButton(text="📊 Reports", callback_data="reports"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")
        ]
    ])
    
    await message.answer(welcome_text, reply_markup=keyboard)