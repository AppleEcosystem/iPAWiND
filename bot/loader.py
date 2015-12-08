import sqlite3

from aiogram import Bot, Dispatcher
from aiogram.bot.api import TelegramAPIServer
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from bot.config import bot_token, accounts, reseller_accounts, api_id, api_hash
from bot.utils.r2 import R2Storage
from pyrogram import Client 

server = TelegramAPIServer.from_base("http://localhost:81")
bot = Bot(bot_token, server=server)
pyrogram_bot = Client(name="pyrobot", api_id=api_id, api_hash=api_hash, bot_token=bot_token, no_updates=True, max_concurrent_transmissions=20)
pyrogram_bot.start()

dp = Dispatcher(bot, storage=MemoryStorage())

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

r2 = R2Storage('https://Example.r2.cloudflarestorage.com',
               'KeyExample',
               'LongKeyExaemplef74b9f9b30bbaa7ad72eb053c9f7616',
               'BucketName', 'https://yourDomainforR2.com')


r2_plist = R2Storage('https://Example.r2.cloudflarestorage.com',
                     'KeyExample',
                     'LongKeyExaemplef74b9f9b30bbaa7ad72eb053c9f7616',
                     'Bucketname', 'https://yourDomainforR2.com')


from bot.utils.account_manager import AccountManager, ChineseApi

account_manager = AccountManager.from_list(accounts, reseller_accounts)
chinese_api = ChineseApi()
