# migrations/remove_default_categories.py
"""
Migration script to remove default categories and ensure user-managed categories only
Run this once to clean up the database
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import settings
from models.base import User, Category, Transaction

logger = logging.getLogger(__name__)

# List of default category names that should be removed
DEFAULT_CATEGORY_NAMES = [
    # Income categories
    'Salary', 'Freelance', 'Investment', 'Gift', 'Refund', 
    'Business', 'Other Income', 'Bonus', 'Rental Income',
    
    # Expense categories  
    'Food & Drinks', 'Transport', 'Shopping', 'Entertainment',
    'Bills & Utilities', 'Healthcare', 'Education', 'Other',
    'Groceries', 'Rent', 'Insurance', 'Subscriptions',
    'Clothing', 'Home', 'Personal', 'Travel'
]

async def migrate_database():
    """Main migration function"""
    logger.info("Starting database migration...")
    
    # Create engine and session
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Get all users
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            logger.info(f"Found {len(users)} users to process")
            
            for user in users:
                await migrate_user(session, user)
            
            await session.commit()
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()

async def migrate_user(session: AsyncSession, user: User):
    """Migrate a single user's categories"""
    logger.info(f"Processing user {user.telegram_id} ({user.username or 'No username'})")
    
    # Get all user's categories
    result = await session.execute(
        select(Category).where(Category.user_id == user.id)
    )
    categories = result.scalars().all()
    
    removed_count = 0
    kept_count = 0
    
    for category in categories:
        # Check if this is a default category
        if category.name in DEFAULT_CATEGORY_NAMES:
            # Check if category has transactions
            trans_result = await session.execute(
                select(Transaction).where(
                    Transaction.category_id == category.id
                ).limit(1)
            )
            has_transactions = trans_result.scalar_one_or_none() is not None
            
            if has_transactions:
                # Keep the category but mark it as user-created
                logger.info(f"  Keeping category '{category.name}' (has transactions)")
                kept_count += 1
            else:
                # Delete the category
                await session.delete(category)
                logger.info(f"  Removed default category '{category.name}'")
                removed_count += 1
        else:
            # User-created category, keep it
            kept_count += 1
    
    logger.info(f"  User {user.telegram_id}: Removed {removed_count}, Kept {kept_count} categories")

async def verify_migration():
    """Verify migration was successful"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Count remaining default categories without transactions
            result = await session.execute(
                select(Category).where(
                    Category.name.in_(DEFAULT_CATEGORY_NAMES)
                )
            )
            default_categories = result.scalars().all()
            
            problematic = []
            for cat in default_categories:
                # Check if it has transactions
                trans_result = await session.execute(
                    select(Transaction).where(
                        Transaction.category_id == cat.id
                    ).limit(1)
                )
                if not trans_result.scalar_one_or_none():
                    problematic.append(f"User {cat.user_id}: {cat.name}")
            
            if problematic:
                logger.warning(f"Found {len(problematic)} default categories without transactions:")
                for p in problematic:
                    logger.warning(f"  {p}")
            else:
                logger.info("✅ Migration verified: No unused default categories found")
                
        finally:
            await engine.dispose()

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run migration
    asyncio.run(migrate_database())
    
    # Verify migration
    asyncio.run(verify_migration())