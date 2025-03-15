from __future__ import annotations
from telegram import Bot, Message, LinkPreviewOptions
from telegram.request import HTTPXRequest
from telegram.error import TimedOut, BadRequest
from aiolimiter import AsyncLimiter
from asyncio.locks import Lock
from asyncio import sleep
from datetime import datetime
from pytz import timezone, utc
import logging
import os

from .liveroom import ResponseCodeException, TimeoutException, HTTPStatusError

# test flag: use DummyLiveRoom to examine the functionality
if os.getenv("BILILIVENOTIBOT_TEST") != None:
    from .dummyliveroom import LiveRoom
else:
    from .liveroom import LiveRoom

from .tinyapplication import TinyApplication, CommandHandler
from .roomrecord import RoomRecord
from .commandhandlercallbacks import *


logger = logging.getLogger("BilibiliLiveNotificationBot")



class BilibiliLiveNotificationBot():
    """
                    BilibiliLiveNotificationBot Class
            bot的主體實現，大概。
            獲取並記錄直播間信息、添加刪除直播間、發送消息，都發生在這裡。
            而bot接收command消息、處理command動作，則由 `TinyApplication` 進行。
            很是懷疑Lock()有沒有用。
    """

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

        # specify the display timezone of live_start_time 
        self.timezone = timezone(timezone_str)

    async def subscribeRooms(self, rooms: list[str]):

        """
            添加關注的直播間
        """

        await self.config_lock.acquire()
        rooms = [room for room in rooms if (room.isnumeric() and room.isascii())]
        rooms = list(set(rooms))
        self.subscribed_rooms.extend(rooms)
        for room_id in rooms:
            if self.room_records.get(room_id) == None:
                self.room_records[room_id] = RoomRecord(room_id)
            if self.room_records[room_id].room == None:
                self.room_records[room_id].room = LiveRoom(room_id)
        self.config_lock.release()

        if rooms != []:
            logger.info(f"Subscribe rooms: {rooms}")

    async def unsubscribeRooms(self, rooms: list[str]):
        
        """
            刪除關注的直播間
        """

        await self.config_lock.acquire()
        for room_id in rooms:
            if room_id in self.subscribed_rooms:
                self.subscribed_rooms.remove(room_id)
                del self.room_records[room_id]
        self.config_lock.release()
        
        logger.info(f"Unsubscribe rooms: {rooms}")

    async def getSubscribedRooms(self) -> dict[str, RoomRecord]:

        """
            獲取關注的直播間的列表
        """

        await self.config_lock.acquire()
        ret = self.room_records
        self.config_lock.release()
        return ret

    async def deleteInvalidRooms(self):
        
        """
            刪掉標記為invalid的直播間
        """

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

        """
            更新直播間信息
            使用 `LiveRecord` 記錄直播間有關狀態，包括開播時間、標題和分區等
            根據記錄的狀態判斷後續動作：發送開播消息/更新發送的消息/標記直播結束
            `LiveRecord` 只在消息發送成功後才進行更新，不知道有沒有意義
        """

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

            if current_record.is_living != True:        # 一開始沒在直播：啟動bot後的第一個狀態/not living
                if new_record.is_living:                    # not living --> living, 發消息
                    logger.info(f"Room {room_id}: send live start message")
                    current_record.updateRecord(new_record)
                    current_record.message_sent = await self.sendLiveStartMessage(new_record)
                else:                                       # not living --> not living，更新記錄
                    current_record.updateRecord(new_record)
            else:                                       # 一開始在直播，檢查下一狀態：
                if new_record.is_living:                    # 還在直播，檢查狀態更新
                    if current_record.hasUpdate(new_record):
                        logger.info(f"Room {room_id}: update sent message")
                        current_record.updateRecord(new_record, update_title_history=True)  # 記錄標題變動
                        current_record.message_sent = await self.modifySentLiveMessage(current_record)
                else:                                       # 沒在播了，清理信息和歷史標題
                    logger.info(f"Room {room_id}: live end, update sent message")
                    current_record.updateRecord(new_record, update_start_time=False)    # 此時開始時間為0，避免覆蓋記錄的開始時間
                    await self.markSentLiveMessageAsEnd(current_record)
                    current_record.liveEnd()
                    
        except ResponseCodeException as e:
            # live room may not exist
            # it seems like the server will return 19002000 rather than 1 now, if the live room does not exist 
            logger.warning(f"bilibili api ResponseCodeException code={e.code} message={e.message}")
            self.room_records[room_id].is_valid = False
            await self.sendWarningMessage(f"直播間 {room_id} 出現錯誤，已禁用： {e.code}: {e.message}")
        except TimeoutException:
            # bilibili api timeout
            logger.warning(f"bilibili api TimeoutError, will resume after 5s")
            await sleep(5)
        except TimedOut:
            # telegram timeout error
            logger.warning("Telegram TimedOut exception, will resume after 5s")
            await sleep(5)
        except HTTPStatusError as e:
            # bilibili api weird situation
            # i've encountered 504 before and i don't know why 
            if (e.error_type == "Server error"):
                logger.warning(f"bilibili api http status {e.status_code}: {e.error_type}, will resume after 5s")
                await sleep(5)
            else:
                # 什么情况
                error_text = f"bilibili api unexpected http status {e.status_code}: {e.error_type}"
                logger.error(error_text)
                if os.getenv("BILILIVENOTIBOT_DEBUG") != None:
                    await self.sendDebugMessage(error_text)
                exit(1)
        except BadRequest as e:
            # telegram bad request
            if str(e) == "Chat not found":
                logger.warning("Cannot find specified chat, maybe you forget to send /start message?")
                await sleep(10)
            else:
                logger.error(f"Bad request exception occurred during updating room information: {type(e).__name__}: {str(e)}")
                exit(1)
        # 什麼情況
        except Exception as e:
            error_text = f"Unexpected error during updating room information: {type(e).__name__}: {str(e)}"
            logger.error(error_text)
            if os.getenv("BILILIVENOTIBOT_DEBUG") != None:
                await self.sendDebugMessage(error_text)
            exit(1)

    # rate limit: 50/1min
    async def getRoomInfoWithRateLimit(self, room: LiveRoom):

        """
            我不知道有沒有這個rate limit啊，就當它有吧
        """

        await self.rate_limiter.acquire()
        return await room.get_room_info()

    async def sendDebugMessage(self, message: str):

        """
            sendDebugMessage（捧讀
        """

        if message == "":
            await self.tg_bot.sendMessage(self.chat_id, "test message")
        else:
            await self.tg_bot.sendMessage(self.chat_id, message)
  
    async def sendWarningMessage(self, message: str=""):

        """
            sendWarningMessage（捧讀
        """

        text = f"Warning: {message}"
        await self.tg_bot.sendMessage(self.chat_id, text)

    async def sendLiveStartMessage(self, record: RoomRecord) -> Message:

        """
            直播開始力
            返回發送的消息，用於後續更新/標記結束
        """

        text = record.generateMessageText(self.timezone)
        option = LinkPreviewOptions(prefer_large_media=True, show_above_text=True, url=record.cover_url)

        return await self.tg_bot.sendMessage(self.chat_id, text=text, parse_mode="MarkdownV2", link_preview_options=option)

    async def modifySentLiveMessage(self, record: RoomRecord) -> Message:

        """
            更新發送的消息
        """

        if record.message_sent != None:

            text = record.generateMessageText(self.timezone)
            option = LinkPreviewOptions(prefer_large_media=True, show_above_text=True, url=record.cover_url)

            return await record.message_sent.edit_text(text, parse_mode="MarkdownV2", link_preview_options=option)
        
        return None

    async def markSentLiveMessageAsEnd(self, record: RoomRecord):

        """
            標記結束，記錄結束時間
        """

        record.stop_time = datetime.now().astimezone(utc)
        await self.modifySentLiveMessage(record)
 
    async def appStart(self):

        """
            receive and handle command message
        """

        command_handlers = [
            CommandHandler("start", "啟動bot，以及顯示help", handleStart),
            CommandHandler("list", "列出提醒的直播間以及記錄的信息", handleList),
            CommandHandler("subscribe", "添加提醒的直播間", handleSubscribe),
            CommandHandler("unsubscribe", "移出提醒列表", handleUnsubscribe),
            CommandHandler("interval", "顯示，或修改對完整的提醒列表的輪詢的間隔", handleInterval),
            CommandHandler("echo", "還活著嗎", handleEcho)
        ]

        self.app.addCommandHandlers(command_handlers)

        await self.app.start()

    async def subscribeStart(self):

        """
            輪詢更新直播間狀態
        """

        logger.info("Start subscribing live rooms")
        while True:
            for room_id in self.subscribed_rooms:
                await self.config_lock.acquire()
                await self.updateRoomInformation(room_id)
                self.config_lock.release()
            await self.deleteInvalidRooms()
            await sleep(self.poll_interval)


