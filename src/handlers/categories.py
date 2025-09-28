from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from models.base import User, Category, TransactionType
from typing import Optional

router = Router()

class CategoryStates(StatesGroup):
    selecting_type = State()
    entering_name = State()
    selecting_icon = State()
    editing_category = State()
    confirming_delete = State()

@router.callback_query(F.data == "manage_categories")
async def manage_categories_menu(callback: CallbackQuery, session: AsyncSession):
    """Show category management menu"""
    # Get user
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Please use /start first")
        return
    
    # Get user's custom categories
    categories = await session.execute(
        select(Category).where(
            Category.user_id == user.id,
            Category.is_default == False
        ).order_by(Category.name)
    )
    custom_categories = categories.scalars().all()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Add Category", callback_data="add_category"),
            InlineKeyboardButton(text="✏️ Edit Category", callback_data="edit_category")
        ],
        [
            InlineKeyboardButton(text="🗑️ Delete Category", callback_data="delete_category")
        ],
        [
            InlineKeyboardButton(text="◀️ Back to Settings", callback_data="settings")
        ]
    ])
    
    categories_list = "\n".join([f"{cat.icon} {cat.name}" for cat in custom_categories]) if custom_categories else "No custom categories yet"
    
    await callback.message.edit_text(
        f"📂 <b>Category Management</b>\n\n"
        f"<b>Your custom categories:</b>\n{categories_list}\n\n"
        f"What would you like to do?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a new category"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Income", callback_data="cat_type:income"),
            InlineKeyboardButton(text="💸 Expense", callback_data="cat_type:expense")
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="manage_categories")
        ]
    ])
    
    await state.set_state(CategoryStates.selecting_type)
    await callback.message.edit_text(
        "📝 <b>New Category</b>\n\n"
        "First, select the category type:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("cat_type:"))
async def category_type_selected(callback: CallbackQuery, state: FSMContext):
    """Process category type selection"""
    cat_type = callback.data.split(":")[1]
    await state.update_data(category_type=cat_type)
    await state.set_state(CategoryStates.entering_name)
    
    await callback.message.edit_text(
        f"📝 <b>New {'Income' if cat_type == 'income' else 'Expense'} Category</b>\n\n"
        f"Now, send me the name for your category.\n"
        f"For example: 'Freelance', 'Hobbies', 'Subscriptions', etc.\n\n"
        f"Send /cancel to cancel",
        parse_mode="HTML"
    )

@router.message(CategoryStates.entering_name)
async def process_category_name(message: Message, state: FSMContext, session: AsyncSession):
    """Process the category name"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Category creation cancelled")
        return
    
    category_name = message.text.strip()
    if len(category_name) > 50:
        await message.answer("❌ Category name too long. Please use 50 characters or less.")
        return
    
    await state.update_data(category_name=category_name)
    await state.set_state(CategoryStates.selecting_icon)
    
    # Icon selection keyboard
    expense_icons = ["🍕", "🎮", "📚", "🎬", "✈️", "🏋️", "🎨", "🐾", "🎵", "📱"]
    income_icons = ["💼", "💎", "🏆", "🎯", "💡", "🎁", "💳", "📈", "🏪", "🤝"]
    
    data = await state.get_data()
    icons = income_icons if data['category_type'] == 'income' else expense_icons
    
    keyboard_buttons = []
    for i in range(0, len(icons), 5):
        row = [InlineKeyboardButton(text=icon, callback_data=f"icon:{icon}") 
               for icon in icons[i:i+5]]
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="Skip (no icon)", callback_data="icon:none")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        f"🎨 <b>Choose an icon for '{category_name}'</b>\n\n"
        f"Select an emoji that represents this category:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("icon:"))
async def save_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Save the new category"""
    icon = callback.data.split(":")[1]
    if icon == "none":
        icon = "📌"
    
    data = await state.get_data()
    
    # Get user
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one()
    
    # Create category
    trans_type = TransactionType.INCOME if data['category_type'] == 'income' else TransactionType.EXPENSE
    
    new_category = Category(
        user_id=user.id,
        name=data['category_name'],
        icon=icon,
        transaction_type=trans_type,
        is_default=False
    )
    
    session.add(new_category)
    await session.commit()
    
    await state.clear()
    await callback.answer("✅ Category created successfully!")
    
    await callback.message.edit_text(
        f"✅ <b>Category Created!</b>\n\n"
        f"Name: {icon} {data['category_name']}\n"
        f"Type: {'Income' if data['category_type'] == 'income' else 'Expense'}\n\n"
        f"You can now use this category when adding transactions.",
        parse_mode="HTML"
    )
    
    # Show back button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back to Categories", callback_data="manage_categories")]
    ])
    await callback.message.edit_reply_markup(reply_markup=keyboard)

@router.callback_query(F.data == "delete_category")
async def delete_category_list(callback: CallbackQuery, session: AsyncSession):
    """Show list of categories to delete"""
    # Get user
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one()
    
    # Get custom categories
    categories = await session.execute(
        select(Category).where(
            Category.user_id == user.id,
            Category.is_default == False
        ).order_by(Category.name)
    )
    custom_categories = categories.scalars().all()
    
    if not custom_categories:
        await callback.answer("You don't have any custom categories to delete")
        return
    
    keyboard_buttons = []
    for cat in custom_categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"❌ {cat.icon} {cat.name}",
                callback_data=f"del_cat:{cat.id}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="◀️ Back", callback_data="manage_categories")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(
        "🗑️ <b>Delete Category</b>\n\n"
        "Select a category to delete:\n"
        "⚠️ Transactions in this category will be moved to 'Other'",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("del_cat:"))
async def confirm_delete_category(callback: CallbackQuery, state: FSMContext):
    """Confirm category deletion"""
    category_id = int(callback.data.split(":")[1])
    await state.update_data(category_to_delete=category_id)
    await state.set_state(CategoryStates.confirming_delete)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes, delete", callback_data="confirm_delete"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="manage_categories")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ <b>Confirm Deletion</b>\n\n"
        "Are you sure you want to delete this category?\n"
        "All transactions will be moved to 'Other' category.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "confirm_delete")
async def execute_delete_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Execute category deletion"""
    data = await state.get_data()
    category_id = data['category_to_delete']
    
    # Delete the category
    await session.execute(
        delete(Category).where(Category.id == category_id)
    )
    await session.commit()
    
    await state.clear()
    await callback.answer("✅ Category deleted successfully")
    
    # Return to category management
    await manage_categories_menu(callback, session)