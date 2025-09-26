# src/handlers/transactions/states.py
from aiogram.fsm.state import State, StatesGroup

class TransactionEntry(StatesGroup):
    # Transaction type selection
    selecting_type = State()
    
    # Amount entry
    entering_amount = State()
    validating_amount = State()
    
    # Category selection
    selecting_category = State()
    entering_custom_category = State()
    
    # Description and details
    entering_description = State()
    selecting_date = State()
    
    # Attachments
    uploading_receipt = State()
    
    # Review and confirmation
    reviewing_transaction = State()
    confirming_transaction = State()

# src/handlers/transactions/transaction_handler.py
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from decimal import Decimal, InvalidOperation

router = Router()

@router.message(Command("add"))
async def start_transaction(message: Message, state: FSMContext):
    """Initiate transaction entry flow"""
    await state.set_state(TransactionEntry.selecting_type)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Income", callback_data="type:income"),
            InlineKeyboardButton(text="💸 Expense", callback_data="type:expense")
        ],
        [InlineKeyboardButton(text="↔️ Transfer", callback_data="type:transfer")]
    ])
    
    await message.answer(
        "📝 <b>New Transaction</b>\n\n"
        "Select transaction type:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("type:"), TransactionEntry.selecting_type)
async def process_transaction_type(callback: CallbackQuery, state: FSMContext):
    """Process transaction type selection"""
    transaction_type = callback.data.split(":")[1]
    await state.update_data(transaction_type=transaction_type)
    
    await callback.message.edit_text(
        f"💵 Enter amount for {transaction_type}:\n\n"
        "Example: 150.50 or $150.50"
    )
    await state.set_state(TransactionEntry.entering_amount)