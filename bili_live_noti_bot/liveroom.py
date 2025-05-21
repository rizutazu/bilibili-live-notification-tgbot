import httpx
import json
from datetime import datetime, timezone, timedelta
import logging


logger = logging.getLogger("LiveRoom")

"""
    liveroom.py: bilibili_api.live.LiveRoom Class naive substitution
"""

# api found at https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/live/info.md
BASEINFOAPI = "https://api.live.bilibili.com/xlive/web-room/v1/index/getRoomBaseInfo"

KEYFRAMEAPI = "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids"

# headers used in bilibili_api implementation
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54",
    "Referer": "https://www.bilibili.com",
}

# operation must be atomic
class LiveRoom():
    """
                LiveRoom class
            bilibili api implementation, maintain fetched info 
    """

    def __init__(self) -> None:

        # "room_id": (
        #   cache_ready: bool,
        #
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
        #
        # )
        self.rooms: dict[str, tuple[bool, dict]] = {}
        self.httpx_client: httpx.AsyncClient = httpx.AsyncClient()

    def addRoom(self, room_id: str) -> None:

        """
            add room to subscribe list, coz new api supports batch fetch
        """

        self.rooms[room_id] = (False, {})

    def removeRoom(self, room_id: str) -> None:

        """
            remove from subscribe list
        """

        if self.rooms.get(room_id) != None:
            del self.rooms[room_id]

    async def updateRoomInfo(self) -> None:

        """
            batch fetch room live status using api
        """

        if len(self.rooms) == 0:
            return

        params = {
            "req_biz": "web_room_componet",
            "room_ids": [int(i) for i in self.rooms.keys()]
        }

        try:
            response = await self.httpx_client.get(BASEINFOAPI, params=params, headers=HEADERS)
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
            logger.critical(f"updateRoomInfo: {code}: {responseContent.get('message')}")
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
    
    async def getRoomInfo(self, room_id: str) -> dict:
        
        """
            Interface exposed to other modules, return room info of given room_id from cache.
            Each method invocation will clear its corresponding cache, if it encountered cache miss,
            updateRoomInfo() will be invoked for a complete subscribe list info update
        """
        
        if room_id not in self.rooms.keys():
            raise Exception("room_id does not appear in room_ids")
        
        if not self.rooms[room_id][0]:
            await self.updateRoomInfo()

        if self.rooms[room_id][1]["valid"]:
            result = self.rooms[room_id][1]
            self.rooms[room_id] = (False, {})
            return result
        else:
            raise RoomNotExistException()
        
    async def getKeyFrameUrl(self, uid: str) -> str:

        params = {
            "uids[]": [int(uid)]
        }

        try:
            response = await self.httpx_client.get(KEYFRAMEAPI, params=params, headers=HEADERS)
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
            logger.critical(f"getKeyFrameUrl: {code}: {responseContent.get('message')}")
            raise CodeFieldException(code, responseContent.get("message"))
        
        if responseContent["data"].get(uid) == None:
            raise RoomNotExistException()
        else:
            url = responseContent["data"][uid]["keyframe"]
            if url != "":
                logger.info(f"Retrieved key frame url of user {uid}: {url}")
            else:
                logger.info(f"Key frame url is empty string")
            return url

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