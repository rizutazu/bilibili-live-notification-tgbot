from __future__ import annotations
from telegram import Message, constants
from telegram.helpers import escape_markdown
from datetime import datetime
from pytz import utc, BaseTzInfo
import logging

logger = logging.getLogger("RoomRecord")

class RoomRecord():
    """
                    RoomRecord Class
            記錄從bilibili api獲取到的信息，以及生成發送的消息
    """

    def __init__(self, room_id: str) -> None:

        # bot-related
        self.is_valid: bool = True                  # 是否為有效直播間

        # variables that associated with specific live
        self.message_sent: Message = None           # 已經發送的通知消息，用於在直播結束時修改

        # variables that can be directly used
        self.is_living: bool = None                 # 是否在直播
        self.room_id: str = room_id                 # 直播間號
        self.uid: str = None                        # 主播在主站的uid
        self.uname: str = None                      # 主播的顯示名稱
        self.current_room_title: str = None         # 當前的直播間標題
        self.cover_url: str = None                  # 直播封面的鏈接
        self.area_name_pair: str = None             # 所在的分區

        # variables that need special care among each live
        self.history_room_titles: list[str] = []    # 直播間用過的標題的列表，不含當前在用的，按時間從早到晚排序
        self.start_time: datetime = None            # 開始直播的時間
        self.stop_time: datetime = None             # 上一次直播結束時間，只在未開播時有效

        # snapshot
        self.snapshot: dict = {}
        
    def parseResult(self, result: dict) -> None:

        """
            parse results from bilibili api
        """

        self.uid = str(result["room_info"]["uid"])
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

    def tryUpdateRecord(self, new_record: RoomRecord, update_title_history: bool=False, update_start_time: bool=True) -> None:

        """
            以從API獲取到的新記錄尝试更新自身, 配合commitUpdateRecord使用，否則更新會回滾。
            update_title_history：是否要根據新紀錄的標題更新歷史標題記錄
            update_start_time：是否要更新開始時間（可能為0）
        """

        self.takeSnapshot()

        # basic info
        self.uid = new_record.uid
        self.uname = new_record.uname
        self.is_living = new_record.is_living

        # room title && history title log
        if update_title_history and self.current_room_title != None and self.current_room_title != new_record.current_room_title:
            self.history_room_titles.append(self.current_room_title)
        self.current_room_title = new_record.current_room_title

        if update_start_time:
            self.start_time = new_record.start_time

        self.cover_url = new_record.cover_url
        self.area_name_pair = new_record.area_name_pair

    def commitUpdateRecord(self) -> None:
        
        """
            commit update
        """

        self.snapshot = {}

    def takeSnapshot(self) -> None:

        """
            take a snapshot before update coz sendMessage may error
        """

        self.snapshot = {
            "magic": "snapshot",
            "uid": self.uid,
            "uname": self.uname,
            "is_living": self.is_living,
            "history_room_titles": self.history_room_titles.copy(),
            "current_room_title": self.current_room_title,
            "start_time": self.start_time,
            "cover_url": self.cover_url,
            "area_name_pair": self.area_name_pair
        }

    def restoreSnapshot(self) -> None:

        """
            restore snapshot
        """

        if self.snapshot.get("magic") == "snapshot":

            logger.info(f"restore snapshot for uid {self.uid}")
            
            self.uid = self.snapshot["uid"]
            self.uname = self.snapshot["uname"]
            self.is_living = self.snapshot["is_living"]
            self.history_room_titles = self.snapshot["history_room_titles"]
            self.current_room_title = self.snapshot["current_room_title"]
            self.start_time = self.snapshot["start_time"]
            self.cover_url = self.snapshot["cover_url"]
            self.area_name_pair = self.snapshot["area_name_pair"]

            self.snapshot = {}

    def liveEnd(self) -> None:    # 清空狀態

        """
            直播結束，清空和一次直播關聯的條目
        """

        self.history_room_titles.clear()
        self.message_sent = None

    def generateMessageText(self, timezone: BaseTzInfo) -> str:

        """
            生成發送的消息，包括點擊鏈接，markdown格式
        """

        # use provided live status
        text = ""
        if self.is_living:
            text += "[🟢]"
        else:
            text += "[🟠]"
        
        # username
        text += f"{self.uname}: "

        # add current title
        text += f"{self.current_room_title}"
        # add title changing history
        for title in reversed(self.history_room_titles):
            text += f" ⬅️ {title}"
        
        text += "\n"

        # add area
        text += f"分區: {self.area_name_pair}"

        # add url
        text = escape_markdown(text, 2)
        text = f"[{text}](https://live.bilibili.com/{self.room_id})\n"

        # add time-related
        if self.start_time != None:
            text += f"開始時間： {self.start_time.astimezone(timezone).strftime('%Y/%m/%d %H:%M:%S')} {timezone.zone}\n"

        if self.stop_time != None and not self.is_living:
            time_delta_str = str(self.stop_time - self.start_time).split(".")[0]
            text += f"結束時間： {self.stop_time.astimezone(timezone).strftime('%Y/%m/%d %H:%M:%S')} {timezone.zone}\n"
            text += f"持續時間： {time_delta_str}\n"

        return text
    
    def generateInfoText(self, timezone: BaseTzInfo) -> str:

        """
            generate tree-like summary text, used in /list
        """

        if not self.is_valid:
            return ""

        text = ""
        if self.is_living != None:
            if self.is_living:
                text += "[🟢]直播中："
            else:
                text += "[🟠]未開播："
            text = escape_markdown(text, 2)
            text += f" `{escape_markdown(self.uname, 2, constants.MessageEntityType.CODE)}`\n"
            
            text += f"  ├ [直播間號： {self.room_id}](https://live.bilibili.com/{self.room_id})\n"
            text += f"  ├ [個人空間： {self.uid}](space.bilibili.com/{self.uid})\n"   # so anyone wants to exploit sth here?

            if not self.is_living:
                if self.stop_time != None:
                    text +=  f"  ├ 上次直播結束時間： {self.stop_time.astimezone(timezone).strftime('%Y/%m/%d %H:%M:%S')} {timezone.zone}\n"
                else:
                    text +=  f"  ├ 上次直播結束時間： 未記錄\n"

            text += f"  └ 當前直播間標題： `{escape_markdown(self.current_room_title, 2, constants.MessageEntityType.CODE)}`\n"

        else:
            text += "[❓]未知：\n"
            text = escape_markdown(text, 2)
            text += f"  └ [直播間號： {self.room_id}](https://live.bilibili.com/{self.room_id})\n"
        
        return text

