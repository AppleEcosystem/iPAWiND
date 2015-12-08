from base64 import b64encode, b64decode
from aiogram import types
from aiogram.dispatcher import FSMContext

import uuid 
import os 

import tempfile
from bot import buttons, strings
from bot.config import *
from bot.loader import *
from bot.states import RedirectStates
from bot.utils import utils


@dp.message_handler(state='*', commands='r', )
async def set_redirect(message: types.Message):
    if message.from_user.id in admin + reseller:
        await message.reply(strings.get("select_domain", message.from_user.id), reply_markup=buttons.domain_btns('domain_'))
        await RedirectStates.domain.set()


@dp.callback_query_handler(lambda c: c.data.startswith("domain_"), state=RedirectStates.domain)
async def get_domain(call: types.CallbackQuery, state: FSMContext):
    url_index = call.data.split("_")[1]
    api_url = api_urls[int(url_index)]

    async with state.proxy() as data:
        data['api_url'] = api_url 

    await call.message.edit_text(strings.get("redirect_plist_logo", call.from_user.id))
    await RedirectStates.plist_logo.set()

@dp.message_handler(state=RedirectStates.plist_logo, content_types=['text', 'photo'])
async def get_photo(message: types.Message, state=FSMContext):

    if message.text == "/skip":
        url = "default"

    elif message.photo:
        with tempfile.TemporaryDirectory() as temp_folder:
            photo_path = await utils.download_aiogram_bytes(message.photo[-1])
            url = await r2_plist.upload_file(
                photo_path, 
                os.path.join("plist_logo", str(uuid.uuid4()))
            )

    async with state.proxy() as data:
        data['plist_url'] = url 

    await message.reply(strings.get("redirect_title", message.from_user.id))
    await RedirectStates.channel_name.set()

@dp.message_handler(state=RedirectStates.channel_name, content_types='text')
async def get_channel_name(message: types.Message, state=FSMContext):
    channel_title = message.text 
    
    async with state.proxy() as data:
        data['channel_name'] = channel_title

    await message.reply(strings.get("redirect_link", message.from_user.id))
    await RedirectStates.channel_link.set()

@dp.message_handler(state=RedirectStates.channel_link, content_types='text')
async def get_channel_link(message: types.Message, state=FSMContext):
    channel_link = message.text 

    async with state.proxy() as data:
        data['channel_link'] = channel_link

    await message.reply(strings.get("redirect_logo", message.from_user.id))
    await RedirectStates.channel_logo.set()

@dp.message_handler(state=RedirectStates.channel_logo, content_types=['photo', 'animation'])
async def get_channel_logo(message: types.Message, state=FSMContext):
    if message.photo:
        doc = message.photo[-1]
        logo_type = "photo"
    elif message.animation: 
        doc = message.animation 
        logo_type = "gif"

    photo_bytes = await utils.download_aiogram_bytes(document=doc)
    image = b64encode(photo_bytes.getvalue())

    async with state.proxy() as data:
        data['channel_logo'] = image.decode()
        
        data['logo_type'] = logo_type

        query = "INSERT OR REPLACE INTO redirects VALUES (?, ?, ?, ?, ?, ?, ?)"
        cursor.execute(query, (
            message.from_user.id,
            data['channel_name'],
            data['channel_link'],
            data['channel_logo'],
            data['api_url'],
            data['logo_type'],
            data['plist_url']
        ))
        conn.commit()

    await message.reply(strings.get("redirect_saved", message.from_user.id))
    await state.finish()

@dp.message_handler(state='*', commands='remove_r')
async def remove_redirect(message: types.Message):
    if message.from_user.id in admin + reseller:
        cursor.execute("DELETE FROM redirects WHERE user_id = ?", (message.from_user.id,))
        conn.commit()
        await message.reply(strings.get("delete_redirect", message.from_user.id))

@dp.message_handler(state='*', commands='get_r')
async def get_redirect(message: types.Message):
    
    if message.from_user.id in admin + reseller:
        details = cursor.execute(f"SELECT * FROM redirects WHERE user_id='{message.from_user.id}'").fetchone()

        if not details:
            await message.reply(strings.get("no_redirect_details", message.from_user.id))
            return 

        msg = strings.get("redirect_details", message.from_user.id).format(
            api = details[4],
            plist_logo = details[6],
            channel_link = details[2],
            channel_title = details[1],
        )

        if details[5] == "photo":
            await message.reply_photo(
                photo = b64decode(details[3]), 
                caption = msg
            )
        else:
            await message.reply_video(
                video = b64decode(details[3]),
                caption = msg
            )