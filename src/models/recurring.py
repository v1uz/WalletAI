from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Numeric, Boolean, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from models.base import Base, TransactionType

class RecurringFrequency(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

class RecurringTransaction(Base):
    __tablename__ = 'recurring_transactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    amount = Column(Numeric(12, 2), nullable=False)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    description = Column(Text)
    frequency = Column(String(20), nullable=False)  # daily, weekly, monthly, yearly
    next_execution = Column(DateTime(timezone=True))
    last_execution = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    category = relationship("Category")