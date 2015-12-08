"""
Beta Apple developer account manager
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import List
from uuid import uuid4

import aiohttp
import jwt

from bot import config
from bot.loader import cursor, conn

import aiofiles


class ChineseApi:

    @staticmethod
    async def register(udid: str, code: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://udid.appds.cn/api/device/exchange?udid={udid}&code={code}") as resp:
                return resp.status

    @staticmethod
    async def get_certificate(udid: str, folder: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://udid.appds.cn/api/device/download/{udid}") as resp:
                if resp.status == 200:
                    async with aiofiles.open(os.path.join(folder, f"{udid.upper()}.zip"), "wb") as f:
                        await f.write(await resp.read())
                    return True
                return False


class Account:
    """
    Represents Apple developer acccount
    :param name: Account name
    :type name: str
    :param iss_id: Account issuer id
    :type iss_id: str
    """

    name: str
    iss_id: str

    def __init__(self, name: str, iss_id: str):
        self.name = name
        self.iss_id = iss_id
        self.path = f"api/{self.name} - {self.iss_id}"

        if not os.path.isdir(self.path):
            raise NotADirectoryError("Account folder not found or not a directory")

        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS '{self.iss_id}_UDIDs' (udid TEXT UNIQUE PRIMARY KEY NOT NULL, status TEXT NOT NULL, registred_at TEXT NOT NULL, device TEXT NULLABLE)")

        try:
            self.expired = self.udids[-1] == 'Expired'
        except IndexError:
            self.expired = False

        try:
            self.revoked = self.udids[-1][1] == 'Revoked'
            # print(self.udids[-1], self.revoked)
        except IndexError:
            self.revoked = True

        self.is_reseller = self.iss_id in config.reseller_accounts

        self.belongs_to_reseller = None if not self.is_reseller else config.reseller_accounts[self.iss_id]


    @property
    def udids(self):
        return cursor.execute(f"SELECT udid, status FROM '{self.iss_id}_UDIDs'").fetchall()

    def get_udid(self, udid: str) -> list:
        return cursor.execute(f"SELECT * FROM '{self.iss_id}_UDIDs' WHERE udid==?",
                              (udid.strip(),)).fetchone()

    async def generate_cert(self, output, udid) -> List[str] | bool:
        """
        Create p12 certificate and provisioning file
        :param udid: udid for mobileprovision
        :param output: path to place files
        :return: path to mobileprovision and p12 if successed, else False
        """
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as client:
            headers = {'Authorization': f'Bearer {self.get_token()}'}

            async with client.get(
                    f"https://api.appstoreconnect.apple.com/v1/certificates?filter[displayName]={self.name}",
                    headers=headers) as response:
                certificates = await response.json()
                try:
                    certificate_id = certificates["data"][0]["id"]
                except KeyError:
                    logging.error("Failed to get certificate id on acc " + self.name)
                    return False
            async with client.get(
                    f"https://api.appstoreconnect.apple.com/v1/bundleIds?filter[identifier]={self.iss_id}",
                    headers=headers) as response:
                bundleid = await response.json()
                bundleid_id = bundleid["data"][0]["id"]

            async with client.get(f"https://api.appstoreconnect.apple.com/v1/devices?filter[udid]={udid}",
                                  headers=headers) as response:
                device = await response.json()

                device_id = device["data"][0]["id"]

            attributes = {
                "name": str(uuid4())[:5],
                "profileType": "IOS_APP_ADHOC"
            }

            relationships = {
                "bundleId": {
                    "data": {
                        "id": bundleid_id,
                        "type": "bundleIds"
                    }
                },
                "certificates": {
                    "data": [
                        {
                            "id": certificate_id,
                            "type": "certificates"
                        }
                    ]
                },
                "devices": {
                    "data": [
                        {
                            "id": device_id,
                            "type": "devices"
                        }
                    ]
                }
            }

            payload = {
                "data": {
                    "attributes": attributes,
                    "relationships": relationships,
                    "type": "profiles"
                }
            }

            async with client.post("https://api.appstoreconnect.apple.com/v1/profiles", headers=headers,
                                   json=payload) as response:
                profile = await response.json()
                profile_content = base64.b64decode(profile["data"]["attributes"]["profileContent"])

        prov_path = f"{output}/AdHoc_{self.iss_id}.mobileprovision"

        with open(prov_path, 'wb') as f:
            f.write(profile_content)

        if os.path.isfile(prov_path) and os.path.isfile(
                f"{self.path}/{self.iss_id}.p12"):
            return [f"{self.path}/{self.iss_id}.p12", prov_path]
        else:
            logging.error(f"Failed to generate cert. Apple API response:\n{profile}")
            return False

    async def register_udid(self, platform, udid) -> dict:
        """
        Register UDID into developer account
        :param platform: Platform to register as
        :param udid: UDID to register
        :return: apple api response
        """

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as client:
            payload = {
                "data": {
                    "type": "devices",
                    "attributes": {
                        "name": udid,
                        "platform": platform,
                        "udid": udid
                    }
                }
            }

            headers = {'Authorization': f'Bearer {self.get_token()}'}

            async with client.post("https://api.appstoreconnect.apple.com/v1/devices", json=payload,
                                   headers=headers) as response:
                json_response = await response.json(content_type=None)
                if not json_response.get("data"):
                    return json_response
                device_url = json_response["data"]["links"]["self"]

            async with client.get(device_url, headers=headers) as response:
                return await response.json(content_type=None)

    async def update_udid(self, udid, enabled):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as client:
            headers = {'Authorization': f'Bearer {self.get_token()}'}

            async with client.get(f"https://api.appstoreconnect.apple.com/v1/devices?filter[udid]={udid}",
                                  headers=headers) as response:
                device = await response.json()
                device_id = device["data"][0]["id"]
                device_link = device["data"][0]["links"]["self"]

            payload = {
                "data": {
                    "type": "devices",
                    "id": device_id,
                    "attributes": {
                        "status": "ENABLED" if enabled else "DISABLED"
                    }
                }
            }

            async with client.patch(device_link, headers=headers, json=payload) as response:
                return await response.json()

    def get_token(self) -> str:
        """
        Generate Apple App Store Connect API auth token
        :return: Apple API token
        """
        expiration_in_ten_minutes = int(time.time() + 600)

        with open(f"{self.path}/{self.iss_id}.json") as f:
            account_json = json.load(f)

        payload = {
            "iss": account_json.get("issuer_id"),
            "exp": expiration_in_ten_minutes,
            "aud": "appstoreconnect-v1"
        }
        headers = {
            "alg": "ES256",
            "kid": account_json.get("key_id"),
            "typ": "JWT"
        }

        with open(f"{self.path}/AuthKey_{account_json.get('key_id')}.p8", "r") as f:
            private_key = f.read()

        token = jwt.encode(payload=payload, key=private_key, algorithm="ES256", headers=headers)

        return token

    async def get_info(self) -> dict:
        """
        Gives info about account
        :return: dict with account info
        """
        with open(f"{self.path}/{self.iss_id}.json", 'r') as json_file:
            account_json = json.load(json_file)

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as client:
            headers = {'Authorization': f'Bearer {self.get_token()}'}
            async with client.get(
                    "https://api.appstoreconnect.apple.com/v1/devices?filter[platform]=IOS&limit=200",
                    headers=headers) as response:
                response = await response.json()
                ios_count = len(response["data"])

            async with client.get(
                    "https://api.appstoreconnect.apple.com/v1/devices?filter[platform]=MAC_OS&limit=200",
                    headers=headers) as response:
                response = await response.json()
                mac_count = len(response["data"])

            udid_count = ios_count + mac_count

        return {
            "name": account_json["name"],
            "email": account_json["email"],
            "phone": account_json["phone"],
            "password": account_json["pass"],
            "udid_count": f"{udid_count}/300",
            "mac_count": mac_count,
            "ios_count": ios_count
        }


class AccountManager:
    """
    Simple Apple developer account manager
    :param accounts: List of Account objects
    :type accounts: list
    """

    accounts: List[Account]

    def __init__(self, accounts: List[Account], reseller_accounts: dict):
        self.accounts = accounts
        self.reseller_accounts = reseller_accounts
        
        self.reseller_acc_list = [account for account in accounts if account.iss_id in self.reseller_accounts]

    @classmethod
    def from_list(cls, account_list: list, reseller_accounts: dict) -> AccountManager:
        """
        Generates new AccountManager from list
        :param account_list: list of dicts with name and id keys
        :return: AccountManager with all the accounts
        """
        return cls([Account(account["name"], account["id"]) for account in account_list], reseller_accounts)

    def get_account(self, name: str | None = None, iss_id: str | None = None) -> Account:
        """
        Get account by name or issuer id
        :param name: account name
        :param iss_id: account issuer id
        :return: Account object with given name or id
        """

        if not name and not iss_id:
            raise ValueError("You should pass either account name or id")

        for account in self.accounts:
            if account.name == name or account.iss_id == iss_id:
                return account
        else:
            raise ValueError("Account not found")

    def get_tokens(self):
        """
        Get API tokens for every account
        :return: dict of tokens and accounts
        """
        accounts_tokens = {}

        for account in self.accounts:
            token = account.get_token()
            accounts_tokens[token] = account

        return accounts_tokens

    async def update_udids_data(self):
        """
        Dump UDIDs from Apple API to database
        """
        logging.info("Updating UDIDs data...")

        client = aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False))

        try:
            async with client:
                for number, account in enumerate(self.accounts, start=1):

                    logging.info(f"[{number}/{len(self.accounts)}] Updating UDIDs on account {account.name}")
                    token = account.get_token()
                    headers = {'Authorization': f'Bearer {token}'}

                    async with client.get(
                            "https://api.appstoreconnect.apple.com/v1/devices?filter[platform]=IOS&limit=200",
                            headers=headers) as response:
                        if response.status == 401:
                            logging.error(f"Account {account.name} revoked!")
                            account.revoked = True
                            cursor.execute(f"UPDATE '{account.iss_id}_UDIDs' SET status=?", ("Revoked",))
                            conn.commit()
                            continue
                        elif response.status == 403:
                            logging.error(f"Account {account.name} expired!")
                            account.expired = True
                            cursor.execute(f"UPDATE '{account.iss_id}_UDIDs' SET status=?", ("Expired",))
                            conn.commit()
                            continue
                        devices_response = await response.json()
                        ios_devices = devices_response.get("data")
                        # print(ios_devices)

                    async with client.get(
                            "https://api.appstoreconnect.apple.com/v1/devices?filter[platform]=MAC_OS&limit=200",
                            headers=headers) as response:
                        devices_response = await response.json()
                        mac_devices = devices_response.get("data")

                    devices = ios_devices + mac_devices
         
                    for device in devices:
                        device_data = device.get("attributes")
                        cursor.execute(
                            f"INSERT OR REPLACE INTO '{account.iss_id}_UDIDs' (udid, status, registred_at, device) VALUES (?, ?, ?, ?)",
                            (device_data.get("udid").upper(), device_data.get("status"),
                             device_data.get("addedDate"), device_data.get("model")))
                        conn.commit()
        except Exception as e:
            logging.error(f"Unexcepted error during updating UDIDs! - {e}", exc_info=True)
        else:
            logging.info("Updated UDID data succsessfully!")
