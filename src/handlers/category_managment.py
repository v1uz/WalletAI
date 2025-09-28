# handlers/category_management.py
"""
Complete category management handlers for rename, delete, and view operations
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from models.base import User, Category, Transaction

logger = logging.getLogger(__name__)
router = Router()

class CategoryManagementStates(StatesGroup):
    selecting_category_to_rename = State()
    entering_new_name = State()
    selecting_category_to_delete = State()

# ============= VIEW ALL CATEGORIES =============

@router.callback_query(F.data == "view_all_cats")
async def view_all_categories(callback: CallbackQuery, session: AsyncSession):
    """Display all user categories"""
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
        
        # Get all categories
        cat_result = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.is_active == True
            ).order_by(Category.type, Category.name)
        )
        categories = cat_result.scalars().all()
        
        if not categories:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Add Category", callback_data="add_cat:expense")],
                [InlineKeyboardButton(text="⬅️ Back", callback_data="manage_cats")]
            ])
            
            await callback.message.edit_text(
                "📁 <b>Your Categories</b>\n\n"
                "You haven't created any categories yet.\n"
                "Click 'Add Category' to create your first one!",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return
        
        # Group by type
        income_cats = [c for c in categories if c.type == "income"]
        expense_cats = [c for c in categories if c.type == "expense"]
        
        message_text = "📁 <b>Your Categories</b>\n\n"
        
        if income_cats:
            message_text += "📈 <b>Income Categories:</b>\n"
            for cat in income_cats:
                icon = cat.icon if cat.icon else "📁"
                message_text += f"  {icon} {cat.name}\n"
            message_text += "\n"
        
        if expense_cats:
            message_text += "📉 <b>Expense Categories:</b>\n"
            for cat in expense_cats:
                icon = cat.icon if cat.icon else "📁"
                message_text += f"  {icon} {cat.name}\n"
        
        message_text += f"\n<b>Total:</b> {len(categories)} categories"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="manage_cats")]
        ])
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error viewing categories: {e}")
        await callback.message.answer("❌ Error loading categories")

# ============= RENAME CATEGORY =============

@router.callback_query(F.data == "rename_cat")
async def show_rename_category_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Show menu to select category for renaming"""
    try:
        await callback.answer()
        
        # Get user and categories
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ User not found")
            return
        
        cat_result = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.is_active == True
            ).order_by(Category.name)
        )
        categories = cat_result.scalars().all()
        
        if not categories:
            await callback.message.edit_text(
                "❌ No categories to rename.\n"
                "Create some categories first!",
                parse_mode="HTML"
            )
            return
        
        # Create keyboard with categories
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for cat in categories:
            emoji = "📈" if cat.type == "income" else "📉"
            icon = cat.icon if cat.icon else "📁"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{emoji} {icon} {cat.name}",
                    callback_data=f"rename_cat_id:{cat.id}"
                )
            ])
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="❌ Cancel", callback_data="manage_cats")
        ])
        
        await state.set_state(CategoryManagementStates.selecting_category_to_rename)
        
        await callback.message.edit_text(
            "✏️ <b>Rename Category</b>\n\n"
            "Select a category to rename:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing rename menu: {e}")
        await callback.message.answer("❌ Error")

