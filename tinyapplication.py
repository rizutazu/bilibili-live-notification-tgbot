from telegram.ext import Updater
from asyncio import Queue, sleep
from telegram import Bot, Message, MessageEntity, Update
from telegram.helpers import escape_markdown
from telegram.error import NetworkError
import logging

logger = logging.getLogger("TinyApplication")

class TinyApplication():
    def __init__(self, tg_bot: Bot, parent) -> None:
        self.update_queue: Queue = Queue()
        self.updater = Updater(tg_bot, self.update_queue)
        self.command_handlers: dict[str, callable] = {}
        self.parent = parent

    def addCommandHandler(self, command: str, handler: callable):
        self.command_handlers[command] = handler

    def parseCommand(self, message: Message) -> tuple[str, str]:
        types = [entity.type for entity in message.entities]
        # print(types)
        if MessageEntity.BOT_COMMAND in types:
            idx = message.text.find(" ")
            if idx == -1:
                cmd = message.text.lstrip("/")
                argument = ""
            else:
                cmd = message.text[:idx].lstrip("/").rstrip()
                argument = message.text[idx:].lstrip().rstrip()
            return (cmd, argument)
        else:
            return ("", message.text)

    async def handleUpdate(self, update: Update):
        if update.message.chat_id != int(self.parent.chat_id):
            return
        logger.info(f"New message: {update.message.text}")
        command, argument = self.parseCommand(update.message)
        handler = self.command_handlers.get(command)
        if handler != None:
            logger.info(f"Run /{command} handler")
            await handler(update, self, argument)

    async def start(self):
        while True:
            try:
                if not self.updater._initialized:
                    await self.updater.initialize()
                if not self.updater.running:
                    await self.updater.start_polling(drop_pending_updates=True)
                logger.info("Start polling updates from telegram")
                while True:
                    update = await self.update_queue.get()
                    await self.handleUpdate(update)
                    # todo: update may have None message attribute
            except NetworkError:
                logger.warning("Telegram NetworkError, will shutdown and restart after 5s")
                if self.updater.running:
                    await self.updater.stop()
                if self.updater._initialized:
                    await self.updater.shutdown()
                await sleep(5)
                continue

async def handleStart(update: Update, caller: TinyApplication, argument: str):
    message = """Bilibili live notification bot 已啟動。
輸入 /add room_id 以添加提醒的直播間；
輸入 /list 以列出加入提醒列表的直播間；
輸入 /remove room_id 以將直播間移出提醒列表；
輸入 /interval 以顯示輪詢完整提醒列表的間隔， 輸入 /interval number_int 以修改這一間隔；
輸入 /echo 以查看bot是否在運行
"""
    await update.message.reply_text(message)

async def handleList(update: Update, caller: TinyApplication, argument: str):
    text = ""
    live_status_str = ["[🟢]直播中: ", "[🟠]未開播: "]
    room_info = await caller.parent.getSubscribedRooms()
    for room_id, info in room_info.items():
        newline = ""
        if info["is_living"] != None:
            newline += live_status_str[0] if info["is_living"] else live_status_str[1]
        newline = escape_markdown(newline, 2)
        newline += f"[直播間 {room_id}](https://live.bilibili.com/{room_id})"
        if info["uname"] != None:
            newline += f": [{escape_markdown(info['uname'], 2)}](https://space.bilibili.com/{info['uid']})\n"
        else:
            newline += "\n"
        text += newline
    await update.message.reply_text(text, parse_mode="MarkdownV2", disable_web_page_preview=True)

async def handleAdd(update: Update, caller: TinyApplication, argument: str):
    if not argument.isnumeric():
        await update.message.reply_text("請給出有效的直播間號")
    else:
        room_info = await caller.parent.getSubscribedRooms()

        if argument in room_info.keys():
            await update.message.reply_text(f"直播間 {argument} 已在提醒列表中")
        else:
            await caller.parent.subscribeRooms([argument])
            await update.message.reply_text(f"已添加直播間 {argument}")

async def handleRemove(update: Update, caller: TinyApplication, argument: str):
    if not argument.isnumeric():
        await update.message.reply_text("請給出有效的直播間號")
    else:
        room_info = await caller.parent.getSubscribedRooms()

        if argument not in room_info.keys():
            await update.message.reply_text(f"直播間 {argument} 不在提醒列表中")
        else:
            await caller.parent.unsubscribeRooms([argument])
            await update.message.reply_text(f"已移除直播間 {argument}")

async def handleEcho(update: Update, caller: TinyApplication, argument: str):
    text = argument
    if argument == "":
        text = "Bot is running"
    await update.message.reply_text(text)

async def handleInterval(update: Update, caller: TinyApplication, argument: str):
    if argument == "":
        old_time = caller.parent.sleep_time
        await update.message.reply_text(f"當前的輪詢間隔為 {old_time}s")
    elif not argument.isnumeric():
        await update.message.reply_text("請給出有效的輪詢間隔")
    else:
        new_time = int(argument)
        old_time = caller.parent.sleep_time
        if old_time == new_time:
            await update.message.reply_text("輪詢間隔未發生變化")
        else:
            caller.parent.sleep_time = new_time
            await update.message.reply_text(f"已修改輪詢間隔： {old_time}s ==> {new_time}s")