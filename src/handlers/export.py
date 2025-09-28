from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.base import User, Transaction, Category
import pandas as pd
from datetime import datetime, timedelta
import os
import tempfile

router = Router()

@router.callback_query(F.data == "export_data")
async def export_menu(callback: CallbackQuery):
    """Show export options"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 All Transactions", callback_data="export:all")
        ],
        [
            InlineKeyboardButton(text="📅 This Month", callback_data="export:month")
        ],
        [
            InlineKeyboardButton(text="📆 Last 30 Days", callback_data="export:30days")
        ],
        [
            InlineKeyboardButton(text="🗓️ This Year", callback_data="export:year")
        ],
        [
            InlineKeyboardButton(text="◀️ Back", callback_data="settings")
        ]
    ])
    
    await callback.message.edit_text(
        "📊 <b>Export Data</b>\n\n"
        "Select the period you want to export:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("export:"))
async def process_export(callback: CallbackQuery, session: AsyncSession):
    """Generate and send Excel file"""
    period = callback.data.split(":")[1]
    
    # Get user
    result = await session.execute(
        select(User).where(User.telegram_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Please use /start first")
        return
    
    # Show processing message
    await callback.answer("📊 Generating Excel file...")
    
    # Build query based on period
    query = select(Transaction, Category).join(
        Category, Transaction.category_id == Category.id
    ).where(Transaction.user_id == user.id)
    
    now = datetime.now()
    if period == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        query = query.where(Transaction.date >= start_date)
        period_text = f"{now.strftime('%B %Y')}"
    elif period == "30days":
        start_date = now - timedelta(days=30)
        query = query.where(Transaction.date >= start_date)
        period_text = "Last 30 Days"
    elif period == "year":
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        query = query.where(Transaction.date >= start_date)
        period_text = str(now.year)
    else:  # all
        period_text = "All Time"
    
    # Execute query
    result = await session.execute(query.order_by(Transaction.date.desc()))
    transactions = result.all()
    
    if not transactions:
        await callback.message.answer("No transactions found for this period.")
        return
    
    # Prepare data for Excel
    data = []
    for trans, category in transactions:
        data.append({
            'Date': trans.date.strftime('%Y-%m-%d %H:%M'),
            'Type': 'Income' if trans.transaction_type.value == 'income' else 'Expense',
            'Category': f"{category.icon} {category.name}",
            'Amount': float(trans.amount),
            'Currency': user.currency,
            'Description': trans.description or ''
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Calculate summary statistics
    summary_data = {
        'Total Income': df[df['Type'] == 'Income']['Amount'].sum(),
        'Total Expenses': df[df['Type'] == 'Expense']['Amount'].sum(),
        'Balance': df[df['Type'] == 'Income']['Amount'].sum() - df[df['Type'] == 'Expense']['Amount'].sum(),
        'Transaction Count': len(df),
        'Average Transaction': df['Amount'].mean()
    }
    
    # Create Excel file with multiple sheets
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', delete=False) as tmp_file:
        with pd.ExcelWriter(tmp_file.name, engine='openpyxl') as writer:
            # Transactions sheet
            df.to_excel(writer, sheet_name='Transactions', index=False)
            
            # Summary sheet
            summary_df = pd.DataFrame([summary_data])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Category breakdown
            category_breakdown = df.groupby(['Type', 'Category'])['Amount'].agg(['sum', 'count']).reset_index()
            category_breakdown.columns = ['Type', 'Category', 'Total Amount', 'Count']
            category_breakdown.to_excel(writer, sheet_name='Categories', index=False)
            
            # Format the Excel sheets
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                
                # Adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Send the file
        filename = f"WalletAI_{period_text.replace(' ', '_')}_{now.strftime('%Y%m%d')}.xlsx"
        
        await callback.message.answer_document(
            FSInputFile(tmp_file.name, filename=filename),
            caption=f"📊 <b>Export Complete!</b>\n\n"
                   f"Period: {period_text}\n"
                   f"Transactions: {len(df)}\n"
                   f"Total Income: {user.currency} {summary_data['Total Income']:.2f}\n"
                   f"Total Expenses: {user.currency} {summary_data['Total Expenses']:.2f}\n"
                   f"Balance: {user.currency} {summary_data['Balance']:.2f}",
            parse_mode="HTML"
        )
        
        # Clean up temp file
        os.unlink(tmp_file.name)