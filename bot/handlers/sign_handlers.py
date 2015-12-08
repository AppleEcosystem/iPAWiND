import asyncio
import logging
import os
import re
import uuid
from io import BytesIO
import zipfile

import base64
import plistlib

import aiohttp
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import ChatTypeFilter
from aiogram.utils.exceptions import BadRequest

from bot import buttons, strings
from bot.config import *
from bot.loader import *
from bot.states import SignFileStates
from bot.utils import utils
#from pymongo import MongoClient

#admins = [719363292]
#mongodb_client = MongoClient('mongodb+srv://murattopel8:aaZ3dwIlyvvCnUAJ@cluster0.cdasvxx.mongodb.net/?retryWrites=true&w=majority')
#banned_users = mongodb_client["bot"]["banned_users"]

logger = logging.getLogger(__name__)
regexp = re.compile(r'^Payload/.*\.app/Info\.plist$')  # find Info.plist path


@dp.callback_query_handler(lambda c: c.data == "signfile", ChatTypeFilter("private"), state='*')
async def sign_file(call: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup()
    cursor.execute(f"SELECT name, cert_id FROM Sessions WHERE user_id={call.from_user.id}")
    certs = cursor.fetchall()
    for cert in certs:
        keyboard.add(
            types.InlineKeyboardButton(text=cert[0], callback_data=f"selectsigncert-{call.from_user.id}-{cert[1]}"))
    btn_other = types.InlineKeyboardButton(text=strings.get("etc", call.from_user.id), callback_data="othercert")
    btn_free = types.InlineKeyboardButton(text=strings.get("fcert", call.from_user.id), callback_data="free_cert")
    keyboard.add(btn_other, btn_free)
    try:
        await call.message.edit_text(strings.get("pick_cert", call.from_user.id), reply_markup=keyboard)
    except BadRequest:
        await call.message.delete()
        await call.message.answer(strings.get("pick_cert", call.from_user.id), reply_markup=keyboard)
    await SignFileStates.cert.set()


@dp.callback_query_handler(lambda c: c.data == "free_cert", state=SignFileStates.cert)
async def free_cert(call: types.CallbackQuery, state: FSMContext):
    if not os.path.exists("sessions/free/free_cert.p12") or not os.path.exists(
            "sessions/free/free_cert.mobileprovision"):
        await call.message.edit_text("Sorry, but free certificate is not available now",
                                     reply_markup=buttons.get_menu(call.from_user.id))
        return await state.finish()
    with open("sessions/free/free_cert_pass.txt", 'r') as file:
        password = file.read()
    check_result = await utils.check_cert("sessions/free/free_cert.p12", password)
    if not check_result["ok"]:
        await call.message.edit_text("Sorry, but free certificate is not available now",
                                     reply_markup=buttons.get_menu(call.from_user.id))
        return await state.finish()
    async with state.proxy() as data:
        data["random_id"] = str(uuid.uuid4())
        data["p12_path"] = os.path.join(os.getcwd(), "sessions/free/free_cert.p12")
        data["prov_path"] = os.path.join(os.getcwd(), "sessions/free/free_cert.mobileprovision")
        data["password"] = password

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text=strings.get("change_bundle", call.from_user.id),
                                      callback_data="change_bundleid"))
    kb.add(types.InlineKeyboardButton(text=strings.get("sign_butt", call.from_user.id), callback_data="sign"))
    await call.message.edit_text(strings.get("additional_opt", call.from_user.id), reply_markup=kb)
    await SignFileStates.options.set()


@dp.callback_query_handler(lambda c: c.data.startswith("selectsigncert"), state=SignFileStates.cert)
async def select_cert_for_sign(call: types.CallbackQuery, state: FSMContext):
    data = call.data.split("-")
    cert = cursor.execute(
        f"SELECT p12_path, prov_path, password FROM Sessions WHERE user_id={data[1]} AND cert_id='{data[2]}'").fetchone()
    async with state.proxy() as data:
        data["random_id"] = str(uuid.uuid4())
        data["p12_path"] = cert[0].removeprefix('"').removesuffix('"')
        data["prov_path"] = cert[1]
        data["password"] = cert[2]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text=strings.get("change_bundle", call.from_user.id),
                                      callback_data="change_bundleid"))
    kb.add(types.InlineKeyboardButton(text=strings.get("sign_butt", call.from_user.id), callback_data="sign"))
    await call.message.edit_text(strings.get("additional_opt", call.from_user.id), reply_markup=kb)
    await SignFileStates.options.set()


