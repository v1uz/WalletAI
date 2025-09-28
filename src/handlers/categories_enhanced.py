# handlers/categories_enhanced.py
"""
Enhanced Category Management System for WalletAI Bot
Replaces default categories with user-managed categories
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete, update
from models.base import User, Category
from typing import Optional, List

logger = logging.getLogger(__name__)
router = Router()

# ============= STATES =============

class CategoryStates(StatesGroup):
    """States for category management"""
    waiting_for_category_name = State()
    waiting_for_category_type = State()
    waiting_for_new_category_name = State()
    selecting_category_to_delete = State()
    selecting_category_to_rename = State()
    waiting_for_renamed_category = State()

# ============= UTILITY FUNCTIONS =============

def get_currency_symbol(currency: str) -> str:
    """Get currency symbol from currency code"""
    symbols = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
        'RUB': '₽', 'INR': '₹', 'BRL': 'R$', 'CAD': 'C$'
    }
    return symbols.get(currency, currency)

async def get_user_categories(session, user_id: int, transaction_type: Optional[str] = None) -> List[Category]:
    """Get all user categories, optionally filtered by type"""
    query = select(Category).where(
        Category.user_id == user_id,
        Category.is_active == True
    )
    
    if transaction_type:
        query = query.where(Category.type == transaction_type)
    
    result = await session.execute(query.order_by(Category.name))
    return result.scalars().all()

async def create_category_keyboard(
    categories: List[Category], 
    include_management: bool = True,
    page: int = 0,
    items_per_page: int = 8
) -> InlineKeyboardMarkup:
    """
    Create keyboard with categories
    
    Args:
        categories: List of Category objects
        include_management: Whether to include Add/Manage buttons
        page: Current page number
        items_per_page: Number of categories per page
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    # If this is for selection and user has no categories, show only management buttons
    if include_management and not categories:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="➕ Add Category", callback_data="cat:add_new"),
            InlineKeyboardButton(text="⚙️ Manage Categories", callback_data="cat:manage")
        ])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="❌ Cancel", callback_data="cat:cancel")
        ])
        return keyboard
    
    # Paginate categories
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_categories = categories[start_idx:end_idx]
    
    # Add category buttons (2 per row)
    for i in range(0, len(page_categories), 2):
        row = []
        for j in range(2):
            if i + j < len(page_categories):
                cat = page_categories[i + j]
                emoji = "📈" if cat.type == "income" else "📉"
                row.append(
                    InlineKeyboardButton(
                        text=f"{emoji} {cat.name}",
                        callback_data=f"cat:select:{cat.id}"
                    )
                )
        keyboard.inline_keyboard.append(row)
    
    # Add pagination if needed
    pagination_row = []
    if page > 0:
        pagination_row.append(
            InlineKeyboardButton(text="⬅️ Previous", callback_data=f"cat:page:{page-1}")
        )
    if end_idx < len(categories):
        pagination_row.append(
            InlineKeyboardButton(text="➡️ Next", callback_data=f"cat:page:{page+1}")
        )
    if pagination_row:
        keyboard.inline_keyboard.append(pagination_row)
    
    # Add management buttons if requested
    if include_management:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="➕ Add Category", callback_data="cat:add_new"),
            InlineKeyboardButton(text="⚙️ Manage", callback_data="cat:manage")
        ])
    
    # Add cancel button
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="❌ Cancel", callback_data="cat:cancel")
    ])
    
    return keyboard

# ============= CATEGORY SELECTION FOR TRANSACTIONS =============

@router.callback_query(F.data == "select_category")
async def show_category_selection(callback: CallbackQuery, state: FSMContext, session):
    """Show category selection interface for transactions"""
    try:
        await callback.answer()
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ User not found. Please use /start")
            return
        
        # Get state data to determine transaction type
        state_data = await state.get_data()
        transaction_type = state_data.get('transaction_type', 'expense')
        
        # Get user's categories for this transaction type
        categories = await get_user_categories(session, user.id, transaction_type)
        
        # Create keyboard
        keyboard = await create_category_keyboard(categories, include_management=True)
        
        # Prepare message
        if categories:
            message_text = (
                f"📁 <b>Select a category for your {transaction_type}:</b>\n\n"
                f"You have {len(categories)} categories.\n"
                f"Select one or add a new category."
            )
        else:
            message_text = (
                f"📁 <b>No categories found!</b>\n\n"
                f"You need to add at least one {transaction_type} category first.\n"
                f"Click 'Add Category' to create your first category."
            )
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing category selection: {e}")
        await callback.message.answer("❌ Error loading categories")

# ============= ADD NEW CATEGORY =============

