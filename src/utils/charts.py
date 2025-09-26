# src/utils/charts.py
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta

class ChartService:
    def __init__(self):
        self.setup_style()
    
    def setup_style(self):
        """Configure matplotlib style for financial charts"""
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
        plt.rcParams['figure.figsize'] = (10, 6)
        plt.rcParams['font.size'] = 10
    
    async def generate_expense_breakdown(self, transactions: list) -> BytesIO:
        """Generate expense pie chart with category breakdown"""
        # Aggregate by category
        category_totals = {}
        for trans in transactions:
            if trans.transaction_type == TransactionType.EXPENSE:
                cat = trans.category.name if trans.category else "Uncategorized"
                category_totals[cat] = category_totals.get(cat, 0) + float(trans.amount)
        
        if not category_totals:
            return await self._generate_empty_chart("No expenses to display")
        
        # Create pie chart
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Sort categories by amount for better visualization
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        categories, amounts = zip(*sorted_categories)
        
        # Create color palette
        colors = sns.color_palette('husl', len(categories))
        
        # Create pie chart with percentages
        wedges, texts, autotexts = ax.pie(
            amounts,
            labels=categories,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            pctdistance=0.85
        )
        
        # Beautify the chart
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        # Add title
        ax.set_title('Expense Breakdown by Category', fontsize=16, fontweight='bold')
        
        # Add total amount in center
        total = sum(amounts)
        ax.text(0, 0, f'Total\n${total:,.2f}', 
                ha='center', va='center', fontsize=14, fontweight='bold')
        
        # Save to bytes
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer