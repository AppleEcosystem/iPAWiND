from aiogram.dispatcher.filters.state import StatesGroup, State

class SignFileFromCertificate(StatesGroup):
    select_ipa = State()

class UrlShortner(StatesGroup):
    select_link = State()
    select_domain = State()
    select_appname = State()

class RedirectStates(StatesGroup):
    domain = State()
    plist_logo = State()
    channel_name = State()
    channel_link = State()
    channel_logo = State()

class SignFileStates(StatesGroup):
    cert = State()
    p12 = State()
    password = State()
    prov = State()
    options = State()
    bundleid = State()
    ipa = State()
    waiting = State()
    uploading = State()

class CheckUDIDState(StatesGroup):
    udid = State()


class CheckCertStates(StatesGroup):
    p12 = State()
    password = State()


class AddCertStates(StatesGroup):
    p12 = State()
    password = State()
    prov = State()


class GenerateRedeemStates(StatesGroup):
    amount = State()
    account = State()
    platform = State()


class SetFreeCertStates(StatesGroup):
    p12 = State()
    prov = State()


class RegisterUDiDStates(StatesGroup):
    method = State()
    redeem_code = State()
    platform = State()
    account = State()
    udid = State()

    api_key = State()
    api_udid = State()