from __future__ import annotations
from telegram import Bot, Message, BotCommand, MessageEntity, LinkPreviewOptions
from telegram.request import HTTPXRequest
from telegram.helpers import escape_markdown
from telegram.error import NetworkError
from aiolimiter import AsyncLimiter
from asyncio.locks import Lock
from asyncio import sleep
from datetime import datetime
from pytz import timezone, utc
import logging
import os

from .liveroom import ResponseCodeException

if os.getenv("BILILIVENOTIBOT_TEST") != None:
    from .dummyliveroom import LiveRoom
else:
    from .liveroom import LiveRoom


from .tinyapplication import TinyApplication
from .roomrecord import RoomRecord
from .commandhandler import *


logger = logging.getLogger("BilibiliLiveNotificationBot")


class BilibiliLiveNotificationBot():

    def __init__(self, tg_bot_token: str, tg_chat_id: str, 
                    timezone_str: str, poll_interval: str) -> None:

        # bot-related
        self.token: str = tg_bot_token
        self.chat_id: str = tg_chat_id
        self.tg_bot = Bot(tg_bot_token, 
                            request=HTTPXRequest(connection_pool_size=20, read_timeout=30, write_timeout=30))
        self.app = TinyApplication(self.tg_bot, self)

        # subscribe configs
        self.subscribed_rooms: list[str] = []   # room ids
        self.room_records: dict[str, RoomRecord] = {}

        # locks
        self.config_lock = Lock()
        self.rate_limiter = AsyncLimiter(50)    # rate: 50 / 1min
        self.poll_interval: int = poll_interval

        self.timezone = timezone(timezone_str)

    async def subscribeRooms(self, rooms: list[str]):

        await self.config_lock.acquire()
        rooms = [room for room in rooms if room.isnumeric()]
        rooms = list(set(rooms))
        self.subscribed_rooms.extend(rooms)
        for room_id in rooms:
            if self.room_records.get(room_id) == None:
                self.room_records[room_id] = RoomRecord(room_id)
            if self.room_records[room_id].room == None:
                self.room_records[room_id].room = LiveRoom(int(room_id))
        self.config_lock.release()

        if rooms != []:
            logger.info(f"Subscribe rooms: {rooms}")

    async def unsubscribeRooms(self, rooms: list[str]):
        
        await self.config_lock.acquire()
        for room_id in rooms:
            if room_id in self.subscribed_rooms:
                self.subscribed_rooms.remove(room_id)
                del self.room_records[room_id]
        self.config_lock.release()
        
        logger.info(f"Unsubscribe rooms: {rooms}")

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
        if mark_delete != []:
            logger.info(f"Delete invalid rooms: {mark_delete}")

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

            # print(f"BilibiliLiveBot: {room_id}: {new_record.uname}: is_living: {new_record.is_living}")
            logger.info(f"Retrieved room info: room_id={room_id}, uname={new_record.uname}, is_living={new_record.is_living}")
            # update record && action
            # state change matrix of is_living:
            # state\input | F(沒直播)        | T(直播中)    |
            # ---------------------------------------------
            # T           | F,mark end      | T,check diff|
            # F/None      | F               | T,send msg  |
            # send msg: 發送開播提醒
            # check diff: 檢查信息變動
            current_record = self.room_records[room_id]

            if current_record.is_living != True:    # 啟動bot後的第一個狀態/false
                if new_record.is_living:            # 第一次檢查 --> living, 開始直播時間未知
                    logger.info(f"Room {room_id}: send live start message")
                    if current_record.message_sent == None:
                        current_record.message_sent = await self.sendLiveStartMessage(new_record)
                    current_record.update(new_record)
                    current_record.is_living = True
                else:                               
                    current_record.is_living = False
                    current_record.update(new_record)
            else:          # living -> 檢查下一狀態
                if new_record.is_living:            # 還在直播，檢查更新
                    if current_record.hasUpdate(new_record):
                        logger.info(f"Room {room_id}: update sent message")
                        new_record.message_sent = current_record.message_sent
                        current_record.message_sent = await self.modifySentLiveMessage(new_record)
                        current_record.update(new_record)
                else:                               # 沒在播了
                    logger.info(f"Room {room_id}: live end, mark sent message")
                    await self.markSentLiveMessageAsEnd(current_record)
                    current_record.is_living = False
                    current_record.clear()
                    
        except ResponseCodeException:
            logger.info(f"Room {room_id}: bilibili api ResponseCodeException, mark as invalid")
            self.room_records[room_id].is_valid = False
            await self.sendWarningMessage(f"直播間 {room_id} 不存在，已禁用")
        except TimeoutError:
            logger.warning(f"bilibili api TimeoutError, will resume after 5s")
            await sleep(5)
        except NetworkError:
            # telegram network error
            logger.warning("Telegram NetworkError, will resume after 5s")
            await sleep(5)
        # 什麼情況
        except Exception as e:
            logger.error(f"Unexpected error at updateRoomInformation(): {type(e).__name__}: {str(e)}")

            if os.getenv("BILILIVENOTIBOT_DEBUG") != None:
                await self.sendDebugMessage(f"Unexpected error at updateRoomInformation(): {type(e).__name__}: {str(e)}")


    # rate limit: 50/1min
    async def getRoomInfoWithRateLimit(self, room: LiveRoom):

        await self.rate_limiter.acquire()
        return await room.get_room_info()

    async def setSleepTime(self, sleep_time: int):
        # 因為好看
        self.poll_interval = sleep_time

    async def sendDebugMessage(self, message: str):

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
            text += f"開始時間： {record.start_time.astimezone(self.timezone).strftime('%Y/%m/%d %H:%M:%S')} {self.timezone.zone}\n"
        
        text = escape_markdown(text, 2, "text_link")

        return await self.tg_bot.send_message(self.chat_id, text=text, entities=[entity], link_preview_options=option)

    async def modifySentLiveMessage(self, record: RoomRecord):

        if record.message_sent != None:

            text = f"[🟢]{record.uname}: {record.room_title}\n"
            text += f"分區: {record.parent_area_name}-{record.area_name}\n"

            entity = MessageEntity(MessageEntity.TEXT_LINK, url=f"https://live.bilibili.com/{record.room_id}", offset=0, length=len(text))
            option = LinkPreviewOptions(prefer_large_media=True, show_above_text=True, url=record.cover_url)

            if record.start_time != None:
                text += f"開始時間： {record.start_time.astimezone(self.timezone).strftime('%Y/%m/%d %H:%M:%S')} {self.timezone.zone}\n"

            text = escape_markdown(text, 2, "text_link")

            return await record.message_sent.edit_text(text, entities=[entity], link_preview_options=option)
        
        else:
            return None

    async def markSentLiveMessageAsEnd(self, record: RoomRecord):

        if record.message_sent != None:
            # it is ok to modinfy a deleted message
            text = f"[🟠]{record.uname}: {record.room_title}\n"
            text += f"分區: {record.parent_area_name}-{record.area_name}\n"

            entity = MessageEntity(MessageEntity.TEXT_LINK, url=f"https://live.bilibili.com/{record.room_id}", offset=0, length=len(text))
            option = LinkPreviewOptions(prefer_large_media=True, show_above_text=True, url=record.cover_url)
            
            if record.start_time != None:
                timenow = datetime.now().astimezone(utc)
                time_delta_str = str(timenow - record.start_time).split(".")[0]
                text += f"開始時間： {record.start_time.astimezone(self.timezone).strftime('%Y/%m/%d %H:%M:%S')} {self.timezone.zone}\n"
                text += f"結束時間： {timenow.astimezone(self.timezone).strftime('%Y/%m/%d %H:%M:%S')} {self.timezone.zone}\n"
                text += f"持續時間： {time_delta_str}\n"

            text = escape_markdown(text, 2, "text_link")

            await record.message_sent.edit_text(text, entities=[entity], link_preview_options=option)
 
    async def appStart(self):

        bot_commands = [
            BotCommand("start", "啟動bot，以及顯示help"),
            BotCommand("list", "列出提醒的直播間以及記錄的信息"),
            BotCommand("subscribe", "添加提醒的直播間"),
            BotCommand("unsubscribe", "移出提醒列表"),
            BotCommand("interval", "顯示，或修改對完整的提醒列表的輪詢的間隔"),
            BotCommand("echo", "還活著嗎")
        ]
        await self.tg_bot.set_my_commands(bot_commands)

        self.app.addCommandHandler("start", handleStart)
        self.app.addCommandHandler("list", handleList)
        self.app.addCommandHandler("subscribe", handleSubscribe)
        self.app.addCommandHandler("unsubscribe", handleUnsubscribe)
        self.app.addCommandHandler("interval", handleInterval)
        self.app.addCommandHandler("echo", handleEcho)

        await self.app.start()

    async def subscribeStart(self):

        logger.info("Start subscribing live rooms")
        while True:
            for room_id in self.subscribed_rooms:
                await self.config_lock.acquire()
                await self.updateRoomInformation(room_id)
                self.config_lock.release()
            await self.deleteInvalidRooms()
            await sleep(self.poll_interval)


