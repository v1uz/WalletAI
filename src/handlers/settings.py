from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models.base import User

router = Router()

class SettingsStates(StatesGroup):
    main_menu = State()
    language = State()
    currency = State()

@router.callback_query(F.data == "settings")
async def settings_menu(callback: CallbackQuery, session: AsyncSession):
    """Show settings menu"""
    # Get current user settings
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Please use /start first")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"🌐 Language: {user.language}", 
                callback_data="set_language"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"💱 Currency: {user.currency}", 
                callback_data="set_currency"
            )
        ],
        [
            InlineKeyboardButton(
                text="📂 Manage Categories", 
                callback_data="manage_categories"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Recurring Transactions", 
                callback_data="recurring_transactions"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Export Data", 
                callback_data="export_data"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Back", 
                callback_data="main_menu"
            )
        ]
    ])
    
    await callback.message.edit_text(
        "⚙️ <b>Settings</b>\n\n"
        f"Current settings:\n"
        f"🌐 Language: {user.language}\n"
        f"💱 Currency: {user.currency}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "set_language")
async def set_language(callback: CallbackQuery):
    """Language selection"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇸 English", callback_data="lang:EN"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:RU")
        ],
        [
            InlineKeyboardButton(text="◀️ Back", callback_data="settings")
        ]
    ])
    
    await callback.message.edit_text(
        "🌐 <b>Select Language</b>\n\n"
        "Choose your preferred language:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("lang:"))
async def save_language(callback: CallbackQuery, session: AsyncSession):
    """Save selected language"""
    language = callback.data.split(":")[1]
    
    # Update user language
    await session.execute(
        update(User)
        .where(User.telegram_id == callback.from_user.id)
        .values(language=language)
    )
    await session.commit()
    
    # Get translation
    lang_name = "English" if language == "EN" else "Русский"
    success_msg = "✅ Language updated!" if language == "EN" else "✅ Язык обновлен!"
    
    await callback.answer(success_msg)
    
    # Return to settings
    await settings_menu(callback, session)

@router.callback_query(F.data == "set_currency")
async def set_currency(callback: CallbackQuery):
    """Currency selection"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇸 USD ($)", callback_data="curr:USD"),
            InlineKeyboardButton(text="🇷🇺 RUB (₽)", callback_data="curr:RUB")
        ],
        [
            InlineKeyboardButton(text="💶 EUR (€)", callback_data="curr:EUR"),
            InlineKeyboardButton(text="💷 GBP (£)", callback_data="curr:GBP")
        ],
        [
            InlineKeyboardButton(text="◀️ Back", callback_data="settings")
        ]
    ])
    
    await callback.message.edit_text(
        "💱 <b>Select Currency</b>\n\n"
        "Choose your preferred currency:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("curr:"))
async def save_currency(callback: CallbackQuery, session: AsyncSession):
    """Save selected currency"""
    currency = callback.data.split(":")[1]
    
    # Update user currency
    await session.execute(
        update(User)
        .where(User.telegram_id == callback.from_user.id)
        .values(currency=currency)
    )
    await session.commit()
    
    currency_symbols = {
        "USD": "$",
        "RUB": "₽",
        "EUR": "€",
        "GBP": "£"
    }
    
    await callback.answer(f"✅ Currency set to {currency} {currency_symbols.get(currency, '')}")
    
    # Return to settings
    await settings_menu(callback, session)