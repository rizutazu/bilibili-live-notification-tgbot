import httpx
import json

# api used in bilibili_api implementation
API = "https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom"

# api found at https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/live/info.md
# but the response does not contain uname
# API = "https://api.live.bilibili.com/room/v1/Room/get_info"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54",
    "Referer": "https://www.bilibili.com",
}

class LiveRoom():
    
    def __init__(self, room_id: int) -> None:

        self.room_id: int = room_id
        self.httpx_client: httpx.AsyncClient = httpx.AsyncClient()

    async def get_room_info(self) -> dict:

        params = {
            "room_id": self.room_id
        }
        response = await self.httpx_client.get(API, params=params, headers=HEADERS)
        response.raise_for_status()

        result = json.loads(response.text)

        code = result.get("code")
        if code == None:
            raise ResponseCodeException("response data does not contain code field")
        elif code != 0:
            raise ResponseCodeException(f"code field is not 0, message={result.get('message')}")
        
        return result.get("data")

class ResponseCodeException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)