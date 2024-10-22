import json
import os

"""
    fetchconfig.py: 獲取配置
    不過既然config.json和env_vals都是用文件指定的，那這麼做的意義是什麼呢:thinking:
"""


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
        return _config_json_data.get(key)
    except FileNotFoundError:
        _file_not_found = True
        return None

def _get_config(key: str):
    env_key = "BILILIVENOTIBOT_" + key.upper()
    value = os.getenv(env_key)
    if value == None:
        value = _get_json_value(key)
        assert value is not None, f"Error: {key} is not specified\n"
        print(f"Read {key} from json")
    else:
        print(f"Read {key} from env")
    return value

def getTGBotToken() -> str:
    return str(_get_config("tgbot_token"))

def getTGChatID() -> str:
    return str(_get_config("tg_chat_id"))

def getSubscribedRooms() -> list:
    lst = _get_config("subscribed_rooms")
    if not isinstance(lst, list):
        return [i.strip() for i in lst.split(",")]
    return lst

def getTimezone() -> str:
    return str(_get_config("timezone"))

def getPollInterval() -> int:
    return int(_get_config("poll_interval"))