@router.callback_query(F.data == "cat:add_new")
async def start_add_category(callback: CallbackQuery, state: FSMContext):
    """Start the process of adding a new category"""
    try:
        await callback.answer()
        
        # Store that we're adding a category
        await state.update_data(adding_category=True)
        await state.set_state(CategoryStates.waiting_for_category_name)
        
        await callback.message.edit_text(
            "➕ <b>Adding New Category</b>\n\n"
            "Please enter a name for your new category:\n"
            "(e.g., 'Groceries', 'Salary', 'Entertainment')\n\n"
            "Type /cancel to cancel",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error starting category addition: {e}")
        await callback.message.answer("❌ Error. Please try again.")

@router.message(CategoryStates.waiting_for_category_name)
async def process_category_name(message: Message, state: FSMContext, session):
    """Process the category name input"""
    try:
        if message.text == "/cancel":
            await state.clear()
            await message.answer("❌ Category creation cancelled")
            return
        
        category_name = message.text.strip()
        
        # Validate category name
        if len(category_name) < 2:
            await message.answer("❌ Category name must be at least 2 characters long")
            return
        
        if len(category_name) > 50:
            await message.answer("❌ Category name must be less than 50 characters")
            return
        
        # Check for duplicate
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("❌ User not found. Please use /start")
            await state.clear()
            return
        
        # Check if category already exists
        existing = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.name == category_name,
                Category.is_active == True
            )
        )
        
        if existing.scalar_one_or_none():
            await message.answer("❌ A category with this name already exists!")
            return
        
        # Store category name and ask for type
        await state.update_data(category_name=category_name, user_id=user.id)
        await state.set_state(CategoryStates.waiting_for_category_type)
        
        # Ask for category type
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Income", callback_data="cat:type:income"),
                InlineKeyboardButton(text="📉 Expense", callback_data="cat:type:expense")
            ],
            [
                InlineKeyboardButton(text="❌ Cancel", callback_data="cat:cancel")
            ]
        ])
        
        await message.answer(
            f"📁 Category name: <b>{category_name}</b>\n\n"
            f"Now select the category type:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error processing category name: {e}")
        await message.answer("❌ Error creating category")
        await state.clear()

@router.callback_query(F.data.startswith("cat:type:"))
async def process_category_type(callback: CallbackQuery, state: FSMContext, session):
    """Process category type selection"""
    try:
        await callback.answer()
        
        category_type = callback.data.split(":")[2]
        state_data = await state.get_data()
        
        # Create the category
        new_category = Category(
            user_id=state_data['user_id'],
            name=state_data['category_name'],
            type=category_type,
            is_active=True
        )
        
        session.add(new_category)
        await session.commit()
        
        emoji = "📈" if category_type == "income" else "📉"
        
        await callback.message.edit_text(
            f"✅ <b>Category Created Successfully!</b>\n\n"
            f"{emoji} Name: {state_data['category_name']}\n"
            f"Type: {category_type.capitalize()}\n\n"
            f"You can now use this category for your transactions.",
            parse_mode="HTML"
        )
        
        # Clear state but check if we were in transaction flow
        original_transaction_type = state_data.get('transaction_type')
        original_amount = state_data.get('amount')
        
        if original_transaction_type and original_amount:
            # We were adding a category during transaction flow
            # Return to category selection
            await state.update_data(
                transaction_type=original_transaction_type,
                amount=original_amount,
                adding_category=False
            )
            
            # Show updated category list
            categories = await get_user_categories(session, state_data['user_id'], original_transaction_type)
            keyboard = await create_category_keyboard(categories, include_management=True)
            
            await callback.message.answer(
                "Now select the category for your transaction:",
                reply_markup=keyboard
            )
        else:
            await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating category: {e}")
        await callback.message.answer("❌ Error creating category")
        await state.clear()

# ============= MANAGE CATEGORIES =============

@router.callback_query(F.data == "cat:manage")
async def show_category_management(callback: CallbackQuery, session):
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
        
        # Get all user categories
        categories = await get_user_categories(session, user.id)
        
        if not categories:
            await callback.message.edit_text(
                "📁 <b>No categories to manage</b>\n\n"
                "You haven't created any categories yet.\n"
                "Use 'Add Category' to create your first category.",
                parse_mode="HTML"
            )
            return
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Rename Category", callback_data="cat:rename_menu"),
                InlineKeyboardButton(text="🗑 Delete Category", callback_data="cat:delete_menu")
            ],
            [
                InlineKeyboardButton(text="📋 View All Categories", callback_data="cat:view_all")
            ],
            [
                InlineKeyboardButton(text="⬅️ Back", callback_data="select_category"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cat:cancel")
            ]
        ])
        
        await callback.message.edit_text(
            f"⚙️ <b>Category Management</b>\n\n"
            f"You have {len(categories)} categories.\n"
            f"What would you like to do?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing category management: {e}")
        await callback.message.answer("❌ Error loading management options")

# ============= DELETE CATEGORY =============

