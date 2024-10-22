from __future__ import annotations
from .liveroom import LiveRoom
from telegram import Message
from telegram.helpers import escape_markdown
from datetime import datetime
from pytz import utc, BaseTzInfo

class RoomRecord():
    """
                    RoomRecord Class
            記錄從bilibili api獲取到的信息，以及生成發送的消息
    """

    def __init__(self, room_id: str) -> None:

        # bot-related
        self.room: LiveRoom = None                  # live.LiveRoom instance
        self.is_valid: bool = True                  # 是否為有效直播間
        self.message_sent: Message = None           # 已經發送的通知消息，用於在直播結束時修改

        # variables that may not changing during live 
        self.room_id: str = room_id                 # 直播間號
        self.uid: str = None                        # 主播在主站的uid
        self.uname: str = None                      # 主播的顯示名稱

        # variables that change among each live
        self.is_living: bool = None                 # 是否在直播
        self.history_room_titles: list[str] = []    # 直播間用過的標題的列表，不含當前在用的，按時間從早到晚排序,
        self.current_room_title: str = None         # 當前的標題
        self.start_time: datetime = None            # 開始直播的時間
        self.cover_url: str = None                  # 直播封面的鏈接
        self.area_name_pair: str = None             # 所在的分區

    def parseResult(self, result: dict):

        """
            parse results from bilibili api
        """

        self.uid = result["room_info"]["uid"]
        self.uname = result["anchor_info"]["base_info"]["uname"]
        self.is_living = result["room_info"]["live_status"] == 1
        self.current_room_title = result["room_info"]["title"]
        self.start_time = datetime.fromtimestamp(result["room_info"]["live_start_time"], tz=utc)
        self.cover_url = result["room_info"]["cover"]
        parent_area_name = result["room_info"]["parent_area_name"]
        area_name = result["room_info"]["area_name"]
        self.area_name_pair = f"{parent_area_name}-{area_name}"

    def hasUpdate(self, new_record: RoomRecord) -> bool:

        """
            檢查是否和記錄在內的條目有區別
        """

        # live_start_time 會在直播結束時變成0所以不考慮
        return not (self.current_room_title == new_record.current_room_title \
            and self.uname == new_record.uname \
            and self.cover_url == new_record.cover_url \
            and self.area_name_pair == new_record.area_name_pair)

    def inherit(self, old_record: RoomRecord, inherit_time: bool=False):

        """
            繼承舊的record的部分信息，更新並把title history一併記錄了，等效於更新歷史記錄
        """
        
        self.room = old_record.room
        self.message_sent = old_record.message_sent

        if inherit_time:
            self.start_time = old_record.start_time

        self.history_room_titles = old_record.history_room_titles.copy()
        if old_record.current_room_title != None \
                and old_record.current_room_title != self.current_room_title:
            self.history_room_titles.append(old_record.current_room_title)

    def updateUserInfo(self, new_record: RoomRecord):

        """
            只更新與單次直播無關的
        """
        self.is_living = new_record.is_living   # for /list return
        self.uid = new_record.uid
        self.uname = new_record.uname

    def clear(self):    # 清空狀態

        """
            清空與單次直播有關的記錄
        """

        self.history_room_titles.clear()
        self.current_room_title = None
        self.message_sent = None
        self.start_time = None
        self.cover_url = None
        self.area_name_pair = None

    def generateMessageText(self, timezone: BaseTzInfo, stop_time: datetime=None) -> str:

        """
            生成發送的消息，包括點擊鏈接，markdown格式
        """

        # use provided live status
        text = ""
        if self.is_living:
            text += "[🟢]"
        else:
            text += "[🟠]"
        
        text += f"{self.uname}: "
        # add title changing history
        for title in self.history_room_titles:
            text += f"{title} ➡️ "
        # add current title
        text += f"{self.current_room_title}\n"

        # add area
        text += f"分區: {self.area_name_pair}"

        # add url
        text = escape_markdown(text, 2)
        text = f"[{text}](https://live.bilibili.com/{self.room_id})\n"

        # add time-related
        if self.start_time != None:
            text += f"開始時間： {self.start_time.astimezone(timezone).strftime('%Y/%m/%d %H:%M:%S')} {timezone.zone}\n"

        if stop_time != None:
            time_delta_str = str(stop_time - self.start_time).split(".")[0]
            text += f"結束時間： {stop_time.astimezone(timezone).strftime('%Y/%m/%d %H:%M:%S')} {timezone.zone}\n"
            text += f"持續時間： {time_delta_str}\n"

        return text

