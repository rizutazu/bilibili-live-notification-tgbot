import json

_json_data = None
file_name = "secret.json"

def get_json_value(key: str) -> str:
    global _json_data
    if _json_data != None:
        return _json_data[key]
    with open(file_name, "r") as f:
        _json_data = json.load(f)
    return _json_data[key]

def get_tg_bot_token() -> str:
    return get_json_value("tgbot_token")

def get_tg_chat_id() -> str:
    return get_json_value("tg_chat_id")

def get_subscribed_rooms() -> list:
    return get_json_value("subscribed_rooms")