@dp.callback_query_handler(lambda c: c.data == "othercert", state=SignFileStates.cert)
async def other_cert(call: types.CallbackQuery):
    await call.message.edit_text(strings.get("send_p12", call.from_user.id))
    await SignFileStates.p12.set()


@dp.message_handler(state=SignFileStates.p12, content_types='document')
async def get_p12(message: types.Message, state: FSMContext):
    random_id = str(uuid.uuid4())
    async with state.proxy() as data:
        data["random_id"] = random_id
        data["p12_path"] = os.path.join("sessions", str(message.from_user.id), random_id, f"{random_id}.p12")
    p12_info = await message.answer(strings.get("downloading_file", message.from_user.id))
    if message.document.file_name.endswith(".p12"):
        await utils.download(message.document,
                             os.path.join("sessions", str(message.from_user.id), random_id, f"{random_id}.p12"))
        await p12_info.delete()
        await message.answer(strings.get("send_pass", message.from_user.id), reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text=strings.get("skip", message.from_user.id))]], resize_keyboard=True,
            one_time_keyboard=True))
        await SignFileStates.next()
    else:
        await message.answer(strings.get("wrong_p12", message.from_user.id))
        await p12_info.delete()


@dp.message_handler(state=SignFileStates.password, content_types='text')
async def get_pass(message: types.Message, state=FSMContext):
    main_btns = buttons.get_menu(message.from_user.id)
    async with state.proxy() as data:
        if message.text == strings.get("skip", message.from_user.id):
            is_cert_valid = await utils.check_cert(data["p12_path"], "")
            if is_cert_valid["ok"]:
                await message.reply(strings.get("pass_skipped", message.from_user.id))
            else:
                await state.finish()
                return await message.answer(strings.get(is_cert_valid["message"], message.from_user.id),
                                            reply_markup=main_btns)
        else:
            is_cert_valid = await utils.check_cert(data["p12_path"], message.text)
            if is_cert_valid["ok"]:
                data["password"] = message.text
            else:
                await state.finish()
                return await message.answer(strings.get(is_cert_valid["message"], message.from_user.id),
                                            reply_markup=main_btns)
    delete_keyboard = await message.answer(strings.get("rm_key", message.from_user.id),
                                           reply_markup=types.ReplyKeyboardRemove())
    await delete_keyboard.delete()
    await message.answer(strings.get("send_prov", message.from_user.id))
    await SignFileStates.next()


@dp.message_handler(state=SignFileStates.prov, content_types='document')
async def get_prov(message: types.message, state=FSMContext):
    async with state.proxy() as data:
        mobileprovision_full_path = os.path.join("sessions", str(message.from_user.id),
                                                 f"{data['random_id']}.mobileprovision")
        data["prov_path"] = mobileprovision_full_path
    mobileprovision_info = await message.answer(strings.get("downloading_file", message.from_user.id))
    await utils.download(message.document, mobileprovision_full_path)
    await mobileprovision_info.delete()
    if not message.document.file_name.endswith(".mobileprovision"):
        os.remove(mobileprovision_full_path)
        await message.answer(strings.get("wrong_prov", message.from_user.id))
    else:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(text=strings.get("change_bundle", message.from_user.id),
                                          callback_data="change_bundleid"))
        kb.add(types.InlineKeyboardButton(text=strings.get("sign_butt", message.from_user.id), callback_data="sign"))
        await message.answer(strings.get("additional_opt", message.from_user.id), reply_markup=kb)
        await SignFileStates.next()


@dp.callback_query_handler(lambda c: c.data == "change_bundleid", state=SignFileStates.options)
async def change_bundle_id(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer(strings.get("new_bundle", call.from_user.id), reply_markup=types.ReplyKeyboardMarkup([[
        types.KeyboardButton(strings.get("random", call.from_user.id))
    ]], resize_keyboard=True))
    await SignFileStates.bundleid.set()


#@dp.message_handler(commands=['ban'])
#async def ban_user(message: types.Message):
#    if message.from_user.id not in admins:
#        return
#    user_id = message.text.split()[1]
#    banned_users.update_one({"user_id": int(user_id)}, {"$set":{}}, upsert=True)
#    await message.reply(f"User {user_id} has been banned!")

#@dp.message_handler(commands=['unban'])
#async def unban_user(message: types.Message):
#    if message.from_user.id not in admins:
#        return
#    user_id = message.text.split()[1]
#    status = banned_users.delete_one({"user_id": int(user_id)})
#    if status.deleted_count == 0:
#        await message.reply(f"Unbanning failed for {user_id}!")
#    else:
#        await message.reply(f"User {user_id} has been unbanned!")

@dp.message_handler(state=SignFileStates.bundleid, content_types="text")
async def send_bundleid(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if message.text == strings.get("random", message.from_user.id):
            data["random_bundleid"] = True
        else:
            data["custom_bundleid"] = message.text
    await message.answer(text=strings.get("changed_bundle", message.from_user.id),
                         reply_markup=types.ReplyKeyboardRemove())
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text=strings.get("changed_bundle", message.from_user.id),
                                      callback_data="change_bundleid"))
    kb.add(types.InlineKeyboardButton(text=strings.get("sign_butt", message.from_user.id), callback_data="sign"))
    await message.answer(strings.get("additional_opt", message.from_user.id), reply_markup=kb)
    await SignFileStates.options.set()


@dp.callback_query_handler(lambda c: c.data == "sign", state=SignFileStates.options)
async def send_ipa(call: types.CallbackQuery):
    await call.message.edit_text(strings.get("send_ipa", call.from_user.id))
    await SignFileStates.ipa.set()


