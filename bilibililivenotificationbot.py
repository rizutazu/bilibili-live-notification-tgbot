from __future__ import annotations
from telegram import Bot, Message, BotCommand, MessageEntity, LinkPreviewOptions
from telegram.request import HTTPXRequest
from telegram.helpers import escape_markdown
from bilibili_api import Credential, ResponseCodeException
from aiolimiter import AsyncLimiter
from asyncio.locks import Lock
from asyncio import sleep
from datetime import datetime
from pytz import timezone

from dummyliveroom import LiveRoom
# from bilibili_api.live import LiveRoom
from tinyapplication import TinyApplication, handleStart, handleList, handleAdd, handleRemove, handleEcho
from roomrecord import RoomRecord

class BilibiliLiveNotificationBot():

    def __init__(self, tg_bot_token: str, tg_chat_id: str, 
                    timezone_str: str, bili_credential: Credential=None) -> None:

        # bot-related
        self.token: str = tg_bot_token
        self.chat_id: str = tg_chat_id
        self.tg_bot = Bot(tg_bot_token, 
                            request=HTTPXRequest(connection_pool_size=20, read_timeout=30, write_timeout=30))
        self.app = TinyApplication(self.tg_bot, self)

        # subscribe configs
        self.bili_credential = bili_credential
        self.subscribed_rooms: list[str] = []   # room ids
        self.room_records: dict[str, RoomRecord] = {}

        # locks
        self.config_lock = Lock()
        self.rate_limiter = AsyncLimiter(50)    # rate: 50 / 1min
        self.sleep_time: int = 5

        self.timezone = timezone(timezone_str)

    async def subscribeRooms(self, rooms: list[str]):

        await self.config_lock.acquire()
        rooms = [room for room in rooms if room.isnumeric()]
        self.subscribed_rooms.extend(rooms)
        for room_id in rooms:
            if self.room_records.get(room_id) == None:
                self.room_records[room_id] = RoomRecord(room_id)
            if self.room_records[room_id].room == None:
                self.room_records[room_id].room = LiveRoom(int(room_id), self.bili_credential)
        self.config_lock.release()

    async def unsubscribeRooms(self, rooms: list[str]):
        
        await self.config_lock.acquire()
        for room_id in rooms:
            if room_id in self.subscribed_rooms:
                self.subscribed_rooms.remove(room_id)
                del self.room_records[room_id]
        self.config_lock.release()

    async def getSubscribedRooms(self) -> dict[str, dict]:

        await self.config_lock.acquire()
        ret = {}
        for room_id, record in self.room_records.items():
            ret[room_id] = {
                "is_living": record.is_living,
                "uname": record.uname,
                "uid": record.uid
            }
        self.config_lock.release()
        return ret

    async def deleteInvalidRooms(self):
        
        await sleep(0)
        await self.config_lock.acquire()
        mark_delete = [room_id for room_id, record in self.room_records.items() if not record.is_valid]
        for room_id in mark_delete:
            self.subscribed_rooms.remove(room_id)
            del self.room_records[room_id]
        self.config_lock.release()

    async def updateRoomInformation(self, room_id: str):

        await sleep(0)

        # maybe async race condition?
        if room_id not in self.subscribed_rooms or self.room_records.get(room_id) == None:
            return

        # skip invalid room
        if not self.room_records[room_id].is_valid:
            return

        try:
            result = await self.getRoomInfoWithRateLimit(self.room_records[room_id].room)

            new_record = RoomRecord(room_id)
            new_record.parseResult(result)

            print(f"BilibiliLiveBot: {room_id}: {new_record.uname}: is_living: {new_record.is_living}")

            # update record && action
            # state change matrix of is_living:
            # state\input | 0(沒直播)        | 1(直播中)    | 2(輪播中)    | 
            # -----------------------------------------------------------
            # None        | F               | T,send nmsg | F           |
            # T           | F,mark end      | T,check diff| F, mark end |
            # F           | F               | T,send msg  | F           |
            # send nmsg: 等於send msg，但不含開始時間,也不會記錄這個
            # check diff: 檢查title的變動
            current_record = self.room_records[room_id]

            if current_record.is_living == None:    # 啟動bot -> 第一個狀態
                if new_record.is_living:        # 第一次就是在live，假定直播開始時間未知，故不設置
                    current_record.is_living = True
                    current_record.update(new_record)
                    current_record.message_sent = await self.sendLiveStartMessage(current_record)
                else:
                    current_record.is_living = False
                    current_record.update(new_record)
            elif current_record.is_living:          # living -> 檢查下一狀態
                if new_record.is_living:            # 還在直播，檢查更新
                    if current_record.hasUpdate(new_record):
                        current_record.update(new_record)
                        current_record.message_sent = await self.modifySentLiveMessage(current_record)
                else:                               # 沒在播了
                    await self.markSentLiveMessageAsEnd(current_record)
                    current_record.is_living = False
                    current_record.clear()
            else:                               # not living -> 檢查下一狀態
                if new_record.is_living:        # 無到有開始直播，記錄開始直播的時間
                    current_record.is_living = True
                    current_record.start_time = datetime.now()
                    current_record.update(new_record)
                    current_record.message_sent = await self.sendLiveStartMessage(current_record)
                else:
                    if current_record.hasUpdate(new_record):
                        current_record.update(new_record)
                    
        except ResponseCodeException:
            self.room_records[room_id].is_valid = False
            await self.sendWarningMessage(f"直播間 {room_id} 不存在，已禁用")
        except TimeoutError:
            print(f"TimeoutError occurred at updateRoomInformation(). Will retry later")
            await sleep(5)
        except Exception as e:
            await self.sendMessage("Unexpected error at updateRoomInformation(): " + str(e))

    # rate limit: 50/1min
    async def getRoomInfoWithRateLimit(self, room: LiveRoom):

        await self.rate_limiter.acquire()
        return await room.get_room_info()

    async def setSleepTime(self, sleep_time: int):
        # 因為好看
        self.sleep_time = sleep_time

    async def sendMessage(self, message: str):

        if message == "":
            await self.tg_bot.send_message(self.chat_id, "test message")
        else:
            await self.tg_bot.send_message(self.chat_id, message)
  
    async def sendWarningMessage(self, message: str=""):

        text = f"Warning: {message}"
        await self.tg_bot.send_message(self.chat_id, text)

    async def sendLiveStartMessage(self, record: RoomRecord) -> Message:

        text = f"[🟢]{record.uname}: {record.room_title}\n"
        text += f"分區: {record.parent_area_name}-{record.area_name}\n"

        entity = MessageEntity(MessageEntity.TEXT_LINK, url=f"https://live.bilibili.com/{record.room_id}", offset=0, length=len(text))
        option = LinkPreviewOptions(prefer_large_media=True, show_above_text=True, url=record.cover_url)

        if record.start_time != None:
            text += f"開始時間： {self.timezone.localize(record.start_time).strftime('%Y/%m/%d %H:%M:%S')} {self.timezone.zone}\n"
        
        text = escape_markdown(text, 2, "text_link")

        return await self.tg_bot.send_message(self.chat_id, text=text, entities=[entity], link_preview_options=option)

    async def modifySentLiveMessage(self, record: RoomRecord):
        
        # text = record.message_sent.text
        # text = text.replace(record.room_title, new_title, 1)
        # split = text.split("\n")
        # text_len_without_time = len(split[0] + split[1]) + 2
        text = f"[🟢]{record.uname}: {record.room_title}\n"
        text += f"分區: {record.parent_area_name}-{record.area_name}\n"

        entity = MessageEntity(MessageEntity.TEXT_LINK, url=f"https://live.bilibili.com/{record.room_id}", offset=0, length=len(text))
        option = LinkPreviewOptions(prefer_large_media=True, show_above_text=True, url=record.cover_url)

        if record.start_time != None:
            text += f"開始時間： {self.timezone.localize(record.start_time).strftime('%Y/%m/%d %H:%M:%S')} {self.timezone.zone}\n"

        text = escape_markdown(text, 2, "text_link")

        return await record.message_sent.edit_text(text, entities=[entity], link_preview_options=option)

    async def markSentLiveMessageAsEnd(self, record: RoomRecord):

        if record.message_sent != None:
            # it is ok to modinfy a deleted message
            text = f"[🟠]{record.uname}: {record.room_title}\n"
            text += f"分區: {record.parent_area_name}-{record.area_name}\n"

            entity = MessageEntity(MessageEntity.TEXT_LINK, url=f"https://live.bilibili.com/{record.room_id}", offset=0, length=len(text))
            option = LinkPreviewOptions(prefer_large_media=True, show_above_text=True, url=record.cover_url)
            
            if record.start_time != None:
                timenow = datetime.now()
                time_delta_str = str(timenow - record.start_time).split(".")[0]
                text += f"開始時間： {self.timezone.localize(record.start_time).strftime('%Y/%m/%d %H:%M:%S')} {self.timezone.zone}\n"
                text += f"結束時間： {self.timezone.localize(timenow).strftime('%Y/%m/%d %H:%M:%S')} {self.timezone.zone}\n"
                text += f"持續時間： {time_delta_str}\n"

            text = escape_markdown(text, 2, "text_link")

            await record.message_sent.edit_text(text, entities=[entity], link_preview_options=option)
 
    async def appStart(self):

        bot_commands = [
            BotCommand("start", "啟動bot"),
            BotCommand("list", "列出關注的直播間以及記錄的信息"),
            BotCommand("add", "添加關注的直播間"),
            BotCommand("remove", "移除關注的直播間"),
            BotCommand("echo", "echo")
        ]
        await self.tg_bot.set_my_commands(bot_commands)

        self.app.addCommandHandler("start", handleStart)
        self.app.addCommandHandler("list", handleList)
        self.app.addCommandHandler("add", handleAdd)
        self.app.addCommandHandler("remove", handleRemove)
        self.app.addCommandHandler("echo", handleEcho)

        print("poll started")

        await self.app.start()

    async def subscribeStart(self):

        while True:
            for room_id in self.subscribed_rooms:
                await self.config_lock.acquire()
                await self.updateRoomInformation(room_id)
                self.config_lock.release()
            await self.deleteInvalidRooms()
            await sleep(self.sleep_time)


