from __future__ import annotations
from telegram import Bot, Message, LinkPreviewOptions
import telegram.request
import telegram.error
from asyncio.locks import Lock
from asyncio import sleep
from datetime import datetime
from pytz import timezone, utc
import logging
import os
import traceback

from .liveroom import HTTPStatusError, NetworkError, CodeFieldException, RoomNotExistException

# test flag: use DummyLiveRoom to examine the functionality
if os.getenv("BILILIVENOTIBOT_TEST") != None:
    from .dummyliveroom import LiveRoom
else:
    from .liveroom import LiveRoom

from .tinyapplication import TinyApplication, CommandHandler
from .roomrecord import RoomRecord
from .commandhandlercallbacks import *
from .util import isValidPositiveInt


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
                            request=telegram.request.HTTPXRequest(connection_pool_size=20, read_timeout=30, write_timeout=30))
        self.app = TinyApplication(self.tg_bot, self)

        # subscribe configs
        self.room_records: dict[str, RoomRecord] = {}
        self.liveroom: LiveRoom = LiveRoom()

        # locks
        self.config_lock = Lock()
        self.poll_interval: int = poll_interval

        # specify the display timezone of live_start_time 
        self.timezone = timezone(timezone_str)

    async def subscribeRooms(self, room_ids: list[str]):

        """
            添加關注的直播間
        """

        await sleep(0)
        await self.config_lock.acquire()
        room_ids = [room_id for room_id in room_ids if isValidPositiveInt(room_id)]
        room_ids = list(set(room_ids))
        for room_id in room_ids:
            if self.room_records.get(room_id) == None:
                self.room_records[room_id] = RoomRecord(room_id)
                self.liveroom.addRoom(room_id)
        self.config_lock.release()

        if room_ids != []:
            logger.info(f"Subscribe rooms: {room_ids}")

    async def unsubscribeRooms(self, room_ids: list[str]):
        
        """
            刪除關注的直播間
        """

        await sleep(0)
        await self.config_lock.acquire()
        for room_id in room_ids:
            if self.room_records.get(room_id) != None:
                del self.room_records[room_id]
                self.liveroom.removeRoom(room_id)
        self.config_lock.release()
        
        logger.info(f"Unsubscribe rooms: {room_ids}")

    async def getSubscribedRooms(self) -> dict[str, RoomRecord]:

        """
            獲取關注的直播間的列表
        """

        await sleep(0)
        await self.config_lock.acquire()
        ret = self.room_records.copy()
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
            self.liveroom.removeRoom(room_id)
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
        if self.room_records.get(room_id) == None:
            return

        # skip invalid room
        if not self.room_records[room_id].is_valid:
            return

        try:
            result = await self.getRoomInfo(room_id)

            fetched_record = RoomRecord(room_id)
            fetched_record.parseResult(result)

            # update record && action
            # state change matrix of is_living:
            # state\input | F(沒直播)        | T(直播中)    |
            # ---------------------------------------------
            # T           | F,mark end      | T,check diff|
            # F/None      | F               | T,send msg  |
            # send msg: 發送開播提醒
            # check diff: 檢查信息變動
            current_record = self.room_records[room_id]
            current_record.restoreSnapshot()

            if current_record.is_living != True:        # 一開始沒在直播：啟動bot後的第一個狀態/not living
                if fetched_record.is_living:                    # not living --> living, 發消息
                    logger.info(f"Room {room_id}: send live start message")
                    current_record.tryUpdateRecord(fetched_record)
                    current_record.message_sent = await self.sendLiveStartMessage(current_record)
                    current_record.commitUpdateRecord()
                else:                                       # not living --> not living，更新記錄
                    current_record.tryUpdateRecord(fetched_record)
                    current_record.commitUpdateRecord()
            else:                                       # 一開始在直播，檢查下一狀態：
                if fetched_record.is_living:                    # 還在直播，檢查狀態更新
                    if current_record.hasUpdate(fetched_record):
                        logger.info(f"Room {room_id}: update sent message")
                        current_record.tryUpdateRecord(fetched_record, update_title_history=True)  # 記錄標題變動
                        current_record.message_sent = await self.modifySentLiveMessage(current_record)
                        current_record.commitUpdateRecord()
                else:                                       # 沒在播了，清理信息和歷史標題
                    logger.info(f"Room {room_id}: live end, update sent message")
                    current_record.tryUpdateRecord(fetched_record, update_start_time=False)    # 此時開始時間為0，避免覆蓋記錄的開始時間
                    await self.markSentLiveMessageAsEnd(current_record)
                    current_record.commitUpdateRecord()
                    current_record.liveEnd()
                    
        except RoomNotExistException:
            logger.warning(f"bilibili api RoomNotExistException")
            self.room_records[room_id].is_valid = False
            await self.sendErrorMessage(f"直播間 {room_id} 不存在，已禁用")
        except HTTPStatusError as e:
            # bilibili api weird situation
            # i've encountered 504 before and i don't know why 
            if (e.error_type == "Server error"):
                logger.warning(f"bilibili api http status {e.status_code}: {e.error_type}, will resume after 10s")
                await sleep(10)
            else:
                # 什么情况
                error_text = f"bilibili api unexpected http status {e.status_code}: {e.error_type}"
                logger.error(error_text)
                exit(1)
        except NetworkError as e:
            # bilibili api network error
            logger.warning(f"bilibili api NetworkError, will resume after 10s")
            if e.e != None:
                logger.warning(f"Maybe unexpected error: {traceback.format_exc()}")
            await sleep(10)
        except telegram.error.BadRequest as e:
            # telegram bad request
            if str(e) == "Chat not found":
                logger.warning("Cannot find specified chat, maybe you forget to send /start message?")
                await sleep(10)
            else:
                logger.error(f"Bad request exception occurred during updating room information: {type(e).__name__}: {str(e)}")
                exit(1)
        except telegram.error.NetworkError:
            # telegram NetworkError error
            logger.warning("Telegram NetworkError exception, will resume after 10s")
            await sleep(10)

        except CodeFieldException as e:
            error_text = f"bilibili api CodeFieldException: {e.code}: {e.message}"
            logger.error(error_text)
            # nooooooooooooooooooooo
            await self.sendErrorMessage(f"bilibili api 出错，bot即将退出： {e.code}: {e.message}。请将以上信息发送给开发者。")
            exit(1)
        # 什麼情況
        except Exception as e:
            error_text = f"Unexpected error during updating room information: {traceback.format_exc()}"
            logger.error(error_text)
            await self.sendErrorMessage(f"bot 发生意外错误： {traceback.format_exc()}。请将以上信息发送给开发者。")
            exit(1)

    async def getRoomInfo(self, room_id: str):

        """
            獲取直播間信息
        """

        await sleep(0)
        return await self.liveroom.getRoomInfo(room_id)
  
    async def sendErrorMessage(self, message: str=""):

        """
            sendErrorMessage（捧讀
        """

        await sleep(0)
        text = f"Error: {message}"
        count = 3
        while count > 0:
            try:
                await self.tg_bot.sendMessage(self.chat_id, text)
                logger.warning("error message sent: " + message)
                return
            except Exception:
                count -= 1
        logger.warning("failed to send error message after retrying 3 times")



    async def sendLiveStartMessage(self, record: RoomRecord) -> Message:

        """
            直播開始力
            返回發送的消息，用於後續更新/標記結束
        """

        await sleep(0)
        text = record.generateMessageText(self.timezone)
        option = LinkPreviewOptions(prefer_large_media=True, show_above_text=True, url=record.cover_url)

        return await self.tg_bot.sendMessage(self.chat_id, text=text, parse_mode="MarkdownV2", link_preview_options=option)

    async def modifySentLiveMessage(self, record: RoomRecord) -> Message:

        """
            更新發送的消息
        """

        await sleep(0)
        if record.message_sent != None:

            text = record.generateMessageText(self.timezone)
            option = LinkPreviewOptions(prefer_large_media=True, show_above_text=True, url=record.cover_url)

            return await record.message_sent.edit_text(text, parse_mode="MarkdownV2", link_preview_options=option)
        
        return None

    async def markSentLiveMessageAsEnd(self, record: RoomRecord):

        """
            標記結束，記錄結束時間
        """

        await sleep(0)
        record.stop_time = datetime.now().astimezone(utc)
        await self.modifySentLiveMessage(record)
 
    async def appStart(self):

        """
            receive and handle command message
        """

        command_handlers = [
            CommandHandler("start", "啟動bot，以及顯示help", handleStart),
            CommandHandler("list", "列出訂閱的直播間以及記錄的信息", handleList),
            CommandHandler("subscribe", "添加訂閱的直播間", handleSubscribe),
            CommandHandler("unsubscribe", "移出訂閱列表", handleUnsubscribe),
            CommandHandler("interval", "顯示，或修改對完整的訂閱列表的輪詢的間隔", handleInterval),
            CommandHandler("echo", "還活著嗎", handleEcho)
        ]

        self.app.addCommandHandlers(command_handlers)

        await self.app.start()

    async def subscribeStart(self):

        """
            輪詢更新直播間狀態
        """

        await sleep(0)
        logger.info("Start subscribing live rooms")
        while True:
            for room_id in self.room_records.keys():
                await self.config_lock.acquire()
                await self.updateRoomInformation(room_id)
                self.config_lock.release()
            await self.deleteInvalidRooms()
            await sleep(self.poll_interval)


