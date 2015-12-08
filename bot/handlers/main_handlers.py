from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import ChatTypeFilter

from bot import buttons, strings
from bot.loader import dp, cursor, conn


@dp.message_handler(ChatTypeFilter("private"), commands=["start"], state='*')
async def send_start(message: types.Message):
    lang = cursor.execute(f"SELECT lang FROM UsersLangs WHERE id={message.from_user.id}").fetchone()
    if not lang:
        if message.from_user.language_code not in {'uk', 'en', 'ru', 'fa'}:
            return await message.reply("Choose language bellow: ", reply_markup=buttons.lang_btns)
        cursor.execute(f"INSERT INTO UsersLangs VALUES ({message.from_user.id}, '{message.from_user.language_code}');")
        conn.commit()

    main_btns = buttons.get_menu(message.from_user.id)
    await message.reply(strings.get("start_choice", message.from_user.id), reply_markup=main_btns)


@dp.message_handler(commands=["lang"], state='*')
async def choose_language(message: types.Message):
    await message.reply(strings.get("lang_choice", message.from_user.id), reply_markup=buttons.lang_btns)


@dp.callback_query_handler(lambda c: c.data.startswith("selectlang"), state='*')
async def set_lang(call: types.CallbackQuery):
    lang_to_set = call.data.split()[1]
    try:
        cursor.execute(f'INSERT INTO UsersLangs VALUES ({call.from_user.id}, "{lang_to_set}")')
        conn.commit()
    except:
        cursor.execute(f'UPDATE UsersLangs SET lang="{lang_to_set}" WHERE id={call.from_user.id}')
        conn.commit()
    else:
        main_btns = buttons.get_menu(call.from_user.id)
        await call.message.edit_text(strings.get("start_choice", call.from_user.id), reply_markup=main_btns)
    await call.answer(strings.get("lang_changed", call.from_user.id))


@dp.callback_query_handler(lambda c: c.data == "back_start", state='*')
async def back_to_start(call: types.CallbackQuery):
    main_btns = buttons.get_menu(call.from_user.id)
    await call.message.edit_text(strings.get("start_choice", call.from_user.id), reply_markup=main_btns)


users_cancel = {}
@dp.message_handler(state='*', commands='cancel')
async def cancel_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.finish()
    users_cancel[user_id] = True

    main_btns = buttons.get_menu(user_id)

    await message.reply(strings.get("cancel", message.from_user.id), reply_markup=main_btns)
