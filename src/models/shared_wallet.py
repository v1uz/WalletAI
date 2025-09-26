# src/models/shared_wallet.py
from sqlalchemy import Column, Integer, BigInteger, String, Numeric, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import relationship
from typing import List
from .base import Base

class SharedWallet(Base):
    __tablename__ = 'shared_wallets'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    members = relationship("WalletMember", back_populates="wallet")
    transactions = relationship("SharedTransaction", back_populates="wallet")

class WalletMember(Base):
    __tablename__ = 'wallet_members'
    
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('shared_wallets.id'))
    user_id = Column(BigInteger, nullable=False)
    balance = Column(Numeric(10, 2), default=0)
    
    wallet = relationship("SharedWallet", back_populates="members")

# src/services/debt_calculation_service.py
from dataclasses import dataclass

@dataclass
class Settlement:
    debtor: int
    creditor: int
    amount: float

def get_member_balances(wallet_id: int) -> dict:
    """Get member balances for a wallet"""
    # This would typically query the database
    return {}

class DebtCalculationService:
    @staticmethod
    def calculate_settlements(wallet_id: int) -> List[Settlement]:
        """Calculate optimal settlements using simplified debts algorithm"""
        balances = get_member_balances(wallet_id)
        
        creditors = [(user, balance) for user, balance in balances.items() if balance > 0]
        debtors = [(user, -balance) for user, balance in balances.items() if balance < 0]
        
        creditors.sort(key=lambda x: x[1], reverse=True)
        debtors.sort(key=lambda x: x[1], reverse=True)
        
        settlements = []
        while creditors and debtors:
            creditor, credit = creditors.pop(0)
            debtor, debt = debtors.pop(0)
            
            settle_amount = min(credit, debt)
            settlements.append(Settlement(debtor, creditor, settle_amount))
            
            if credit > debt:
                creditors.insert(0, (creditor, credit - settle_amount))
            elif debt > credit:
                debtors.insert(0, (debtor, debt - settle_amount))
        
        return settlements