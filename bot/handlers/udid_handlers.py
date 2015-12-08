import datetime
import os
import zipfile
from shutil import SameFileError, copy

import aiohttp
from aiogram import types
from aiogram.dispatcher.filters import ChatTypeFilter

from bot import buttons, config, strings
from bot.utils import utils
from bot.loader import dp, cursor, conn, account_manager
from bot.states import CheckUDIDState


@dp.callback_query_handler(lambda c: c.data == "checkudid", ChatTypeFilter("private"), state='*')
async def check_udid(call: types.CallbackQuery):
    await call.message.edit_text(strings.get("send_udid", call.from_user.id))
    await CheckUDIDState.udid.set()



@dp.message_handler(state=CheckUDIDState.udid, content_types='text')
@dp.message_handler(commands="chk")
async def checkudid(message: types.Message, state=None):
    result_msg = await message.answer(strings.get("checking_udids", message.from_user.id))
    try:
        main_btns = buttons.get_menu(message.from_user.id)
        udids = message.text if not message.text.startswith("/chk") else message.get_args()
        if not udids:
            return await message.edit_text("Error: no UDID specified")

        results = ""

        for udid in udids.splitlines():
            udid = udid.upper()
            found = False
            if len(udid) < 25 or len(udid) > 40:
                results += strings.get("invalid_udid", message.from_user.id).replace('!', ': ') + udid + '!\n'
                continue

            for account in config.accounts:
                data = account_manager.get_account(iss_id=account["id"]).get_udid(udid)

                if data:
                    found = True

                    cert_id = account['id']
                    cert_name = account['name']

                    status = data[1]
                    raw_date = data[2].split(".")[0]
                    try:
                        date = datetime.datetime.strptime(raw_date, '%Y-%m-%dT%H:%M:%S').timestamp()
                        reg_date = datetime.datetime.fromtimestamp(date).strftime("%A, %B %d, %Y %I:%M:%S")
                    except ValueError:
                        reg_date = raw_date
                    device = data[3] or "Unknown"

                    if status == "ENABLED":
                        status = strings.get("udid_enabled", message.from_user.id)
                        results += f"UDiD: {udid}\n{strings.get('status', message.from_user.id)}: {status}\n{strings.get('register_time', message.from_user.id)}: {reg_date}\n"
                        main_btns.add(
                            types.InlineKeyboardButton(strings.get('get_cert', message.from_user.id) + f" {cert_name}",
                                                       callback_data=f"getcert_{cert_id}_{udid}"))
                        main_btns.add(
                            types.InlineKeyboardButton(strings.get('save_cert', message.from_user.id) + f" {cert_name}",
                                                       callback_data=f"savecert_{cert_id}_{udid}"))
                    elif status == "PROCESSING":
                        status = strings.get("udid_processing", message.from_user.id)
                        # est_date = date + 3600 * 78
                        # left_date = int(est_date - datetime.datetime.now().timestamp())
                        #results += f"UDiD: {udid}\n{strings.get('status', message.from_user.id)}: {status}\n{strings.get('register_time', message.from_user.id)}: {reg_date}\n"
                        results += f"UDiD: {udid}\n{strings.get('status', message.from_user.id)}: {status}\n{strings.get('register_time', message.from_user.id)}: {reg_date}\n"
                        if message.from_user.id in config.admin:
                            main_btns.add(
                                types.InlineKeyboardButton(strings.get('get_cert', message.from_user.id) + f" {cert_name}",
                                                           callback_data=f"getcert_{cert_id}_{udid}"))
                            main_btns.add(
                                types.InlineKeyboardButton(strings.get('save_cert', message.from_user.id) + f" {cert_name}",
                                                           callback_data=f"savecert_{cert_id}_{udid}"))
                    elif status == "INELIGIBLE":
                        status = strings.get("udid_ineligible", message.from_user.id)
                        # est_date = date + 86400 * 15
                        # left_date = int(est_date - datetime.datetime.now().timestamp())
                        results += f"UDiD: {udid}\n{strings.get('status', message.from_user.id)}: {status}\n{strings.get('register_time', message.from_user.id)}: {reg_date}\n"
                    else:
                        results += f"UDiD: {udid}\n{strings.get('status', message.from_user.id)}: {status}\n{strings.get('register_time', message.from_user.id)}: {reg_date}\n"

                    results += f"{strings.get('cert_name', message.from_user.id)}: {cert_name} ({cert_id})\nDevice: {device}\n⸺⸺⸺⸺⸺⸺⸺\n"
            if not found:
                results += strings.get("udid_not_found", message.from_user.id).format(udid=udid)
                results += "\n⸺⸺⸺⸺⸺⸺⸺\n"
                continue

        if results.count(
                strings.get("udid_enabled", message.from_user.id)) > 10 and message.from_user.id not in config.admin:
            main_btns = buttons.get_menu(message.from_user.id)

        await result_msg.edit_text(results, reply_markup=main_btns if message.chat.type == "private" else None)

    finally:
        try:
            await state.finish()
        except AttributeError:
            pass


@dp.callback_query_handler(lambda c: c.data.startswith("getcert") or c.data.startswith("savecert"), state='*')
async def get_certificate(call: types.CallbackQuery):
    msg = await call.message.answer(strings.get('gen_cert', call.from_user.id))
    main_btns = buttons.get_menu(call.from_user.id)
    data = call.data.split("_")
    output = f"sessions/{call.from_user.id}/certs" if data[0] == "savecert" else os.path.join(
        "sessions", str(call.from_user.id))

    account = account_manager.get_account(iss_id=data[1])

    os.makedirs(output, exist_ok=True)

    cert = await account.generate_cert(output, data[2])

    if not cert:
        return await call.message.answer(strings.get('gen_err', call.from_user.id))

    try:
        copy(cert[1], f"api/{account.name} - {account.iss_id}")
    except SameFileError:
        pass

    await msg.delete()
    if data[0] == "getcert":
        zip_path = os.path.join("sessions", str(call.from_user.id), f"{account.name} ({account.iss_id}).zip")

        zip_file = zipfile.ZipFile(zip_path, 'w')
        zip_file.write(cert[0], f"{account.iss_id}.p12")
        zip_file.write(cert[1], f"AdHoc_{account.iss_id}.mobileprovision")
        zip_file.write("api/README.txt", "README.txt")
        zip_file.write(f"api/{account.name} - {account.iss_id}/{account.iss_id}_PASSWORD.p12", f"{account.iss_id}_PASSWORD.p12")
        zip_file.close()

        
        await call.message.answer_document(types.InputFile(zip_path), reply_markup=main_btns)

        os.remove(cert[1])
        os.remove(zip_path)
    elif data[0] == "savecert":
        try:
            copy(cert[0], f"sessions/{call.from_user.id}/certs")
        except SameFileError:
            pass

        cursor.execute(
            f"INSERT INTO SESSIONS VALUES ({call.from_user.id}, 'sessions/{call.from_user.id}/certs/{account.iss_id}.p12', '{cert[1]}', '', '{account.name}', '{account.iss_id}')")
        conn.commit()

        await call.message.answer(strings.get('saved_cert', call.from_user.id), reply_markup=main_btns)