@router.callback_query(F.data.startswith("rename_cat_id:"))
async def start_rename_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Start renaming process"""
    try:
        await callback.answer()
        
        category_id = int(callback.data.split(":")[1])
        
        # Get category
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        
        if not category:
            await callback.message.edit_text("❌ Category not found")
            return
        
        # Store category ID in state
        await state.update_data(renaming_category_id=category_id, old_name=category.name)
        await state.set_state(CategoryManagementStates.entering_new_name)
        
        emoji = "📈" if category.type == "income" else "📉"
        icon = category.icon if category.icon else "📁"
        
        await callback.message.edit_text(
            f"✏️ <b>Renaming Category</b>\n\n"
            f"Current: {emoji} {icon} {category.name}\n\n"
            f"Send the new name for this category\n"
            f"(or /cancel to cancel):",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error starting rename: {e}")
        await callback.message.answer("❌ Error")

@router.message(CategoryManagementStates.entering_new_name)
async def process_new_category_name(message: Message, state: FSMContext, session: AsyncSession):
    """Process the new category name"""
    try:
        if message.text == "/cancel":
            await state.clear()
            await message.answer("❌ Rename cancelled")
            return
        
        new_name = message.text.strip()
        
        # Validate
        if len(new_name) < 2:
            await message.answer("❌ Name must be at least 2 characters")
            return
        
        if len(new_name) > 50:
            await message.answer("❌ Name must be less than 50 characters")
            return
        
        state_data = await state.get_data()
        category_id = state_data['renaming_category_id']
        
        # Update category
        await session.execute(
            update(Category).where(Category.id == category_id).values(name=new_name)
        )
        await session.commit()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back to Management", callback_data="manage_cats")]
        ])
        
        await message.answer(
            f"✅ <b>Category Renamed!</b>\n\n"
            f"Old: {state_data['old_name']}\n"
            f"New: {new_name}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error renaming category: {e}")
        await message.answer("❌ Error renaming category")

# ============= DELETE CATEGORY =============

@router.callback_query(F.data == "delete_cat")
async def show_delete_category_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Show menu to select category for deletion"""
    try:
        await callback.answer()
        
        # Get user and categories
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ User not found")
            return
        
        cat_result = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.is_active == True
            ).order_by(Category.name)
        )
        categories = cat_result.scalars().all()
        
        if not categories:
            await callback.message.edit_text(
                "❌ No categories to delete.\n"
                "Create some categories first!",
                parse_mode="HTML"
            )
            return
        
        # Create keyboard with categories
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for cat in categories:
            emoji = "📈" if cat.type == "income" else "📉"
            icon = cat.icon if cat.icon else "📁"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🗑 {emoji} {icon} {cat.name}",
                    callback_data=f"delete_cat_id:{cat.id}"
                )
            ])
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="❌ Cancel", callback_data="manage_cats")
        ])
        
        await state.set_state(CategoryManagementStates.selecting_category_to_delete)
        
        await callback.message.edit_text(
            "🗑 <b>Delete Category</b>\n\n"
            "Select a category to delete:\n"
            "⚠️ Warning: This cannot be undone!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing delete menu: {e}")
        await callback.message.answer("❌ Error")

@router.callback_query(F.data.startswith("delete_cat_id:"))
async def confirm_delete_category(callback: CallbackQuery, session: AsyncSession):
    """Confirm category deletion"""
    try:
        await callback.answer()
        
        category_id = int(callback.data.split(":")[1])
        
        # Get category
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        
        if not category:
            await callback.message.edit_text("❌ Category not found")
            return
        
        # Check for transactions
        trans_result = await session.execute(
            select(Transaction).where(Transaction.category_id == category_id).limit(1)
        )
        has_transactions = trans_result.scalar_one_or_none() is not None
        
        warning = ""
        if has_transactions:
            warning = "\n\n⚠️ <b>This category has transactions!</b>\nThey will become uncategorized."
        
        emoji = "📈" if category.type == "income" else "📉"
        icon = category.icon if category.icon else "📁"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"confirm_delete:{category_id}"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="manage_cats")
            ]
        ])
        
        await callback.message.edit_text(
            f"⚠️ <b>Confirm Deletion</b>\n\n"
            f"Delete category: {emoji} {icon} {category.name}?{warning}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error confirming deletion: {e}")
        await callback.message.answer("❌ Error")

@router.callback_query(F.data.startswith("confirm_delete:"))
async def execute_delete_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Execute category deletion"""
    try:
        await callback.answer("Deleting category...")
        
        category_id = int(callback.data.split(":")[1])
        
        # Set category to inactive instead of hard delete
        await session.execute(
            update(Category).where(Category.id == category_id).values(is_active=False)
        )
        await session.commit()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back to Management", callback_data="manage_cats")]
        ])
        
        await callback.message.edit_text(
            "✅ <b>Category Deleted!</b>\n\n"
            "The category has been removed.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error deleting category: {e}")
        await callback.message.answer("❌ Error deleting category")