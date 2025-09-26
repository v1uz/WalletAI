# Create a file called clear_webhook.py
import asyncio
from aiogram import Bot
import os
from dotenv import load_dotenv

load_dotenv()

async def clear():
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    await bot.delete_webhook(drop_pending_updates=True)
    info = await bot.get_webhook_info()
    print(f"Webhook URL: {info.url}")
    print("Webhook cleared!")
    await bot.session.close()

asyncio.run(clear())