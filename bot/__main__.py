import logging
from logging.handlers import RotatingFileHandler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import executor

from bot import handlers
from bot.loader import dp, account_manager, r2
from datetime import datetime, timedelta 

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S', 
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler('bot.log', mode="w", maxBytes=10*5*1024, backupCount=1),
    ]
)

logging.getLogger("pyrogram").setLevel(logging.WARNING)

if __name__ == "__main__":
    scheduler = AsyncIOScheduler()
    
    scheduler.add_job(account_manager.update_udids_data, 'interval', minutes=30)
    # scheduler.add_job(account_manager.update_udids_data, 'interval', minutes=180, next_run_time=datetime.now())

    scheduler.start()
    executor.start_polling(dp)
