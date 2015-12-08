import datetime
import logging
import os
from contextlib import suppress
from uuid import uuid4
import asyncio

from aiogram.types import ParseMode
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import MessageNotModified, BotBlocked, ChatNotFound, UserDeactivated
from zipfile import ZipFile 


from bot.utils import utils
from bot import buttons, config, strings
from bot.loader import dp, cursor, conn, account_manager, bot, chinese_api
from bot.states import GenerateRedeemStates, RegisterUDiDStates, SetFreeCertStates
from bot.handlers.main_handlers import cancel_handler, users_cancel

class ResetKey(BaseException):
    pass 

@dp.callback_query_handler(lambda c: c.data.startswith("get_acc") and "page" not in c.data, state='*')
async def send_account_info(call: types.CallbackQuery):
    data = call.data.split("-")
    try:
        account = await account_manager.get_account(data[1], data[2]).get_info()
    except KeyError:
        return await call.answer("That account is revoked!")

    await call.message.edit_text(f"""Account Name : {account["name"]}
Account Mail : {account["email"]}
Account Password : {account["password"]}
Phone Number : {account["phone"]}
Registered Devices : {account["udid_count"]}
iOS amount : {account["ios_count"]}
Magic amount : {account["mac_count"]}""", reply_markup=buttons.get_menu(call.from_user.id))


@dp.callback_query_handler(lambda c: c.data == "list_accounts", state='*')
async def send_account_list(call: types.CallbackQuery):
    msg = await call.message.answer("⌛")
    kb = buttons.get_accounts_menu("get_acc", user_id=call.from_user.id)

    await msg.edit_text(strings.get("sellect_acct", call.from_user.id), reply_markup=kb)


@dp.callback_query_handler(lambda c: 'page' in c.data, state="*")
async def switch_page(call: types.CallbackQuery):
    data = call.data.split("-page-")
    await call.message.edit_reply_markup(buttons.get_accounts_menu(data[0], int(data[1]), user_id=call.from_user.id))


@dp.callback_query_handler(lambda c: c.data == "gen_coupon")
async def generate_coupon(call: types.CallbackQuery):
    await GenerateRedeemStates.amount.set()

    await call.message.edit_text(strings.get("coupon_count", call.from_user.id))


