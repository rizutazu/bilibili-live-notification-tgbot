import json
import os
import sys
import pytz
_config_json_data = None
_config_json_name = "config.json"
_file_not_found = False

def _get_json_value(key: str):
    global _file_not_found, _config_json_data
    if _file_not_found:
        return None
    if _config_json_data != None:
        return _config_json_data.get(key)
    try:
        with open(_config_json_name, "r") as f:
            _config_json_data = json.load(f)
        return _config_json_data[key]
    except FileNotFoundError:
        _file_not_found = True
        return None

def _get_config(key: str):
    env_key = "BILILIVENOTIBOT_" + key.upper()
    value = os.getenv(env_key)
    if value == None:
        value = _get_json_value(key)
    if value == None:
        sys.stderr.write(f"Error: {key} is not specified\n")
        exit(1)
    return value

def getTGBotToken() -> str:
    return _get_config("tgbot_token")

def getTGChatID() -> str:
    return _get_config("tg_chat_id")

def getSubscribeRooms() -> list:
    lst = _get_config("subscribed_rooms")
    if not isinstance(lst, list):
        return [i.strip() for i in lst.split(",")]
    return lst

def getTimezone() -> str:
    return _get_config("timezone")

def getPollInterval() -> int:
    return int(_get_config("poll_interval"))
