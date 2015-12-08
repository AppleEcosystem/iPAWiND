from aiogram import types
from aiohttp.client_exceptions import ContentTypeError
from bot import config, strings
from bot.loader import account_manager

def get_menu(user_id: int) -> types.InlineKeyboardMarkup:
    base = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=strings.get("sign_file", user_id), callback_data="signfile"),
         types.InlineKeyboardButton(text=strings.get("check_udid", user_id), callback_data="checkudid")],
        [types.InlineKeyboardButton(text=strings.get("check_cert", user_id), callback_data="checkcert"),
         types.InlineKeyboardButton(text=strings.get("my_certs", user_id),
                                    callback_data="mycerts")]])

#    if user_id in config.admin:
#        base.row(types.InlineKeyboardButton(text=strings.get("list_accounts", user_id), callback_data="list_accounts"))
    
#    if user_id in config.admin + config.reseller:
#        base.row(
#            types.InlineKeyboardButton(text=strings.get("reg_udid", user_id), callback_data="register_udid"), 
#            types.InlineKeyboardButton(text=strings.get("gen_coupon", user_id), callback_data="gen_coupon")
#        )

    return base


def get_accounts_menu(callback_command: str, page: int = 1, user_id = None) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    from_account = (page - 1) * 50
    to_account = page * 50

    if user_id in config.admin:
        accs = account_manager.accounts
    else:
        accs = [account for account in account_manager.accounts if user_id in account_manager.reseller_accounts.get(account.iss_id, {}).keys()]
    

    for account in accs[from_account:to_account]:

        if account.name in config.excluded_accounts:
            continue

        udid_count = f'{len(account.udids)}/300' if not account.revoked else ('Revoked' if not account.expired else 'Expired')
        account_name = account.name if not account.is_reseller else "🙅🏻‍ | " + account.name

        kb.add(types.InlineKeyboardButton(f'{account_name} ({udid_count})',
                                          callback_data=f"{callback_command}-{account.name}-{account.iss_id}"))

    if from_account > 0:
        kb.add(
            types.InlineKeyboardButton('⬅️ Back', callback_data=f"{callback_command}-page-{page-1}")
        )
    if len(accs) > to_account:
        kb.add(
            types.InlineKeyboardButton('Next ➡️', callback_data=f"{callback_command}-page-{page+1}")
        )

    return kb


async def get_reseller_account_menu(reseller_id: int, callback_command: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    
    accounts = [account for account in account_manager.reseller_acc_list if reseller_id in account_manager.reseller_accounts[account.iss_id].keys()]
    for account in accounts:
        try:
            udid_status = None if not account.revoked else (
            'Revoked' if not account.expired else 'Expired')
        except (ContentTypeError, KeyError):
            udid_status = "Revoked"
        kb.add(types.InlineKeyboardButton(account.name + (f' ({udid_status}) ' if udid_status else ''),
                                          callback_data=f"{callback_command}-{account.name}-{account.iss_id}"))

    return kb


lang_btns = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="🇬🇧 English", callback_data="selectlang en"),
     types.InlineKeyboardButton(text="🇦🇫 فارسی", callback_data="selectlang fa")],
    [types.InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="selectlang de"),
     types.InlineKeyboardButton(text="🇺🇦 Українська", callback_data="selectlang uk")],
    [types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="selectlang ru"),
     types.InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="selectlang tr")],
    [types.InlineKeyboardButton(text="🇪🇸 Español", callback_data="selectlang es"),
     types.InlineKeyboardButton(text="🇸🇦 العربية", callback_data="selectlang ar")],
    [types.InlineKeyboardButton(text="🇨🇳 中文", callback_data="selectlang zh")] #
])

def domain_btns(cb: str):
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=api_url, callback_data=f"{cb}{index}")] for index, api_url in enumerate(config.api_urls) 
    ])