@router.callback_query(F.data == "cat:delete_menu")
async def show_delete_category_menu(callback: CallbackQuery, state: FSMContext, session):
    """Show menu to select category for deletion"""
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
        categories = await get_user_categories(session, user.id)
        
        if not categories:
            await callback.message.edit_text("❌ No categories to delete")
            return
        
        # Create keyboard with categories
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for i in range(0, len(categories), 2):
            row = []
            for j in range(2):
                if i + j < len(categories):
                    cat = categories[i + j]
                    emoji = "📈" if cat.type == "income" else "📉"
                    row.append(
                        InlineKeyboardButton(
                            text=f"🗑 {emoji} {cat.name}",
                            callback_data=f"cat:delete:{cat.id}"
                        )
                    )
            keyboard.inline_keyboard.append(row)
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="⬅️ Back", callback_data="cat:manage"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cat:cancel")
        ])
        
        await state.set_state(CategoryStates.selecting_category_to_delete)
        
        await callback.message.edit_text(
            "🗑 <b>Delete Category</b>\n\n"
            "Select a category to delete:\n"
            "⚠️ Warning: This will remove the category permanently!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing delete menu: {e}")
        await callback.message.answer("❌ Error")

@router.callback_query(F.data.startswith("cat:delete:"))
async def confirm_delete_category(callback: CallbackQuery, state: FSMContext, session):
    """Confirm category deletion"""
    try:
        await callback.answer()
        
        category_id = int(callback.data.split(":")[2])
        
        # Get category
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        
        if not category:
            await callback.message.edit_text("❌ Category not found")
            return
        
        # Check for transactions using this category
        from models.base import Transaction
        trans_result = await session.execute(
            select(Transaction).where(Transaction.category_id == category_id).limit(1)
        )
        has_transactions = trans_result.scalar_one_or_none() is not None
        
        warning = ""
        if has_transactions:
            warning = "\n\n⚠️ <b>Warning:</b> This category has associated transactions!"
        
        # Confirmation keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Yes, Delete", 
                    callback_data=f"cat:delete_confirm:{category_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Cancel", 
                    callback_data="cat:delete_menu"
                )
            ]
        ])
        
        emoji = "📈" if category.type == "income" else "📉"
        
        await callback.message.edit_text(
            f"⚠️ <b>Confirm Deletion</b>\n\n"
            f"Are you sure you want to delete this category?\n\n"
            f"{emoji} Category: <b>{category.name}</b>\n"
            f"Type: {category.type.capitalize()}{warning}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error confirming deletion: {e}")
        await callback.message.answer("❌ Error")

@router.callback_query(F.data.startswith("cat:delete_confirm:"))
async def execute_delete_category(callback: CallbackQuery, state: FSMContext, session):
    """Execute category deletion"""
    try:
        await callback.answer()
        
        category_id = int(callback.data.split(":")[2])
        
        # Get category
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        
        if not category:
            await callback.message.edit_text("❌ Category not found")
            return
        
        category_name = category.name
        
        # Soft delete (set is_active to False)
        category.is_active = False
        await session.commit()
        
        await callback.message.edit_text(
            f"✅ <b>Category Deleted</b>\n\n"
            f"Category '<b>{category_name}</b>' has been deleted successfully.",
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error deleting category: {e}")
        await callback.message.answer("❌ Error deleting category")

# ============= RENAME CATEGORY =============

@router.callback_query(F.data == "cat:rename_menu")
async def show_rename_category_menu(callback: CallbackQuery, state: FSMContext, session):
    """Show menu to select category for renaming"""
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
        categories = await get_user_categories(session, user.id)
        
        if not categories:
            await callback.message.edit_text("❌ No categories to rename")
            return
        
        # Create keyboard with categories
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for i in range(0, len(categories), 2):
            row = []
            for j in range(2):
                if i + j < len(categories):
                    cat = categories[i + j]
                    emoji = "📈" if cat.type == "income" else "📉"
                    row.append(
                        InlineKeyboardButton(
                            text=f"✏️ {emoji} {cat.name}",
                            callback_data=f"cat:rename:{cat.id}"
                        )
                    )
            keyboard.inline_keyboard.append(row)
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="⬅️ Back", callback_data="cat:manage"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cat:cancel")
        ])
        
        await state.set_state(CategoryStates.selecting_category_to_rename)
        
        await callback.message.edit_text(
            "✏️ <b>Rename Category</b>\n\n"
            "Select a category to rename:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing rename menu: {e}")
        await callback.message.answer("❌ Error")

