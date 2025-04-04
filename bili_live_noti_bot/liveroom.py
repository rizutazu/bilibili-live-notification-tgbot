import httpx
import json
from datetime import datetime, timezone, timedelta
import logging


logger = logging.getLogger("LiveRoom")

"""
    liveroom.py: bilibili_api.live.LiveRoom Class naive substitution
"""

# api found at https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/live/info.md
API = "https://api.live.bilibili.com/xlive/web-room/v1/index/getRoomBaseInfo"

# headers used in bilibili_api implementation
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54",
    "Referer": "https://www.bilibili.com",
}

# operation must be atomic
class LiveRoom():

    def __init__(self) -> None:

        # "1": (cache_ready,
        #   {
        #     "valid": bool
        #     "room_info": {
        #       "live_status": 0/1,
        #       "title": title,
        #       "cover": coverurl,
        #       "parent_area_name": p_area,
        #       "area_name": area,
        #       "uid": 114514,
        #       "live_start_time": 
        #     },
        #     "anchor_info": {
        #       "base_info": {
        #         "uname": "username"
        #       }
        #     }
        #   }
        # )
        self.rooms: dict[str, tuple[bool, dict]] = {}
        self.httpx_client: httpx.AsyncClient = httpx.AsyncClient()

    def add_room(self, room_id: str):
        self.rooms[room_id] = (False, {})

    def remove_room(self, room_id: str):
        del self.rooms[room_id]

    async def update_room_info(self):

        if len(self.rooms) == 0:
            return

        params = {
            "req_biz": "web_room_componet",
            "room_ids": [int(i) for i in self.rooms.keys()]
        }

        try:
            response = await self.httpx_client.get(API, params=params, headers=HEADERS)
            response.raise_for_status()
            responseContent = json.loads(response.text)
        except httpx.HTTPStatusError:
            raise HTTPStatusError(response.status_code)
        except (httpx.NetworkError, httpx.TimeoutException):
            raise NetworkError()
        except Exception as e:
            raise NetworkError(e)

        code = responseContent.get("code")
        if code == None:
            raise CodeFieldException("response data does not contain code field")
        elif code != 0:
            logger.critical(responseContent.get("message"))
            raise CodeFieldException(code, responseContent.get("message"))
        
        results = responseContent["data"]["by_room_ids"]
        
        for room_id in self.rooms.keys():

            info = results.get(room_id)
            if info == None:
                self.rooms[room_id] = (True, {"valid": False})
                logger.warning(f"{room_id} not found in server response")
                continue

            if info["live_time"] == "0000-00-00 00:00:00":
                live_start_time = 0
            else:
                live_start_time = datetime.strptime(info["live_time"], "%Y-%m-%d %H:%M:%S") \
                    .replace(tzinfo=timezone(timedelta(hours=8))) \
                    .astimezone(timezone.utc) \
                    .timestamp()
            c = {
                "valid": True,
                "room_info": {
                    "live_status": info["live_status"],
                    "title": info["title"],
                    "cover": info["cover"],
                    "parent_area_name": info["parent_area_name"],
                    "area_name": info["area_name"],
                    "uid": info["uid"],
                    "live_start_time": live_start_time
                },
                "anchor_info": {
                    "base_info": {
                        "uname": info["uname"]
                    }
                }
            }
            logger.info(f"Retrieved room info: room_id={room_id}, uname={info["uname"]}, is_living={info["live_status"]}, live_start_time={live_start_time}")
            self.rooms[room_id] = (True, c)
        return 
    

    async def get_room_info(self, room_id: str) -> dict:
        
        if room_id not in self.rooms.keys():
            raise Exception("room_id does not appear in room_ids")
        
        if not self.rooms[room_id][0]:
            await self.update_room_info()

        if self.rooms[room_id][1]["valid"]:
            result = self.rooms[room_id][1]
            self.rooms[room_id] = (False, {})
            return result
        else:
            raise RoomNotExistException()

class RoomNotExistException(Exception):
    pass

class CodeFieldException(Exception):
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
    def __init__(self, e: Exception=None):
        self.e = e