import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from core.config import settings
from core.database import database
from core.logging import setup_logging
from middleware.database import DatabaseMiddleware
from middleware.security import SecurityMiddleware
from sqlalchemy import select
from models.base import User, Transaction
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import handlers at the top for better organization
from handlers.settings import router as settings_router
from handlers.recurring import router as recurring_router
from handlers.export import router as export_router
from handlers.transactions import router as trans_router
from handlers.balance import router as balance_router
from handlers.categories_enhanced import router as categories_enhanced_router

# Setup logging
setup_logging(use_sentry=False)
logger = logging.getLogger(__name__)

# ============= UTILITY FUNCTIONS =============

def get_currency_symbol(currency: str) -> str:
    """Get currency symbol from currency code"""
    symbols = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
        'CNY': '¥', 'INR': '₹', 'RUB': '₽', 'BRL': 'R$',
        'CAD': 'C$', 'AUD': 'A$', 'CHF': 'Fr', 'SEK': 'kr',
        'NOK': 'kr', 'DKK': 'kr', 'PLN': 'zł', 'TRY': '₺',
        'MXN': '$', 'ZAR': 'R', 'SGD': 'S$', 'HKD': 'HK$',
        'NZD': 'NZ$', 'THB': '฿', 'MYR': 'RM', 'PHP': '₱',
        'IDR': 'Rp', 'KRW': '₩', 'VND': '₫', 'AED': 'د.إ',
        'SAR': '﷼', 'EGP': 'E£', 'UAH': '₴', 'CZK': 'Kč',
        'HUF': 'Ft', 'ILS': '₪', 'CLP': '$', 'ARS': '$',
        'COP': '$', 'PEN': 'S/', 'UYU': '$U',
    }
    return symbols.get(currency, currency)

def get_text(key: str, lang: str = 'EN') -> str:
    """Get translated text for multi-language support"""
    translations = {
        'EN': {
            'welcome_back': "👋 Welcome back!",
            'add_transaction': "➕ Add Transaction",
            'check_balance': "💰 Balance",
            'reports': "📊 Reports",
            'settings': "⚙️ Settings",
            'ai_advices': "🪙 Financial advises",
            'goals_dreams': "🏆 Goals/Dreams",
            'main_menu_text': "I'm your personal finance assistant.",
            'quick_commands': "Quick Commands:",
        },
        'RU': {
            'welcome_back': "👋 С возвращением!",
            'add_transaction': "➕ Добавить транзакцию",
            'check_balance': "💰 Баланс",
            'reports': "📊 Отчеты",
            'settings': "⚙️ Настройки",
            'ai_advices': "🪙 Финансовые советы",
            'goals_dreams': "🏆 Цели/Мечты",
            'main_menu_text': "Я ваш персональный финансовый помощник.",
            'quick_commands': "Быстрые команды:",
        },
        'ES': {
            'welcome_back': "👋 ¡Bienvenido de nuevo!",
            'add_transaction': "➕ Añadir Transacción",
            'check_balance': "💰 Saldo",
            'reports': "📊 Informes",
            'settings': "⚙️ Configuración",
            'ai_advices': "🪙 Consejos financieros",
            'goals_dreams': "🏆 Metas/Sueños",
            'main_menu_text': "Soy tu asistente financiero personal.",
            'quick_commands': "Comandos rápidos:",
        }
    }
    
    lang_dict = translations.get(lang, translations['EN'])
    return lang_dict.get(key, translations['EN'].get(key, key))

# ============= BACKGROUND TASKS =============