@dp.message_handler(lambda m: m.text.isdigit(), state=GenerateRedeemStates.amount)
async def generate_coupon_amount(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data["amount"] = int(message.text)
    msg = await message.answer("⌛")
    await msg.edit_text(strings.get("sellect_acct", message.from_user.id),
                        reply_markup=buttons.get_accounts_menu("gen_coupon", user_id=message.from_user.id))
    await GenerateRedeemStates.next()


@dp.callback_query_handler(lambda c: c.data.startswith("gen_coupon"), state=GenerateRedeemStates.account)
async def generate_coupon_account(call: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        account_name = call.data.split("-")[1]
        account_id = call.data.split("-")[2]
        data["account_name"] = account_name
        data["account_id"] = account_id

    account = account_manager.get_account(account_name)
    account_info = await account.get_info()
    mac_count = account_info["mac_count"]
    ios_count = account_info["ios_count"]


    acc_types = account_manager.reseller_accounts.get(account.iss_id, {}).get(call.from_user.id, [])
    if call.from_user.id in config.admin:
        acc_types = ['ios', 'macos']

    kb = types.InlineKeyboardMarkup()
    if "ios" in acc_types:
        kb.row(types.InlineKeyboardButton(f"iOS ({ios_count})", callback_data="gen_coupon-IOS"))
    if "macos" in acc_types:
        kb.row(types.InlineKeyboardButton(f"Short ({mac_count})", callback_data="gen_coupon-MAC_OS"))

    await call.message.edit_text("Select platform", reply_markup=kb)
    await GenerateRedeemStates.next()


@dp.callback_query_handler(lambda c: c.data.startswith("gen_coupon"), state=GenerateRedeemStates.platform)
async def generate_coupon_platform(call: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        amount = data["amount"]
        account_name = data["account_name"]
        account_id = data["account_id"]
        platform = call.data.split("-")[1]
    codes = ""
    for _ in range(amount):
        redeem_code = f"{account_name}-{account_id}-{str(uuid4()).replace('-', '')[:6]}-{'IOS' if platform == 'IOS' else 'SECRET'}".upper()
        codes += f"<code>{redeem_code}</code>\n"

        cursor.execute(
            f"INSERT INTO REDEEMCODES VALUES ('{redeem_code}', '{account_name}', '{account_id}', NULL, NULL, '{platform}')")
        conn.commit()

    await call.message.edit_text(codes, parse_mode=types.ParseMode.HTML,
                                 reply_markup=buttons.get_menu(call.from_user.id))
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "register_udid")
@dp.throttled(rate=1)
async def register_udid_handler(call: types.CallbackQuery):
    resellers = set()

    for account in config.reseller_accounts.values():
        for user in account.keys():
            resellers.add(user)

    if call.from_user.id in resellers:
        await call.message.edit_text("Select registration method", reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("Redeem code", callback_data="reg_udid_redeem"),
            types.InlineKeyboardButton("Super Instant", callback_data="reg_udid_instant"),
            types.InlineKeyboardButton("Select account", callback_data="reg_udid_account")
        ))
        await RegisterUDiDStates.method.set()
    elif call.from_user.id not in [config.admin + config.reseller]:
        await call.message.edit_text(strings.get("send_coupon", call.from_user.id))
        await RegisterUDiDStates.redeem_code.set()
    else:
        await call.message.edit_text("Select account", reply_markup=buttons.get_accounts_menu("reg_udid", user_id=call.from_user.id))
        await RegisterUDiDStates.account.set()


@dp.callback_query_handler(lambda c: c.data == "reg_udid_instant", state=RegisterUDiDStates.method)
@dp.throttled(rate=1)
async def ask_api_key(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(strings.get("send_api_key", call.from_user.id))
    await RegisterUDiDStates.api_key.set()


@dp.message_handler(state=RegisterUDiDStates.api_key)
@dp.throttled(rate=1)
async def reg_udid_instant(message: types.Message, state: FSMContext): 
    await message.answer(strings.get("send_udid", message.from_user.id))
    async with state.proxy() as data:
        data['api_key'] = message.text 
    await RegisterUDiDStates.api_udid.set()


@dp.message_handler(state=RegisterUDiDStates.api_udid)
@dp.throttled(rate=1)
async def register_udid_instant(message: types.Message, state: FSMContext): 
    data = await state.get_data()
    await state.finish()
    udid = message.text
    msg = await message.answer("⌛")
    main_btns = buttons.get_menu(message.from_user.id)
    
    status = await chinese_api.register(udid=udid, code=data.get('api_key'))
    logging.info(status)

    if status == 200:
        text_message = "Success!" 
        cursor.execute(f"INSERT INTO 'APIKEYS' VALUES (?, ?, ?)", 
                    (message.from_user.id, data.get('api_key'), udid.upper())) 
        conn.commit() 
        folder = os.path.join("api2", str(message.from_user.id), udid.upper()) 
        try: os.makedirs(folder) 
        except FileExistsError: pass 

        await chinese_api.get_certificate(udid=udid, folder=folder)
        zip_file_path = os.path.join(folder, udid.upper() + ".zip")
        with ZipFile(zip_file_path, 'r') as zObject: 
            zObject.extractall(folder) 

            files = []
        
            file_to_rename = ['.mobileprovision', '.p12']
            for file in os.listdir(folder):
                for to_rename in file_to_rename:
                    new_file_path = os.path.join(folder, f"{udid}{to_rename}")
                    if to_rename in file and new_file_path not in files:
                        os.rename(
                            os.path.join(folder, file),
                            new_file_path
                        )
                        files.append(new_file_path)

            for file in files:
                await message.answer_document(types.InputFile(file), caption = f"Password : {config.PASSWORD}" if file.endswith('.p12') else None)
                                
            with open(os.path.join(folder, "pass.txt"), "w") as f:
                f.write(config.PASSWORD)

        os.remove(zip_file_path)

    elif status == 400:
        text_message = "Code is wrong!\n\nPlease try again."
    elif status == 500:
        text_message = "Either key or the UDiD is wrong.\nPlease try again"
    else:
        text_message = "Failed!"
        
    await msg.edit_text(text_message, reply_markup=main_btns)


@dp.callback_query_handler(lambda c: c.data == "reg_udid_redeem", state=RegisterUDiDStates.method)
@dp.throttled(rate=1)
async def reg_udid_redeem(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(strings.get("send_coupon", call.from_user.id))
    await RegisterUDiDStates.redeem_code.set()


@dp.callback_query_handler(lambda c: c.data == "reg_udid_account", state=RegisterUDiDStates.method)
async def reg_udid_account(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Select account",
                                 reply_markup=await buttons.get_reseller_account_menu(call.from_user.id, "reg_udid"))
    await RegisterUDiDStates.account.set()


@dp.callback_query_handler(lambda c: c.data.startswith("reg_udid") and "page" not in c.data,
                           state=RegisterUDiDStates.account)
async def register_udid_account(call: types.CallbackQuery, state: FSMContext):

    account = account_manager.get_account(iss_id=call.data.split("-")[2])
    data = await state.get_data()
    data["account_name"] = account.name
    data["account_id"] = account.iss_id

    account_info = await account.get_info()

    mac_count = account_info["mac_count"]
    ios_count = account_info["ios_count"]

    await state.update_data(data)

    kb = types.InlineKeyboardMarkup()

    option_types = account.belongs_to_reseller.get(call.from_user.id)
    if call.from_user.id in config.admin:
        option_types = ['ios', 'macos']

    if 'ios' in option_types:
        kb.add(types.InlineKeyboardButton(f"iOS ({ios_count})", callback_data="gen_coupon-IOS"))
    if 'macos' in option_types:
        kb.add(types.InlineKeyboardButton(f"Short ({mac_count})", callback_data="gen_coupon-MAC_OS"))


    await call.message.answer("Select UDiD platform:", reply_markup=kb)
    await RegisterUDiDStates.platform.set()

@dp.callback_query_handler(state=RegisterUDiDStates.platform)
@dp.throttled(rate=1)
async def register_udid_platform(call: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data["platform"] = call.data.split("-")[1]

    await call.message.edit_text(strings.get("send_udid", call.from_user.id))
    await RegisterUDiDStates.udid.set()


@dp.message_handler(state=RegisterUDiDStates.redeem_code)
@dp.throttled(rate=1)
async def register_udid_redeem(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        return await cancel_handler(message, state)
    
    redeem_code = cursor.execute(f"SELECT * FROM REDEEMCODES WHERE code='{message.text}'").fetchone()

    if not redeem_code or redeem_code[3]:
        return await message.answer(strings.get("invalid_coupon", message.from_user.id))
    
    async with state.proxy() as data:
        data["account_name"] = redeem_code[1]
        data["account_id"] = redeem_code[2]
        data["redeem_code"] = message.text
        data['platform'] = redeem_code[5]
    
    cursor.execute(f"DELETE FROM REDEEMCODES WHERE code='{message.text}'")
    conn.commit()

    await message.answer(strings.get("send_udid", message.from_user.id))
    await RegisterUDiDStates.udid.set()



@dp.message_handler(state=RegisterUDiDStates.udid)
@dp.throttled(rate=1, key=lambda message: message.from_user.id)
async def register_udid(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.finish()

    msg = await message.answer("⌛")
    udids = message.text.splitlines()
    main_btns = buttons.get_menu(message.from_user.id)

#    # Check for exactly one UDID in the message
#    if len(udids) != 1:
#        return await message.answer("Only one UDID allowed.")


    msg_text = ""

    account_name = data["account_name"]
    account_id = data["account_id"]

    account = account_manager.get_account(iss_id=account_id)
    account_info = await account.get_info()

    mac_count = account_info["mac_count"]
    ios_count = account_info["ios_count"]

    if len(udids) > 1 and message.from_user.id not in config.admin:
        if not message.from_user.id in account_manager.reseller_accounts.get(account.iss_id).keys():
            return await message.answer(strings.get("multi_reg_err", message.from_user.id),
                                        reply_markup=buttons.get_menu(message.from_user.id))

    platform = data.get("platform")
    redeem_code = data.get("redeem_code", "")
    for udid in udids:
        try:
            if len(udid) < 25 or len(udid) > 40:
                msg_text += f"UDiD: {udid}\n{strings.get('reg_status', message.from_user.id)}: {strings.get('invalid_udid', message.from_user.id)}\n⸺⸺⸺⸺⸺⸺⸺\n"
                raise ResetKey
    

            if account.get_udid(udid):
                msg_text += f"UDiD: {udid}\n{strings.get('reg_status', message.from_user.id)}: Already registred\n⸺⸺⸺⸺⸺⸺⸺\n"
                raise ResetKey

            if ios_count + mac_count > 300 or (
                    (ios_count >= 200 and platform == "IOS") or (mac_count >= 100 and platform == "MAC_OS")
            ):
                msg_text += f"UDiD: {udid}\n{strings.get('reg_status', message.from_user.id)}: UDID limit exceed\n⸺⸺⸺⸺⸺⸺⸺\n"
                raise ResetKey

            response = await account.register_udid(platform, udid)

            if not response.get("data"):
                error_code = response.get('errors')[0]

                if str(error_code.get('status')) == '403':
                    msg_text += f"UDiD: {udid}\n{strings.get('reg_status', message.from_user.id)}: {strings.get('reg_udid_err', message.from_user.id)}\n\nFollowing UDID is iPhone⸺⸺⸺⸺⸺⸺⸺\n"
                elif str(error_code.get('status')) == '409':
                    msg_text += f"UDiD: {udid}\n{strings.get('reg_status', message.from_user.id)}: {strings.get('reg_udid_err', message.from_user.id)}\n\nYour account is full, or following udid is an iphone⸺⸺⸺⸺⸺⸺⸺\n"
                else:
                    msg_text += f"UDiD: {udid}\n{strings.get('reg_status', message.from_user.id)}: {strings.get('reg_udid_err', message.from_user.id)}\n{response}\n⸺⸺⸺⸺⸺⸺⸺\n"
                raise ResetKey

            msg_text += f"UDiD: {udid}\n{strings.get('reg_status', message.from_user.id)}: {strings.get('reg_udid_success', message.from_user.id)}\n"

            status = response["data"]["attributes"]["status"]
            device = response["data"]["attributes"]["model"]
            raw_date = response["data"]["attributes"]["addedDate"].split(".")[0]
            date = datetime.datetime.strptime(raw_date, '%Y-%m-%dT%H:%M:%S').timestamp()
            reg_date = datetime.datetime.fromtimestamp(date).strftime("%A, %B %d, %Y %I:%M:%S")

            try:
                cursor.execute(f"INSERT INTO '{account_id}_UDIDs' VALUES (?, ?, ?, ?)",
                            (udid.upper(), status, reg_date, device))
                conn.commit()
            except Exception as e:
                logging.error(f"UDID {udid} Register failed")
                msg_text += f"UDiD: {udid}\n{strings.get('reg_status', message.from_user.id)}: Failed ({e})\n⸺⸺⸺⸺⸺⸺⸺\n"
                raise ResetKey

            if status == "ENABLED":
                main_btns.add(
                    types.InlineKeyboardButton(strings.get('get_cert', message.from_user.id) + f" {account_name}",
                                            callback_data=f"getcert_{account_id}_{udid}"))
                main_btns.add(
                    types.InlineKeyboardButton(strings.get('save_cert', message.from_user.id) + f" {account_name}",
                                            callback_data=f"savecert_{account_id}_{udid}"))
            try:
                status = strings.get(f"udid_{status.lower()}", message.from_user.id)
            except KeyError:
                pass

            msg_text += (f"{strings.get('status', message.from_user.id)}: {status}\n"
                        f"{strings.get('register_time', message.from_user.id)}: {reg_date}\n"
                        f"{strings.get('cert_name', message.from_user.id)}: {account_name} ({account_id})\n"
                        f"Device: {device}\n⸺⸺⸺⸺⸺⸺⸺\n")

            await msg.edit_text(msg_text, reply_markup=main_btns)
            if redeem_code:
                cursor.execute(
                    f"INSERT INTO REDEEMCODES VALUES ('{redeem_code}', '{account_name}', '{account_id}', {message.from_user.id}, {udid}, '{platform}')"
                )
                conn.commit()
        except ResetKey:
            if redeem_code:
                cursor.execute(
                    f"INSERT INTO REDEEMCODES VALUES ('{redeem_code}', '{account_name}', '{account_id}', NULL, NULL, '{platform}')"
                )
                conn.commit()

    try:
        await msg.edit_text(msg_text, reply_markup=main_btns)
    except MessageNotModified:
        pass



@dp.message_handler(lambda m: m.from_user.id in config.admin, commands="blacklist")
@dp.message_handler(lambda m: m.from_user.id in config.admin, commands="whitelist")
async def blacklist_udid(message: types.Message):
    args = message.get_args().split()
    udid = args[0]
    enabled = message.text.startswith("/whitelist")
    account = account_manager.get_account(iss_id=args[1])

    result = await account.update_udid(udid, enabled)
    await message.answer(result)


@dp.message_handler(lambda m: m.from_user.id in config.admin, commands="free")
async def set_free_cert(message: types.Message):
    await message.answer("Send ur p12"
                         "\ninclude password as caption bcs me lazy adding one more state")
    await SetFreeCertStates.p12.set()


@dp.message_handler(state=SetFreeCertStates.p12, content_types=["document"])
async def set_free_p12(message: types.Message, state: FSMContext):
    if not message.document.file_name.endswith(".p12"):
        return await message.answer("Invalid .p12 file.")
    password = message.caption
    if not password:
        return await message.answer("Send the .p12 and add the password in caption.")
    p12_path = os.path.join(os.getcwd(), "sessions/free", "free_cert.p12")
    await utils.download(message.document, p12_path)
    check_result = await utils.check_cert(p12_path, password)
    if not check_result["ok"]:
        await state.finish()
        os.remove(p12_path)
        return await message.answer("Certificate is revoked")

    with open(os.path.join(os.getcwd(), "sessions/free", "free_cert_pass.txt"), 'w') as file:
        file.write(password)

    await message.answer("Please send your provision file")
    await SetFreeCertStates.next()


@dp.message_handler(state=SetFreeCertStates.prov, content_types=["document"])
async def set_free_prov(message: types.Message, state: FSMContext):
    if not message.document.file_name.endswith(".mobileprovision"):
        return await message.answer("The files isn't .mobileprovision")
    await utils.download(message.document, os.path.join(os.getcwd(), "sessions/free", "free_cert.mobileprovision"))
    await message.answer("done")
    await state.finish()



@dp.message_handler(commands=['broadcast'])
async def broadcast_message(message: types.Message):
    message_text = message.get_args()

    if not message_text:
        return await message.reply("You need to provide a message to broadcast.")

    # Retrieve user IDs from the database
    cursor.execute("SELECT id FROM UsersLangs")
    users = [item[0] for item in cursor.fetchall()]
    logging.info(f"Found {len(users)} users to broadcast to.")

    if not users:
        return await message.answer("No users found to broadcast to.")

    await message.answer(f"Broadcasting to {len(users)} users...")

    success_count = 0
    rate_limit = 1 / 2  # Pause duration in seconds to send 3 messages per second

    for user_id in users:
        try:
            await bot.send_message(user_id, message_text, parse_mode=types.ParseMode.HTML)
            logging.info(f"Message sent to user {user_id}")
            success_count += 1
            await asyncio.sleep(rate_limit)  # Pause to respect the rate limit of 3 messages per second
        except (BotBlocked, ChatNotFound, UserDeactivated):
            logging.warning(f"Failed to send message to user {user_id}")

    await message.answer(f"Broadcast complete. Sent to {success_count}/{len(users)} users.")
