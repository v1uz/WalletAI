from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.core.config import settings
from src.models.base import Base, Category, TransactionType

class Database:
    def __init__(self):
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            future=True
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def create_tables(self):
        """Create all tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def init_default_categories(self, user_id: int):
        """Create default categories for new user"""
        async with self.session_factory() as session:
            default_categories = [
                # Expense categories
                ("🍔 Food & Dining", "🍔", TransactionType.EXPENSE),
                ("🚗 Transportation", "🚗", TransactionType.EXPENSE),
                ("🏠 Housing", "🏠", TransactionType.EXPENSE),
                ("🎬 Entertainment", "🎬", TransactionType.EXPENSE),
                ("🛒 Shopping", "🛒", TransactionType.EXPENSE),
                ("💊 Healthcare", "💊", TransactionType.EXPENSE),
                ("📚 Education", "📚", TransactionType.EXPENSE),
                ("💡 Utilities", "💡", TransactionType.EXPENSE),
                ("🏷️ Other Expense", "🏷️", TransactionType.EXPENSE),
                # Income categories
                ("💰 Salary", "💰", TransactionType.INCOME),
                ("💼 Business", "💼", TransactionType.INCOME),
                ("📈 Investment", "📈", TransactionType.INCOME),
                ("🎁 Gift", "🎁", TransactionType.INCOME),
                ("💸 Other Income", "💸", TransactionType.INCOME),
            ]
            
            for name, icon, trans_type in default_categories:
                category = Category(
                    user_id=user_id,
                    name=name,
                    icon=icon,
                    transaction_type=trans_type,
                    is_default=True
                )
                session.add(category)
            
            await session.commit()

database = Database()
