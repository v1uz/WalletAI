import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from core.config import settings
from core.database import database
from core.logging import setup_logging
from middleware.database import DatabaseMiddleware
from middleware.security import SecurityMiddleware
from sqlalchemy import select
from models.base import User
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
setup_logging(use_sentry=False)
logger = logging.getLogger(__name__)

async def main():
    """Main bot function"""
    
    try:
        # Initialize database
        logger.info("Creating database tables...")
        await database.create_tables()
        logger.info("Database tables created successfully")
        
        # Create bot
        logger.info("Creating bot instance...")
        bot = Bot(token=settings.BOT_TOKEN)
        dp = Dispatcher()
        
        # Register middleware
        logger.info("Registering middleware...")
        dp.update.middleware(DatabaseMiddleware(database.session_factory))
        
        # Add security middleware if encryption key is set
        if settings.ENCRYPTION_KEY:
            dp.update.middleware(SecurityMiddleware(encryption_key=settings.ENCRYPTION_KEY))
        
        # Register routers
        logger.info("Registering command handlers...")
        from handlers.transactions import router as trans_router
        from handlers.balance import router as balance_router
        dp.include_router(trans_router)
        dp.include_router(balance_router)
        
        # Start command
        @dp.message(CommandStart())
        async def cmd_start(message: Message, session):
            try:
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
                    await database.init_default_categories_with_session(user.id, session)
                    await session.commit()
                    
                    welcome_msg = "🎉 Welcome to WalletAI!"
                    logger.info(f"New user registered: {user.telegram_id}")
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
            except Exception as e:
                logger.error(f"Error in /start command: {e}", exc_info=True)
                await message.answer("❌ An error occurred. Please try again.")
        
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
        
        # Report command (basic implementation)
        @dp.message(Command("report"))
        async def cmd_report(message: Message, session):
            try:
                from services.report_service import ReportService
                
                # Get user
                result = await session.execute(
                    select(User).where(User.telegram_id == message.from_user.id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    await message.answer("Please use /start first to initialize your account.")
                    return
                
                # Generate report
                report_service = ReportService(session)
                monthly_report = await report_service.generate_monthly_report(user.id)
                
                # Format report message
                report_text = (
                    f"📊 <b>Monthly Report - {monthly_report['period']}</b>\n\n"
                    f"💰 Income: ${monthly_report['total_income']:.2f}\n"
                    f"💸 Expenses: ${monthly_report['total_expense']:.2f}\n"
                    f"💵 Balance: ${monthly_report['balance']:.2f}\n"
                    f"📈 Savings Rate: {monthly_report['savings_rate']:.1f}%\n"
                    f"📅 Daily Average: ${monthly_report['daily_average']:.2f}\n\n"
                )
                
                if monthly_report['category_breakdown']:
                    report_text += "<b>Category Breakdown:</b>\n"
                    for category, amount in monthly_report['category_breakdown'].items():
                        report_text += f"{category}: ${amount:.2f}\n"
                
                await message.answer(report_text, parse_mode="HTML")
                
            except Exception as e:
                logger.error(f"Error in /report command: {e}", exc_info=True)
                await message.answer("❌ Error generating report. Please try again later.")
        
        # Start polling
        logger.info("Starting bot...")
        logger.info(f"Bot username: @{(await bot.get_me()).username}")
        
        try:
            await dp.start_polling(bot)
        finally:
            await bot.session.close()
            
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        logger.info("Starting WalletAI Bot...")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"Debug mode: {settings.DEBUG}")
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        sys.exit(1)