@router.callback_query(F.data.startswith("cat:rename:"))
async def start_rename_category(callback: CallbackQuery, state: FSMContext, session):
    """Start renaming process"""
    try:
        await callback.answer()
        
        category_id = int(callback.data.split(":")[2])
        
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
        await state.set_state(CategoryStates.waiting_for_renamed_category)
        
        emoji = "📈" if category.type == "income" else "📉"
        
        await callback.message.edit_text(
            f"✏️ <b>Renaming Category</b>\n\n"
            f"Current name: {emoji} <b>{category.name}</b>\n\n"
            f"Please enter the new name for this category:\n"
            f"Type /cancel to cancel",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error starting rename: {e}")
        await callback.message.answer("❌ Error")

@router.message(CategoryStates.waiting_for_renamed_category)
async def process_renamed_category(message: Message, state: FSMContext, session):
    """Process the new category name"""
    try:
        if message.text == "/cancel":
            await state.clear()
            await message.answer("❌ Rename cancelled")
            return
        
        new_name = message.text.strip()
        
        # Validate
        if len(new_name) < 2:
            await message.answer("❌ Category name must be at least 2 characters long")
            return
        
        if len(new_name) > 50:
            await message.answer("❌ Category name must be less than 50 characters")
            return
        
        state_data = await state.get_data()
        category_id = state_data['renaming_category_id']
        old_name = state_data['old_name']
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        # Check for duplicate
        duplicate = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.name == new_name,
                Category.is_active == True,
                Category.id != category_id
            )
        )
        
        if duplicate.scalar_one_or_none():
            await message.answer("❌ A category with this name already exists!")
            return
        
        # Update category
        await session.execute(
            update(Category).where(Category.id == category_id).values(name=new_name)
        )
        await session.commit()
        
        await message.answer(
            f"✅ <b>Category Renamed Successfully!</b>\n\n"
            f"Old name: {old_name}\n"
            f"New name: <b>{new_name}</b>",
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error renaming category: {e}")
        await message.answer("❌ Error renaming category")
        await state.clear()

# ============= VIEW ALL CATEGORIES =============

@router.callback_query(F.data == "cat:view_all")
async def view_all_categories(callback: CallbackQuery, session):
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
        categories = await get_user_categories(session, user.id)
        
        if not categories:
            await callback.message.edit_text(
                "📁 <b>No categories found</b>\n\n"
                "You haven't created any categories yet.",
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
                message_text += f"  • {cat.name}\n"
            message_text += "\n"
        
        if expense_cats:
            message_text += "📉 <b>Expense Categories:</b>\n"
            for cat in expense_cats:
                message_text += f"  • {cat.name}\n"
        
        message_text += f"\n<b>Total:</b> {len(categories)} categories"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="cat:manage")]
        ])
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error viewing categories: {e}")
        await callback.message.answer("❌ Error loading categories")

# ============= CANCEL HANDLERS =============

@router.callback_query(F.data == "cat:cancel")
async def cancel_category_operation(callback: CallbackQuery, state: FSMContext):
    """Cancel any category operation"""
    try:
        await callback.answer("Operation cancelled")
        await state.clear()
        await callback.message.edit_text("❌ Operation cancelled")
    except Exception as e:
        logger.error(f"Error cancelling operation: {e}")

# ============= CATEGORY SELECTION HANDLER =============

@router.callback_query(F.data.startswith("cat:select:"))
async def handle_category_selection(callback: CallbackQuery, state: FSMContext):
    """Handle when user selects a category for transaction"""
    try:
        await callback.answer()
        
        category_id = int(callback.data.split(":")[2])
        
        # Store selected category in state
        await state.update_data(category_id=category_id)
        
        # Continue with transaction flow
        state_data = await state.get_data()
        
        # This would trigger the next step in transaction flow
        # You'll need to import and call the appropriate handler
        from handlers.transactions import process_transaction_description
        
        await callback.message.edit_text(
            "📝 <b>Add Description</b>\n\n"
            "Enter a description for this transaction:\n"
            "(or type 'skip' to skip)",
            parse_mode="HTML"
        )
        
        # Set state for description
        from handlers.transactions import TransactionStates
        await state.set_state(TransactionStates.waiting_for_description)
        
    except Exception as e:
        logger.error(f"Error selecting category: {e}")
        await callback.message.answer("❌ Error selecting category")

# ============= PAGINATION HANDLER =============

@router.callback_query(F.data.startswith("cat:page:"))
async def handle_category_pagination(callback: CallbackQuery, state: FSMContext, session):
    """Handle category list pagination"""
    try:
        await callback.answer()
        
        page = int(callback.data.split(":")[2])
        
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.message.answer("❌ User not found")
            return
        
        # Get state data for transaction type
        state_data = await state.get_data()
        transaction_type = state_data.get('transaction_type')
        
        # Get categories
        categories = await get_user_categories(session, user.id, transaction_type)
        
        # Update keyboard with new page
        keyboard = await create_category_keyboard(categories, include_management=True, page=page)
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error handling pagination: {e}")
        await callback.answer("❌ Error")