import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import executor

from bot import handlers
from bot.loader import dp, account_manager, r2, pyrogram_bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler('bot.log', mode="w", maxBytes=10 * 5 * 1024, backupCount=1),
    ]
)

logging.getLogger("pyrogram").setLevel(logging.WARNING)

scheduler = AsyncIOScheduler()

async def on_startup(dp):
    await pyrogram_bot.start()

    scheduler.add_job(
        minutes=30,
        trigger='interval',
        func=account_manager.update_udids_data,
    )
    scheduler.start()

async def on_shutdown(dp):
    scheduler.shutdown()
    await pyrogram_bot.stop()

if __name__ == "__main__":
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )
