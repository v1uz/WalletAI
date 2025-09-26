import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from src.core.config import settings
from src.core.database import database
from src.middleware.database import DatabaseMiddleware
from sqlalchemy import select
from src.models.base import User

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main bot function"""
    
    # Initialize database
    logger.info("Creating database tables...")
    await database.create_tables()
    
    # Create bot
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    
    # Register middleware
    dp.update.middleware(DatabaseMiddleware(database.session_factory))
    
    # Register routers
    from src.handlers.transactions import router as trans_router
    from src.handlers.balance import router as balance_router
    dp.include_router(trans_router)
    dp.include_router(balance_router)
    
    # Start command
    @dp.message(CommandStart())
    async def cmd_start(message: Message, session):
        # Check/create user
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
            
            # Initialize default categories
            await database.init_default_categories(user.id)
            await session.commit()
            
            welcome_msg = "🎉 Welcome to WalletAI!"
        else:
            welcome_msg = "👋 Welcome back!"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Add Transaction", callback_data="menu:add"),
                InlineKeyboardButton(text="💰 Balance", callback_data="menu:balance")
            ],
            [
                InlineKeyboardButton(text="📊 Reports", callback_data="menu:reports"),
                InlineKeyboardButton(text="⚙️ Settings", callback_data="menu:settings")
            ]
        ])
        
        await message.answer(
            f"{welcome_msg}\n\n"
            f"I'm your personal finance assistant.\n\n"
            f"<b>Quick Commands:</b>\n"
            f"/add - Add income or expense\n"
            f"/balance - Check your balance\n"
            f"/help - Show all commands\n\n"
            f"Let's manage your finances! 💪",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    # Help command
    @dp.message(Command("help"))
    async def cmd_help(message: Message):
        await message.answer(
            "📚 <b>Available Commands:</b>\n\n"
            "/start - Main menu\n"
            "/add - Add new transaction\n"
            "/balance - Check balance\n"
            "/report - View reports (coming soon)\n"
            "/budget - Set budgets (coming soon)\n"
            "/export - Export data (coming soon)\n"
            "/settings - Bot settings (coming soon)\n\n"
            "💡 <b>Tips:</b>\n"
            "• Track all expenses for better insights\n"
            "• Set monthly budgets to control spending\n"
            "• Check reports weekly to understand patterns",
            parse_mode="HTML"
        )
    
    # Start polling
    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped")