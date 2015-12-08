import os
import re
import uuid

from aiogram import types
from aiogram.dispatcher import FSMContext

from bot import buttons, strings
from bot.utils import utils
from bot.loader import dp, cursor, conn
from bot.states import CheckCertStates, AddCertStates


@dp.callback_query_handler(lambda c: c.data == "checkcert", state='*')
async def check_certificate(call: types.CallbackQuery):
    await call.message.edit_text(strings.get("send_p12", call.from_user.id))
    await CheckCertStates.p12.set()


@dp.message_handler(state=CheckCertStates.p12, content_types="document")
async def send_cert(message: types.Message, state: FSMContext):
    random_id = str(uuid.uuid4())
    async with state.proxy() as data:
        data["p12_path"] = os.path.join("sessions", str(message.from_user.id), random_id, f"{random_id}.p12")
    p12_info = await message.answer(strings.get("downloading_file", message.from_user.id))
    if message.document.file_name.endswith(".p12"):
        await utils.download(message.document,
                             os.path.join("sessions", str(message.from_user.id), random_id, f"{random_id}.p12"))
        await p12_info.delete()
        await message.answer(strings.get("send_pass", message.from_user.id), reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text=strings.get("skip", message.from_user.id))]], resize_keyboard=True))
        await CheckCertStates.next()
    else:
        await message.edit_text(strings.get("wrong_p12", message.from_user.id))
        await p12_info.delete()


@dp.message_handler(state=CheckCertStates.password, content_types="text")
async def send_cert_pass(message: types.Message, state: FSMContext):
    main_btns = buttons.get_menu(message.from_user.id)
    async with state.proxy() as data:
        if message.text == strings.get("skip", message.from_user.id):
            is_cert_valid = await utils.check_cert(data["p12_path"], "")
        else:
            is_cert_valid = await utils.check_cert(data["p12_path"], message.text)
    delete_keyborad = await message.answer(strings.get("rm_key", message.from_user.id),
                                           reply_markup=types.ReplyKeyboardRemove())
    await delete_keyborad.delete()
    if is_cert_valid.get("output", None):
        cert_status = is_cert_valid["output"]
        cert_status = cert_status.replace("Certificate Name", strings.get("cert_name", message.from_user.id))
        cert_status = cert_status.replace("Certificate Status", strings.get("cert_status", message.from_user.id))
        cert_status = cert_status.replace("Certificate Expiration Date", strings.get("cert_date", message.from_user.id))
        cert_status = cert_status.replace("Revoked", strings.get("status_revoked", message.from_user.id))
        cert_status = cert_status.replace("Signed", strings.get("status_signed", message.from_user.id))
        await message.answer(cert_status, reply_markup=main_btns)
    else:
        await message.answer(strings.get(is_cert_valid["message"], message.from_user.id), reply_markup=main_btns)
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "mycerts", state='*')
async def my_certs(call: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup()
    cursor.execute(f"SELECT name, cert_id FROM Sessions WHERE user_id={call.from_user.id}")
    certs = cursor.fetchall()
    for cert in certs:
        keyboard.add(
            types.InlineKeyboardButton(text=cert[0], callback_data=f"selectcert-{call.from_user.id}-{cert[1]}"))
    btn_back = types.InlineKeyboardButton(text=strings.get("back", call.from_user.id), callback_data="back_start")
    btn_add = types.InlineKeyboardButton(text=strings.get("add", call.from_user.id), callback_data="addcert")
    keyboard.row(btn_back, btn_add)
    try:
        await call.message.edit_text(strings.get("your_cert", call.from_user.id), reply_markup=keyboard)
    except:
        await call.message.delete()
        await call.message.answer(strings.get("your_cert", call.from_user.id), reply_markup=keyboard)



@dp.callback_query_handler(lambda c: c.data == "addcert")
async def add_cert(call: types.CallbackQuery):
    await call.message.answer(strings.get("send_p12", call.from_user.id))
    await AddCertStates.p12.set()


@dp.message_handler(state=AddCertStates.p12, content_types="document")
async def add_p12(message: types.message, state: FSMContext):
    random_id = str(uuid.uuid4())[:8]
    async with state.proxy() as data:
        data["random_id"] = random_id
        data["p12_path"] = os.path.join("sessions", str(message.from_user.id), "certs", f"{random_id}.p12")
    p12_info = await message.answer(strings.get("downloading_file", message.from_user.id))
    if message.document.file_name.endswith(".p12"):
        await utils.download(message.document,
                             os.path.join("sessions", str(message.from_user.id), "certs", f"{random_id}.p12"))
        await p12_info.delete()
        await message.answer(strings.get("send_pass", message.from_user.id), reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text=strings.get("skip", message.from_user.id))]], resize_keyboard=True,
            one_time_keyboard=True))
        await AddCertStates.next()
    else:
        await message.answer(strings.get("wrong_p12", message.from_user.id))
        await p12_info.delete()


@dp.message_handler(state=AddCertStates.password, content_types='text')
async def add_pass(message: types.Message, state=FSMContext):
    main_btns = buttons.get_menu(message.from_user.id)
    async with state.proxy() as data:
        if message.text == strings.get("skip", message.from_user.id):
            is_cert_valid = await utils.check_cert(data["p12_path"], "")
            if is_cert_valid["ok"]:
                await message.reply(strings.get("pass_skipped", message.from_user.id))
                cert_name = re.search("Certificate Name:\s+(.+)", is_cert_valid["output"]).group(1)
                if len(cert_name.encode()) > 30:
                    cert_name = cert_name[:30] + "..."
                data["cert_name"] = cert_name
                data["password"] = ""
            else:
                await state.finish()
                return await message.answer(strings.get(is_cert_valid["message"], message.from_user.id),
                                            reply_markup=main_btns)
        else:
            is_cert_valid = await utils.check_cert(data["p12_path"], message.text)
            if is_cert_valid["ok"]:
                data["password"] = message.text
                cert_name = re.search("Certificate Name:\s+(.+)", is_cert_valid["output"]).group(1)
                if len(cert_name.encode()) > 30:
                    cert_name = cert_name[:30] + "..."
                data["cert_name"] = cert_name
            else:
                await state.finish()
                return await message.answer(strings.get(is_cert_valid["message"], message.from_user.id),
                                            reply_markup=main_btns)
    delete_keyboard = await message.answer(strings.get("rm_key", message.from_user.id),
                                           reply_markup=types.ReplyKeyboardRemove())
    await delete_keyboard.delete()
    await message.answer(strings.get("send_prov", message.from_user.id))
    await AddCertStates.next()


@dp.message_handler(state=AddCertStates.prov, content_types='document')
async def get_prov(message: types.message, state=FSMContext):
    async with state.proxy() as data:
        mobileprovision_full_path = os.path.join("sessions", str(message.from_user.id), "certs",
                                                 f"{data['random_id']}.mobileprovision")
        p12_path = data["p12_path"]
        cert_name = data["cert_name"]
        password = data["password"]
        cert_id = str(uuid.uuid4()).replace("-", ".")
    mobileprovision_info = await message.answer(strings.get("downloading_file", message.from_user.id))
    await utils.download(message.document, mobileprovision_full_path)
    await mobileprovision_info.delete()
    if not message.document.file_name.endswith(".mobileprovision"):
        os.remove(mobileprovision_full_path)
        await message.answer(strings.get("wrong_prov", message.from_user.id))
    else:
        cursor.execute(
            "INSERT INTO Sessions VALUES (?, ?, ?, ?, ?, ?)",
            (message.from_user.id, p12_path, mobileprovision_full_path, password, cert_name, cert_id)
        )
        conn.commit()

        kb = types.InlineKeyboardMarkup(row_width=2).add(
            types.InlineKeyboardButton(text=strings.get("back", message.from_user.id), callback_data="mycerts"))
        await state.finish()
        await message.answer(strings.get("added_cert", message.from_user.id), reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith("selectcert"), state='*')
async def get_cert(call: types.CallbackQuery):
    data = call.data.split("-")
    cursor.execute(f"SELECT p12_path, password, name, cert_id FROM Sessions WHERE user_id={data[1]} AND cert_id='{data[2]}'")
    cert = cursor.fetchone()
    cert_status = await utils.check_cert(cert[0], cert[1])
    if cert_status["output"]:
        cert_status = cert_status["output"].replace("Certificate Name", strings.get("cert_name", call.from_user.id))
        cert_status = cert_status.replace("Certificate Status", strings.get("cert_status", call.from_user.id))
        cert_status = cert_status.replace("Certificate Expiration Date", strings.get("cert_date", call.from_user.id))
        cert_status = cert_status.replace("Revoked", strings.get("status_revoked", call.from_user.id))
        cert_status = cert_status.replace("Signed", strings.get("status_signed", call.from_user.id))
        cert_status += f"{strings.get('password', call.from_user.id)}: <tg-spoiler>{cert[1] if cert[1] != '' else strings.get('skipped', call.from_user.id)}</tg-spoiler>"
    else:
        return await call.message.edit_text(strings.get("unknown_error", call.from_user.id))
    kb = types.InlineKeyboardMarkup(row_width=2).add(
        types.InlineKeyboardButton(text=strings.get("back", call.from_user.id), callback_data="mycerts")).add(
        types.InlineKeyboardButton(text=strings.get("del", call.from_user.id), callback_data=f"deletecert-{cert[3]}"))
    await call.message.edit_text(cert_status, reply_markup=kb, parse_mode=types.ParseMode.HTML)


@dp.callback_query_handler(lambda c: c.data.startswith("deletecert"), state='*')
async def delete_cert(call: types.CallbackQuery):
    data = call.data.split('-')
    cert = cursor.execute(
        f"SELECT p12_path, prov_path FROM Sessions WHERE user_id={call.from_user.id} AND cert_id='{data[1]}'").fetchone()

    cursor.execute(f"DELETE FROM Sessions WHERE cert_id='{data[1]}' AND user_id={call.from_user.id}")
    conn.commit()
    os.remove(cert[0])
    os.remove(cert[1])
    kb = types.InlineKeyboardMarkup(row_width=2).add(
        types.InlineKeyboardButton(text=strings.get("back", call.from_user.id), callback_data="mycerts"))
    await call.message.edit_text(strings.get("del_cert", call.from_user.id), reply_markup=kb)
