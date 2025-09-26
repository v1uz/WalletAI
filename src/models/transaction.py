# src/models/transaction.py
from sqlalchemy import Column, Integer, BigInteger, Numeric, String, DateTime, Enum, ForeignKey, func, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from cryptography.fernet import Fernet
from decimal import Decimal
import enum
import os
from .base import Base

class TransactionType(enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    amount = Column(Numeric(20, 2), nullable=False)
    encrypted_description = Column(String(500))
    transaction_type = Column(Enum(TransactionType), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    date = Column(DateTime(timezone=True), nullable=False)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    attachments = relationship("TransactionAttachment", cascade="all, delete-orphan")
    
    # Encryption key from environment
    _fernet = None
    
    @property
    def fernet(self):
        if not self._fernet:
            key = os.getenv('ENCRYPTION_KEY').encode()
            self._fernet = Fernet(key)
        return self._fernet
    
    @hybrid_property
    def description(self):
        """Decrypt description on access"""
        if self.encrypted_description:
            return self.fernet.decrypt(self.encrypted_description.encode()).decode()
        return None
    
    @description.setter
    def description(self, value):
        """Encrypt description on storage"""
        if value:
            self.encrypted_description = self.fernet.encrypt(value.encode()).decode()
        else:
            self.encrypted_description = None
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_transaction_user_date', 'user_id', 'date'),
        Index('idx_transaction_category', 'category_id'),
        Index('idx_transaction_type_date', 'transaction_type', 'date'),
    )