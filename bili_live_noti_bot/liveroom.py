import httpx
import json

"""
    liveroom.py: bilibili_api.live.LiveRoom Class naive substitution
"""

# api found at https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/live/info.md
# but the response does not contain uname
# API = "https://api.live.bilibili.com/room/v1/Room/get_info"

# api used in bilibili_api implementation
API = "https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom"

# headers used in bilibili_api implementation
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54",
    "Referer": "https://www.bilibili.com",
}
# curl --header "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54" -- header "Referer: https://www.bilibili.com" https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom?room_id=

class LiveRoom():
    
    def __init__(self, room_id: str) -> None:

        if not (room_id.isnumeric() and room_id.isascii()):
            raise ValueError("room_id is not a numeric ascii string")
        
        self.room_id: str = room_id
        self.httpx_client: httpx.AsyncClient = httpx.AsyncClient()

    async def get_room_info(self) -> dict:

        params = {
            "room_id": int(self.room_id)
        }


        try:
            response = await self.httpx_client.get(API, params=params, headers=HEADERS)
            response.raise_for_status()
            result = json.loads(response.text)
        except httpx.HTTPStatusError:
            raise HTTPStatusError(response.status_code)
        except httpx.NetworkError or httpx.TimeoutException:
            raise NetworkError()

        code = result.get("code")
        if code == None:
            raise ResponseCodeException("response data does not contain code field")
        elif code != 0:
            raise ResponseCodeException(code, result.get("message"))
        
        return result.get("data")

class ResponseCodeException(Exception):
    """
        exception about `code` field in bilibili api response 
    """
    def __init__(self, code: int, message: str, *args: object) -> None:
        super().__init__(*args)
        self.code = code
        self.message = message

class HTTPStatusError(Exception):
    """
        http status code exception
    """
    def __init__(self, status_code: int, *args: object) -> None:
        super().__init__(*args)
        # from httpx/_models.py: Response.raise_for_status
        error_types = {
            1: "Informational response",
            3: "Redirect response",
            4: "Client error",
            5: "Server error",
        }
        self.error_type: str = error_types.get(status_code // 100, "Invalid status code")
        self.status_code: int = status_code
        
class NetworkError(Exception):
    """
        Any NetWork exception
    """