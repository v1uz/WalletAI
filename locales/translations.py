# Localization dictionary for WalletAI
translations = {
    'EN': {
        # General
        'welcome': "🎉 Welcome to WalletAI!",
        'welcome_back': "👋 Welcome back!",
        'cancel': "❌ Cancel",
        'back': "◀️ Back",
        'yes': "Yes",
        'no': "No",
        'skip': "Skip",
        'done': "Done",
        
        # Main menu
        'add_transaction': "➕ Add Transaction",
        'check_balance': "💰 Balance",
        'reports': "📊 Reports",
        'settings': "⚙️ Settings",
        
        # Transaction messages
        'add_success': "✅ Transaction added successfully!",
        'transaction_type_prompt': "Select transaction type:",
        'income': "💰 Income",
        'expense': "💸 Expense",
        'enter_amount': "Enter amount:",
        'select_category': "Select category:",
        'enter_description': "Enter description (or /skip):",
        'invalid_amount': "❌ Invalid amount. Please enter a valid number:",
        
        # Balance
        'balance_title': "💰 Your Financial Summary",
        'balance_current': "Balance",
        'total_income': "Total Income",
        'total_expense': "Total Expenses",
        'this_month': "This Month",
        'today': "Today",
        'spent': "Spent",
        
        # Categories
        'manage_categories': "📂 Manage Categories",
        'add_category': "➕ Add Category",
        'edit_category': "✏️ Edit Category",
        'delete_category': "🗑️ Delete Category",
        'category_created': "✅ Category created successfully!",
        'category_deleted': "✅ Category deleted successfully!",
        'no_custom_categories': "No custom categories yet",
        
        # Settings
        'settings_title': "⚙️ Settings",
        'language_setting': "🌐 Language",
        'currency_setting': "💱 Currency",
        'select_language': "Select Language",
        'select_currency': "Select Currency",
        'language_updated': "✅ Language updated!",
        'currency_updated': "✅ Currency updated!",
        
        # Recurring
        'recurring_transactions': "🔄 Recurring Transactions",
        'add_recurring': "➕ Add Recurring",
        'view_recurring': "📋 View All",
        'remove_recurring': "🗑️ Remove",
        'recurring_created': "✅ Recurring transaction created!",
        'frequency_daily': "Daily",
        'frequency_weekly': "Weekly",
        'frequency_monthly': "Monthly",
        'frequency_yearly': "Yearly",
        
        # Export
        'export_data': "📊 Export Data",
        'all_transactions': "All Transactions",
        'this_month_export': "This Month",
        'last_30_days': "Last 30 Days",
        'this_year': "This Year",
        'export_complete': "📊 Export Complete!",
        'no_transactions': "No transactions found for this period.",
        
        # Errors
        'error_occurred': "❌ An error occurred. Please try again.",
        'not_found': "Not found",
        'invalid_input': "Invalid input",
    },
    
    'RU': {
        # General
        'welcome': "🎉 Добро пожаловать в WalletAI!",
        'welcome_back': "👋 С возвращением!",
        'cancel': "❌ Отмена",
        'back': "◀️ Назад",
        'yes': "Да",
        'no': "Нет",
        'skip': "Пропустить",
        'done': "Готово",
        
        # Main menu
        'add_transaction': "➕ Добавить транзакцию",
        'check_balance': "💰 Баланс",
        'reports': "📊 Отчеты",
        'settings': "⚙️ Настройки",
        
        # Transaction messages
        'add_success': "✅ Транзакция успешно добавлена!",
        'transaction_type_prompt': "Выберите тип транзакции:",
        'income': "💰 Доход",
        'expense': "💸 Расход",
        'enter_amount': "Введите сумму:",
        'select_category': "Выберите категорию:",
        'enter_description': "Введите описание (или /skip):",
        'invalid_amount': "❌ Неверная сумма. Введите корректное число:",
        
        # Balance
        'balance_title': "💰 Ваша финансовая сводка",
        'balance_current': "Баланс",
        'total_income': "Общий доход",
        'total_expense': "Общие расходы",
        'this_month': "В этом месяце",
        'today': "Сегодня",
        'spent': "Потрачено",
        
        # Categories
        'manage_categories': "📂 Управление категориями",
        'add_category': "➕ Добавить категорию",
        'edit_category': "✏️ Изменить категорию",
        'delete_category': "🗑️ Удалить категорию",
        'category_created': "✅ Категория успешно создана!",
        'category_deleted': "✅ Категория успешно удалена!",
        'no_custom_categories': "Пользовательских категорий пока нет",
        
        # Settings
        'settings_title': "⚙️ Настройки",
        'language_setting': "🌐 Язык",
        'currency_setting': "💱 Валюта",
        'select_language': "Выберите язык",
        'select_currency': "Выберите валюту",
        'language_updated': "✅ Язык обновлен!",
        'currency_updated': "✅ Валюта обновлена!",
        
        # Recurring
        'recurring_transactions': "🔄 Повторяющиеся транзакции",
        'add_recurring': "➕ Добавить повторяющуюся",
        'view_recurring': "📋 Посмотреть все",
        'remove_recurring': "🗑️ Удалить",
        'recurring_created': "✅ Повторяющаяся транзакция создана!",
        'frequency_daily': "Ежедневно",
        'frequency_weekly': "Еженедельно",
        'frequency_monthly': "Ежемесячно",
        'frequency_yearly': "Ежегодно",
        
        # Export
        'export_data': "📊 Экспорт данных",
        'all_transactions': "Все транзакции",
        'this_month_export': "Этот месяц",
        'last_30_days': "Последние 30 дней",
        'this_year': "Этот год",
        'export_complete': "📊 Экспорт завершен!",
        'no_transactions': "Транзакций за этот период не найдено.",
        
        # Errors
        'error_occurred': "❌ Произошла ошибка. Попробуйте еще раз.",
        'not_found': "Не найдено",
        'invalid_input': "Неверный ввод",
    }
}

def get_text(key: str, lang: str = 'EN', **kwargs) -> str:
    """Get translated text for given key and language"""
    if lang not in translations:
        lang = 'EN'
    
    if key not in translations[lang]:
        return translations['EN'].get(key, key)
    
    text = translations[lang][key]
    
    # Format with kwargs if provided
    if kwargs:
        return text.format(**kwargs)
    
    return text

def get_currency_symbol(currency: str) -> str:
    """Get currency symbol"""
    symbols = {
        'USD': '$',
        'RUB': '₽',
        'EUR': '€',
        'GBP': '£'
    }
    return symbols.get(currency, currency)