async def process_recurring_transactions():
    """Process recurring transactions daily"""
    while True:
        try:
            from models.recurring import RecurringTransaction
            
            async with database.session_factory() as session:
                # Get all due recurring transactions
                now = datetime.now()
                
                result = await session.execute(
                    select(RecurringTransaction).where(
                        RecurringTransaction.is_active == True,
                        RecurringTransaction.next_execution <= now
                    )
                )
                
                for recurring in result.scalars():
                    try:
                        # Create actual transaction
                        transaction = Transaction(
                            user_id=recurring.user_id,
                            category_id=recurring.category_id,
                            amount=recurring.amount,
                            transaction_type=recurring.transaction_type,
                            description=f"[Recurring] {recurring.description}",
                            date=now
                        )
                        session.add(transaction)
                        
                        # Update next execution date
                        if recurring.frequency == 'daily':
                            recurring.next_execution = now + timedelta(days=1)
                        elif recurring.frequency == 'weekly':
                            recurring.next_execution = now + timedelta(weeks=1)
                        elif recurring.frequency == 'monthly':
                            # Handle month boundaries properly
                            next_month = now.month + 1 if now.month < 12 else 1
                            next_year = now.year if now.month < 12 else now.year + 1
                            recurring.next_execution = now.replace(
                                month=next_month, year=next_year, 
                                day=min(recurring.next_execution.day, 28)  # Avoid day overflow
                            )
                        elif recurring.frequency == 'yearly':
                            recurring.next_execution = now.replace(year=now.year + 1)
                        
                        recurring.last_execution = now
                        
                    except Exception as e:
                        logger.error(f"Error processing recurring transaction {recurring.id}: {e}")
                        continue
                
                await session.commit()
                logger.debug(f"Processed recurring transactions at {now}")
                
        except Exception as e:
            logger.error(f"Error in recurring transactions processor: {e}", exc_info=True)
        
        # Wait 1 hour before next check
        await asyncio.sleep(3600)

