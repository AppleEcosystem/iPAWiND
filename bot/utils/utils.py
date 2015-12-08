import asyncio
import logging
import uuid

import os 
import io 
import time

from bot.config import bot_token
from aiogram.types import Message 
from bot.loader import bot, pyrogram_bot

logger = logging.getLogger(__name__)



def create_progress_bar(percentage, total_length=20):
    filled_length = int(total_length * percentage // 100)
    bar = '▓' * filled_length + '░' * (total_length - filled_length)
    return f"{percentage}% {bar} 100%"

async def download_progress(current, _, total, chat_id, message_id, last_edit_time, edit_counter, last_progress_percentage):

    progress_percentage = int((current * 100) / total)
    current_time = time.time()
    current_mb = current / (1024 * 1024)
    total_mb = total / (1024 * 1024)    

    if current_time - last_edit_time[0] >= 1:
        last_edit_time[0] = current_time
        edit_counter[0] = 0

    if progress_percentage > last_progress_percentage[0] and edit_counter[0] < 3:
        progress_bar = create_progress_bar(progress_percentage)
        progress_text = f"Downloaded: {current_mb:.2f} MB / {total_mb:.2f} MB\n{progress_bar}"
        try:
            await pyrogram_bot.edit_message_text(chat_id, message_id, progress_text)
            edit_counter[0] += 1
            last_progress_percentage[0] = progress_percentage
        except Exception as e:
            pass


async def download(document, path, message: Message = None):
    if message:

        edit_counter = [0]  
        last_progress_percentage = [0] 
        last_edit_time = [time.time()]

        chat_id = message.chat.id
        file_size = document.file_size
        message_id = message.message_id

        x = await pyrogram_bot.download_media(
            message=document.file_id, 
            progress=download_progress, 
            progress_args=(file_size, chat_id, message_id, last_edit_time, edit_counter, last_progress_percentage)
        )
    else: x = await pyrogram_bot.download_media(message=document.file_id)
    os.renames(x, path)


async def download_aiogram_bytes(document):
    file = await bot.get_file(document.file_id)
    file_path = file.file_path.removeprefix(f"/var/lib/telegram-bot-api/{bot_token}/")
    return await bot.download_file(file_path, destination=io.BytesIO())

async def download_aiogram(document, destination_folder):
    file = await bot.get_file(document.file_id)
    file_path = file.file_path.removeprefix(f"/var/lib/telegram-bot-api/{bot_token}/")
    return await bot.download_file(file_path, destination_dir=destination_folder)

async def check_cert(cert: str, password: str) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "node",
        "tools/checker/index.js",
        cert,
        password,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    output, _ = await proc.communicate()
    output = output.decode()
    if "Password is likely incorrect" in output:
        return {"ok": False, "message": "invalid_pass"}
    elif "Revoked" in output:
        return {"ok": False, "message": "cert_revoked", "output": output}
    elif "Signed" in output:
        return {"ok": True, "output": output}
    else:
        logger.error("Failed to check cert:\n" + output)
        return {"ok": False, "message": "unknown_error"}


def get_command(p12: str,
                prov: str,
                output: str,
                ipa: str,
                password: str = None,
                random_bundleid: bool = False,
                custom_bundleid: str = None) -> str:
    base_command: str = f'./tools/zsign -k "{p12}" -m "{prov}" -o {output}'
    if password:
        base_command += f' -p "{password}"'
    if random_bundleid:
        base_command += f" -b com.{str(uuid.uuid4())[:5]}.{str(uuid.uuid4())[:5]}"
    if custom_bundleid:
        base_command += f" -b {custom_bundleid}"
    base_command += f' "{ipa}"'
    return base_command
