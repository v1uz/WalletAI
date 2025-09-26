# src/services/notification_service.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..models.budget import Budget

class NotificationService:
    def __init__(self, bot, db_session, redis_client):
        self.bot = bot
        self.db_session = db_session
        self.redis = redis_client
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        
    def start(self):
        """Initialize all scheduled tasks"""
        # Daily summary at 9 AM user's timezone
        self.scheduler.add_job(
            self.send_daily_summaries,
            trigger='cron',
            hour=9,
            minute=0,
            id='daily_summary'
        )
        
        # Budget alerts check every hour
        self.scheduler.add_job(
            self.check_budget_alerts,
            trigger='interval',
            hours=1,
            id='budget_alerts'
        )
        
        # Goal progress weekly update
        self.scheduler.add_job(
            self.send_goal_updates,
            trigger='cron',
            day_of_week='mon',
            hour=10,
            minute=0,
            id='goal_updates'
        )
        
        self.scheduler.start()
    
    async def check_budget_alerts(self):
        """Check budget thresholds and send alerts"""
        async with self.db_session() as session:
            # Get active budgets
            budgets = await session.execute(
                select(Budget).where(
                    Budget.is_active == True
                ).options(selectinload(Budget.user))
            )
            
            for budget in budgets.scalars():
                # Calculate current spending
                spent = await self._calculate_budget_spending(budget)
                percentage = (spent / budget.amount_limit * 100) if budget.amount_limit > 0 else 0
                
                # Check if alert needed
                if percentage >= budget.alert_threshold * 100:
                    # Check if already alerted recently
                    alert_key = f"budget_alert:{budget.id}"
                    if not await self.redis.get(alert_key):
                        await self._send_budget_alert(budget, spent, percentage)
                        
                        # Prevent spam - don't alert again for 24 hours
                        await self.redis.setex(alert_key, 86400, "1")