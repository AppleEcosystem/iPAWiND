from aiogram import types
from aiogram.dispatcher import FSMContext

import aiohttp
import random 
import string 
import logging 
from bot import buttons, strings
from bot.config import *
from bot.loader import *
from bot.states import UrlShortner

logger = logging.getLogger(__name__)


async def make_request(api, body):
    headers = {
        'Content-Type': 'application/json',
        'apiKey': api_key
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(api, headers=headers, json=body) as response:
            if response.status != 200:
                logger.error("Failed to short url: " + await response.text())
                return None  
            return await response.json()


@dp.message_handler(state='*', commands='short')
async def short_url(message: types.Message, state: FSMContext):
    if message.from_user.id in admin + reseller:
        details = cursor.execute(f"SELECT * from redirects where user_id={message.from_user.id}").fetchone()
        if not details:
            return await message.reply("First set /r")
        
        async with state.proxy() as data:
            data['channel_link'] = details[2]
            data['channel_title'] = details[1]
            data['photo'] = details[3]
            data['logo_type'] = details[5]

        await message.reply(strings.get("select_domain", message.from_user.id), reply_markup=buttons.domain_btns('short_'))
        await UrlShortner.select_domain.set()
    else:
        await message.reply("Send link : ")
        await UrlShortner.select_link.set()


@dp.callback_query_handler(lambda c: c.data.startswith("short_"), state=UrlShortner.select_domain)
async def select_domain(call: types.CallbackQuery, state: FSMContext):
    url_index = call.data.split("_")[1]
    api_url = api_urls[int(url_index)]
    async with state.proxy() as data:
        data['api_url'] = api_url 
    await call.message.edit_text("Send app name")
    await UrlShortner.select_appname.set()



@dp.message_handler(state=UrlShortner.select_appname, content_types=['text'])
async def select_appname(message: types.Message, state: FSMContext):
    appname = message.text
    async with state.proxy() as data:
        data['appname'] = appname 
    await message.reply("send link")
    await UrlShortner.select_link.set()


@dp.message_handler(state=UrlShortner.select_link, content_types=['text'])
async def select_url_link(message: types.Message, state: FSMContext):
    link = message.text
    async with state.proxy() as data:
        photo = data.get('photo')
        appname = data.get('appname')
        api_url = data.get('api_url')
        logo_type = data.get('logo_type')
        channel_link = data.get('channel_link')
        channel_title = data.get('channel_title')


    # if message.from_user.id in admin + reseller:   
    #     api_url = api_url            
    #     data = {
    #         "link": link,
    #         "app": {
    #             "name": appname,
    #             "version": "1.0.0",
    #             "bundleId": f"com.application.{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"
    #         },
    #         'channel': {
    #             'name': channel_title,
    #             'link': channel_link,
    #         },
    #         'icon': photo,
    #         'iconMimeType': "image/png" if logo_type == "photo" else "video/mp4",
    #     }
    #     response_url = "shortenedLink"
    # else:
    api_url = server_address
    data = {
        "url": link,
        "duration": "30"
    }
    response_url = "ipa_bot"

    link = await make_request(api_url, data)
    if not link:
        await message.reply("Something went wrong!")
    else:
        await message.reply(f"Here is your link : {link[response_url]}")

    await state.finish()