@dp.message_handler(state=SignFileStates.ipa, content_types='document')
@dp.throttled(rate=1)
async def get_ipa_and_sign(message: types.Message, state: FSMContext):
#    status = banned_users.find_one({"user_id": message.from_user.id})
#    if status is not None:
#        await message.answer(f"You are banned from using this bot!")
#        return

    async with state.proxy() as data:
        await state.finish()
        ipa_file_full_name = os.path.join("sessions", str(message.from_user.id), f"{data['random_id']}.ipa")
        ipa_info = await message.answer(strings.get("downloading_file", message.from_user.id))
        random_id = data["random_id"]
        if message.document.file_name.endswith(".ipa"):
            if message.document.file_size < 324288000 or message.from_user.id in admin + reseller:
                await utils.download(message.document, ipa_file_full_name, message=ipa_info)
                with zipfile.ZipFile(ipa_file_full_name) as z:
                    total_size = sum(e.file_size for e in z.infolist())
                    if total_size > 4194304000:
                        username = message.from_user.username
                        user_info = f"@{username}" if username else f"User: {message.from_user.first_name}"
                        await bot.send_message(-1001709289685, f"zip bomb alert fucking idiot! {user_info} (ID: {message.from_user.id})")
                        await message.answer("File is too big!")
                        os.remove(ipa_file_full_name)
                        return
                    else:
                        print(f'Total files size: {total_size} bytes')
            else:
                return await ipa_info.edit_text("Due to lots of spam we have limited the bot temporarily to sign 50MB file max. you can sign esign or scarlet.")
        else:
            return await ipa_info.edit_text(strings.get("wrong_ipa", message.from_user.id))

        await ipa_info.delete()

        random_file_name = f"{uuid.uuid4()}.ipa"
        main_btns = buttons.get_menu(message.from_user.id)
        alert = await message.answer(strings.get("signing", message.from_user.id))
        process = await asyncio.create_subprocess_shell(
            str(utils.get_command(p12=data["p12_path"], password=data.get('password'), ipa=ipa_file_full_name,
                                  prov=data["prov_path"],
                                  output=os.path.join("sessions", str(message.from_user.id), random_file_name),
                                  random_bundleid=data.get("random_bundleid"),
                                  custom_bundleid=data.get("custom_bundleid"))),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await process.communicate()
        stderr = stderr.decode()
        stdout = stdout.decode()

        file = os.path.join("sessions", str(message.from_user.id), random_file_name)
        if not os.path.isfile(file):
            await alert.delete()
            await message.answer(strings.get("sign_error", message.from_user.id) + stdout, reply_markup=main_btns)
            return
        
        bundleID = re.search("BundleId:\s+(.+)", stdout)
        if data.get("custom_bundleid", False) or data.get("random_bundleid", False):
            bundleID = bundleID.group(1).split(" -> ")[1] if bundleID else "package_name"
        else:
            bundleID = bundleID.group(1) if bundleID else "package_name"


        # app_version = re.search("AppVersion:\s+(.+)", stdout)
        # app_version = app_version.group(1) if app_version else ""
        app_version = ""
        with zipfile.ZipFile(file) as ipa_zip:
            for zip_file in ipa_zip.namelist():
                if re.match(regexp, zip_file):
                    with ipa_zip.open(zip_file) as plist_file:
                        app_version = plistlib.load(plist_file).get('CFBundleShortVersionString')

        app_name = re.search("AppName:\s+(.+)", stdout)
        app_name = app_name.group(1) if app_name else ""
        await alert.edit_text(strings.get("upload_file", message.from_user.id))

        try:
            os.mkdir(f"{web_path}/uploads/{message.from_user.id}")
        except:
            pass
        plist_random = str(uuid.uuid4())
        r2_url = await r2.upload_file(file,
                                      f"{message.from_user.id}/{random_id}.ipa")
        
        details = cursor.execute(f"SELECT * from redirects where user_id={message.from_user.id}").fetchone()
        

        plist_url = await r2_plist.upload_file(
            BytesIO(
                template.format(
                    url=r2_url,
                    package_name=bundleID, version=app_version,
                    appname=app_name, 
                    redirect_url = details[6] if (details and details[6] != "default") else "https://raw.githubusercontent.com/NekooGroup/api/main/appicon.png"
                ).encode()
            ),
            f"{plist_random}.plist"
        )


        async with aiohttp.ClientSession() as httpclient:
            # if message.from_user.id not in admin + reseller or not details:
            req = httpclient.post(server_address, json={
                "url": f"itms-services://?action=download-manifest&url={plist_url}",
                "duration": "30"
            })
            response_url = "ipa_bot"
            # else:
            #     api = details[4]
            #     channel_link = details[2]
            #     channel_title = details[1]
            #     photo = details[3]
            #     logo_type = details[5]
            #     headers = {
            #         'Content-Type': 'application/json',
            #         'apiKey': api_key,
            #     }
            #     json_data = {
            #         'link': f'itms-services://?action=download-manifest&url={plist_url}',
            #         'app': {
            #             'name': app_name,
            #             'version': app_version,
            #             'bundleId': bundleID,
            #         },
            #         'channel': {
            #             'name': channel_title,
            #             'link': channel_link,
            #         },
            #         'icon': photo,
            #         'iconMimeType': "image/png" if logo_type == "photo" else "video/mp4",
            #     }

            #     req = httpclient.post(api, json=json_data, headers=headers)
            #     response_url = "shortenedLink"


            async with req as response:

                if response.status != 200:
                    text = await response.text()
                    await message.answer(strings.get("upload_failed", message.from_user.id), reply_markup=main_btns)
                    logger.error("Failed to upload file!: " + text)
                    return

                short_url = await response.json()

            try:
                os.remove(file)
                os.remove(ipa_file_full_name)
            except FileNotFoundError:
                logger.error(f"Failed to delete signed.ipa, sign failed?\n{stdout}")

            await alert.edit_text(
                f"{strings.get('sign_ok', message.from_user.id)}\n\nApp Name: {app_name}\nBundel ID: {bundleID}\nLink: <blockquote>{short_url.get(response_url)}&mode=compact</blockquote>",
                parse_mode='html',
                reply_markup=main_btns.add(types.InlineKeyboardButton(text=strings.get("install", message.from_user.id),
                                                                      url=f"{short_url.get(response_url)}&mode=compact")))
