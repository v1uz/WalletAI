# core/database.py
"""
Database Module - Fixed for SQLite and PostgreSQL compatibility
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from models.base import Base, User, Category
from core.config import settings

logger = logging.getLogger(__name__)

class Database:
    """Database connection and operations manager"""
    
    def __init__(self, database_url: str = None):
        """Initialize database connection"""
        self.database_url = database_url or settings.DATABASE_URL
        
        # Determine database type
        is_sqlite = 'sqlite' in self.database_url.lower()
        
        # Create engine with appropriate parameters
        if is_sqlite:
            # SQLite doesn't support pool_size and max_overflow
            self.engine = create_async_engine(
                self.database_url,
                echo=settings.DEBUG,  # Log SQL queries in debug mode
                pool_pre_ping=True,  # Check connections before using
            )
        else:
            # PostgreSQL, MySQL, etc. support pooling
            self.engine = create_async_engine(
                self.database_url,
                echo=settings.DEBUG,  # Log SQL queries in debug mode
                pool_pre_ping=True,  # Check connections before using
                pool_size=5,
                max_overflow=10
            )
        
        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        logger.info(f"Database initialized: {'SQLite' if is_sqlite else 'PostgreSQL/Other'}")
    
    async def create_tables(self):
        """Create all database tables"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    async def drop_tables(self):
        """Drop all database tables (use with caution!)"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.warning("All database tables dropped")
        except Exception as e:
            logger.error(f"Error dropping database tables: {e}")
            raise
    
    async def get_or_create_user(self, telegram_id: int, **kwargs) -> User:
        """Get existing user or create new one"""
        async with self.session_factory() as session:
            # Check if user exists
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                # Create new user
                user = User(
                    telegram_id=telegram_id,
                    **kwargs
                )
                session.add(user)
                await session.commit()
                logger.info(f"Created new user: {telegram_id}")
                
                # DO NOT create default categories
                # Users will create their own categories through the UI
                logger.info(f"User {telegram_id} initialized without default categories")
            
            return user
    
    async def get_user(self, telegram_id: int) -> User:
        """Get user by telegram ID"""
        async with self.session_factory() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
    
    async def close(self):
        """Close database connection"""
        await self.engine.dispose()
        logger.info("Database connection closed")

# Create global database instance
database = Database()

# ============= MIGRATION HELPER =============

async def migrate_remove_default_categories(session: AsyncSession, user_id: int):
    """
    Migration helper to remove default categories if needed
    This can be used to clean up existing users who have default categories
    """
    try:
        # List of default category names to remove
        default_categories = [
            'Food & Drinks', 'Transport', 'Shopping', 'Entertainment',
            'Bills & Utilities', 'Healthcare', 'Education', 'Other',
            'Salary', 'Freelance', 'Investment', 'Gift', 'Refund'
        ]
        
        # Delete default categories for the user
        result = await session.execute(
            select(Category).where(
                Category.user_id == user_id,
                Category.name.in_(default_categories)
            )
        )
        
        categories_to_remove = result.scalars().all()
        
        for category in categories_to_remove:
            # Check if category has transactions
            from models.base import Transaction
            trans_result = await session.execute(
                select(Transaction).where(
                    Transaction.category_id == category.id
                ).limit(1)
            )
            
            if not trans_result.scalar_one_or_none():
                # No transactions, safe to delete
                await session.delete(category)
                logger.info(f"Removed default category '{category.name}' for user {user_id}")
            else:
                # Has transactions, just mark as inactive
                category.is_active = False
                logger.info(f"Deactivated default category '{category.name}' for user {user_id} (has transactions)")
        
        await session.commit()
        logger.info(f"Migration completed for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        await session.rollback()
        raise

# ============= HELPER FUNCTIONS =============

async def check_user_has_categories(session: AsyncSession, user_id: int) -> bool:
    """Check if user has any active categories"""
    result = await session.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.is_active == True
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None

async def get_user_category_count(session: AsyncSession, user_id: int) -> dict:
    """Get count of user's categories by type"""
    from sqlalchemy import func
    
    result = await session.execute(
        select(
            Category.type,
            func.count(Category.id)
        ).where(
            Category.user_id == user_id,
            Category.is_active == True
        ).group_by(Category.type)
    )
    
    counts = {row[0]: row[1] for row in result}
    
    return {
        'income': counts.get('income', 0),
        'expense': counts.get('expense', 0),
        'total': sum(counts.values())
    }