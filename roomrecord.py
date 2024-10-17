from __future__ import annotations
from bilibili_api.live import LiveRoom
from telegram import Message
from datetime import datetime

class RoomRecord():

    def __init__(self, room_id) -> None:

        self.room_id: str = room_id                 # 直播間號
        self.uid: str = None                        # 主播在主站的uid
        self.is_living: bool = None                 # 是否在直播
        self.uname: str = None                      # 主播的顯示名稱
        self.room: LiveRoom = None                  # live.LiveRoom instance
        self.is_valid: bool = True                  # 是否為有效直播間

        self.message_sent: Message = None           # 已經發送的通知消息，用於在直播結束時修改
        self.room_title: str = None                 # 直播間標題
        self.start_time: datetime = None            # 開始直播的時間
        # self.stop_time: datetime = None             # 結束直播的時間
        self.cover_url: str = None                  # 直播封面的鏈接
        self.parent_area_name: str = None           # 分區名稱-parent 
        self.area_name: str = None                  # 分區名稱-child

    def parseResult(self, result: dict):

        self.uid = result["room_info"]["uid"]
        self.is_living = result["room_info"]["live_status"] == 1
        self.uname = result["anchor_info"]["base_info"]["uname"]

        self.room_title = result["room_info"]["title"]
        self.cover_url = result["room_info"]["cover"]
        self.parent_area_name = result["room_info"]["parent_area_name"]
        self.area_name = result["room_info"]["area_name"]

    def hasUpdate(self, new_record: RoomRecord) -> bool:

        return not (self.room_title == new_record.room_title \
            and self.uname == new_record.uname \
            and self.cover_url == new_record.cover_url \
            and self.parent_area_name == new_record.parent_area_name \
            and self.area_name == new_record.area_name)

    def update(self, new_record: RoomRecord):

        self.uid = new_record.uid
        self.uname = new_record.uname
         
        self.room_title = new_record.room_title 
        self.cover_url = new_record.cover_url 
        self.parent_area_name = new_record.parent_area_name 
        self.area_name = new_record.area_name

    def clear(self):    # 清空狀態

        self.room_title = None
        self.message_sent = None
        self.start_time = None
        # self.stop_time = None
        self.cover_url = None
        self.parent_area_name = None
        self.area_name = None