# ============= MAIN BOT FUNCTION =============

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
            logger.info("Security middleware enabled")
            dp.update.middleware(SecurityMiddleware(encryption_key=settings.ENCRYPTION_KEY))
        else:
            logger.warning("Security middleware disabled - no encryption key set")
        
        # Register routers
        logger.info("Registering command handlers...")
        dp.include_router(categories_enhanced_router)  # Category management first
        dp.include_router(trans_router)               # Then transactions
        dp.include_router(balance_router)
        dp.include_router(settings_router)
        dp.include_router(recurring_router)
        dp.include_router(export_router)
                
        # ============= COMMAND HANDLERS =============
        
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
                    
                    # DO NOT initialize default categories - users create their own
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
                        InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")
                    ],
                    [
                        InlineKeyboardButton(text="🪙 Financial advises", callback_data="ai_advices"),
                        InlineKeyboardButton(text="🏆 Goals/Dreams", callback_data="goals_dreams")
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
                "/report - View reports\n"
                "/settings - Bot settings\n"
                "/export - Export data to Excel\n"
                "/ai_advices - AI financial insights (Coming soon)\n"
                "/goals_dreams - Track financial goals (Coming soon)\n\n"
                "💡 <b>Tips:</b>\n"
                "• Track all expenses for better insights\n"
                "• Set monthly budgets to control spending\n"
                "• Check reports weekly to understand patterns\n\n"
                "📁 <b>Categories:</b>\n"
                "• Create your own custom categories\n"
                "• Name them in any language\n"
                "• Manage them anytime through /add command",
                parse_mode="HTML"
            )
        
        # Report command
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
                
                # Get currency symbol
                currency_symbol = get_currency_symbol(user.currency)
                
                # Format report message
                report_text = (
                    f"📊 <b>Monthly Report - {monthly_report['period']}</b>\n\n"
                    f"💰 Income: {currency_symbol}{monthly_report['total_income']:.2f}\n"
                    f"💸 Expenses: {currency_symbol}{monthly_report['total_expense']:.2f}\n"
                    f"💵 Balance: {currency_symbol}{monthly_report['balance']:.2f}\n"
                    f"📈 Savings Rate: {monthly_report['savings_rate']:.1f}%\n"
                    f"📅 Daily Average: {currency_symbol}{monthly_report['daily_average']:.2f}\n\n"
                )
                
                if monthly_report['category_breakdown']:
                    report_text += "<b>Category Breakdown:</b>\n"
                    for category, amount in monthly_report['category_breakdown'].items():
                        report_text += f"• {category}: {currency_symbol}{amount:.2f}\n"
                
                await message.answer(report_text, parse_mode="HTML")
                
            except Exception as e:
                logger.error(f"Error in /report command: {e}", exc_info=True)
                await message.answer("❌ Error generating report. Please try again later.")
        
        # AI Advices command
        @dp.message(Command("ai_advices"))
        async def cmd_ai_advices(message: Message):
            """Handle /ai_advices command"""
            await message.answer(
                "🤖 <b>AI Financial Advices</b>\n\n"
                "🚧 We are currently working on this feature.\n\n"
                "Soon you'll be able to:\n"
                "• Get personalized spending insights\n"
                "• Receive smart budget recommendations\n"
                "• Analyze your financial patterns\n"
                "• Get predictive alerts for unusual spending\n"
                "• Receive investment suggestions\n\n"
                "We apologize for the inconvenience. This feature will be available soon! 🚀",
                parse_mode="HTML"
            )
        
        # Goals/Dreams command
        @dp.message(Command("goals_dreams"))
        async def cmd_goals_dreams(message: Message):
            """Handle /goals_dreams command"""
            await message.answer(
                "🏆 <b>Goals & Dreams Tracker</b>\n\n"
                "🚧 We are currently working on this feature.\n\n"
                "Soon you'll be able to:\n"
                "• Set financial goals and track progress\n"
                "• Create savings plans for your dreams\n"
                "• Get milestone notifications\n"
                "• Visualize your journey to success\n"
                "• Set up automatic savings transfers\n\n"
                "We apologize for the inconvenience. This feature will be available soon! 🎯",
                parse_mode="HTML"
            )
        
        # Migration command (for existing users with default categories)
        @dp.message(Command("migrate_categories"))
        async def cmd_migrate_categories(message: Message, session):
            """Remove default categories for user"""
            try:
                # Get user
                result = await session.execute(
                    select(User).where(User.telegram_id == message.from_user.id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    await message.answer("User not found. Please use /start first.")
                    return
                
                # Check if migration module exists
                try:
                    from core.database_updated import migrate_remove_default_categories
                    await migrate_remove_default_categories(session, user.id)
                    
                    await message.answer(
                        "✅ <b>Migration completed!</b>\n\n"
                        "Default categories have been removed.\n"
                        "You can now create your own custom categories.\n\n"
                        "Use /add to start creating your personalized categories!",
                        parse_mode="HTML"
                    )
                except ImportError:
                    logger.warning("Migration module not found")
                    await message.answer(
                        "⚠️ Migration module not available.\n"
                        "Please ensure database_updated.py exists in core/ directory."
                    )
                    
            except Exception as e:
                logger.error(f"Migration error: {e}", exc_info=True)
                await message.answer("❌ Migration failed. Please contact support.")
        
        # ============= CALLBACK HANDLERS =============
        
        # Main menu callback
        @dp.callback_query(F.data == "main_menu")
        async def show_main_menu(callback: CallbackQuery, session):
            """Return to main menu"""
            try:
                await callback.answer()
                
                # Get user for language preference
                result = await session.execute(
                    select(User).where(User.telegram_id == callback.from_user.id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    await callback.answer("Please use /start first")
                    return
                
                lang = user.language or 'EN'
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=get_text('add_transaction', lang), 
                            callback_data="menu:add"
                        ),
                        InlineKeyboardButton(
                            text=get_text('check_balance', lang), 
                            callback_data="menu:balance"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=get_text('reports', lang), 
                            callback_data="menu:reports"
                        ),
                        InlineKeyboardButton(
                            text=get_text('settings', lang), 
                            callback_data="settings"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=get_text('ai_advices', lang), 
                            callback_data="ai_advices"
                        ),
                        InlineKeyboardButton(
                            text=get_text('goals_dreams', lang), 
                            callback_data="goals_dreams"
                        )
                    ]
                ])
                
                await callback.message.edit_text(
                    f"{get_text('welcome_back', lang)}\n\n"
                    f"{get_text('main_menu_text', lang)}\n\n"
                    f"<b>{get_text('quick_commands', lang)}</b>\n"
                    "/add - Add income or expense\n"
                    "/balance - Check your balance\n"
                    "/help - Show all commands",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Error in show_main_menu: {e}")
                await callback.answer("❌ Error loading menu")

        # Menu callbacks handler
        @dp.callback_query(F.data.startswith("menu:"))
        async def handle_menu_callbacks(callback: CallbackQuery, state: FSMContext, session):
            """Handle main menu button clicks"""
            try:
                await callback.answer()
                action = callback.data.split(":")[1]
                
                if action == "add":
                    # Trigger add transaction flow
                    from handlers.transactions import cmd_add_transaction
                    await cmd_add_transaction(callback.message, state)
                    
                elif action == "balance":
                    # Show balance
                    from handlers.balance import show_balance_for_user
                    # Use a helper function instead of modifying message
                    await show_balance_for_user(callback.from_user.id, callback.message, session)
                    
                elif action == "reports":
                    # Generate report
                    from services.report_service import ReportService
                    
                    # Get user
                    result = await session.execute(
                        select(User).where(User.telegram_id == callback.from_user.id)
                    )
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        await callback.answer("Please use /start first")
                        return
                    
                    report_service = ReportService(session)
                    monthly_report = await report_service.generate_monthly_report(user.id)
                    
                    # Format report message
                    currency_symbol = get_currency_symbol(user.currency)
                    report_text = (
                        f"📊 <b>Monthly Report - {monthly_report['period']}</b>\n\n"
                        f"💰 Income: {currency_symbol}{monthly_report['total_income']:.2f}\n"
                        f"💸 Expenses: {currency_symbol}{monthly_report['total_expense']:.2f}\n"
                        f"💵 Balance: {currency_symbol}{monthly_report['balance']:.2f}\n"
                        f"📈 Savings Rate: {monthly_report['savings_rate']:.1f}%\n"
                        f"📅 Daily Average: {currency_symbol}{monthly_report['daily_average']:.2f}\n\n"
                    )
                    
                    if monthly_report['category_breakdown']:
                        report_text += "<b>Category Breakdown:</b>\n"
                        for category, amount in monthly_report['category_breakdown'].items():
                            report_text += f"• {category}: {currency_symbol}{amount:.2f}\n"
                    
                    await callback.message.answer(report_text, parse_mode="HTML")
                    
            except Exception as e:
                logger.error(f"Error in menu callback handler: {e}", exc_info=True)
                await callback.answer("❌ Error processing request")
        
        # AI Advices callback handler
        @dp.callback_query(F.data == "ai_advices")
        async def handle_ai_advices_callback(callback: CallbackQuery):
            """Handle AI advices button click"""
            try:
                await callback.answer("🚧 Feature coming soon!")
                await callback.message.answer(
                    "🤖 <b>AI Financial Advices</b>\n\n"
                    "🚧 We are currently working on this feature.\n\n"
                    "Soon you'll be able to:\n"
                    "• Get personalized spending insights\n"
                    "• Receive smart budget recommendations\n"
                    "• Analyze your financial patterns\n"
                    "• Get predictive alerts for unusual spending\n"
                    "• Receive investment suggestions\n\n"
                    "We apologize for the inconvenience. This feature will be available soon! 🚀\n\n"
                    "Press /start to return to the main menu.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Error in AI advices callback: {e}")
                await callback.answer("❌ Error")
        
        # Goals/Dreams callback handler
        @dp.callback_query(F.data == "goals_dreams")
        async def handle_goals_dreams_callback(callback: CallbackQuery):
            """Handle goals/dreams button click"""
            try:
                await callback.answer("🚧 Feature coming soon!")
                await callback.message.answer(
                    "🏆 <b>Goals & Dreams Tracker</b>\n\n"
                    "🚧 We are currently working on this feature.\n\n"
                    "Soon you'll be able to:\n"
                    "• Set financial goals and track progress\n"
                    "• Create savings plans for your dreams\n"
                    "• Get milestone notifications\n"
                    "• Visualize your journey to success\n"
                    "• Set up automatic savings transfers\n\n"
                    "We apologize for the inconvenience. This feature will be available soon! 🎯\n\n"
                    "Press /start to return to the main menu.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Error in goals/dreams callback: {e}")
                await callback.answer("❌ Error")
        
        # ============= START BOT =============
        
        # Start background task for recurring transactions
        asyncio.create_task(process_recurring_transactions())
        
        # Get bot info and start polling
        bot_info = await bot.get_me()
        logger.info(f"Starting bot: @{bot_info.username}")
        logger.info(f"Bot name: {bot_info.first_name}")
        logger.info(f"Bot ID: {bot_info.id}")
        
        try:
            await dp.start_polling(bot)
        finally:
            await bot.session.close()
            logger.info("Bot session closed")
            
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise

# ============= ENTRY POINT =============

if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("Starting WalletAI Bot...")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"Debug mode: {settings.DEBUG}")
        logger.info("=" * 50)
        
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        sys.exit(1)