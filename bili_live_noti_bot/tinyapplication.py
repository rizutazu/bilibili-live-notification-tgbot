from __future__ import annotations
from telegram.ext import Updater
from asyncio import Queue, sleep
from telegram import Bot, Message, MessageEntity, Update, BotCommand
from telegram.error import TimedOut
import logging
import os
import re

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .bilibililivenotificationbot import BilibiliLiveNotificationBot

logger = logging.getLogger("TinyApplication")

class TinyApplication():
    
    """
                    TinyApplication Class
            不是，為什麼Telegram.ext.Application沒有方便的async啟動函數啊，
            然後它的doc我怎麼看不懂啊（我太菜了.jpg
            然後就自己寫了個簡單的，之類的？
    """

    def __init__(self, tg_bot: Bot, owner) -> None:
        self.update_queue: Queue = Queue()
        self.updater = Updater(tg_bot, self.update_queue)
        self.command_handlers: dict[str, CommandHandler] = {}
        self.owner: BilibiliLiveNotificationBot = owner

    def addCommandHandlers(self, command_handlers: list[CommandHandler]):

        """
            添加CommandHandler對象
        """

        for ch in command_handlers:
            self.command_handlers[ch.command] = ch

    def parseCommand(self, message: Message) -> tuple[str, str]:

        """
            解析接收的message，分解為command和argument
            不是command類的message，text內容會全塞進argument
        """

        types = [entity.type for entity in message.entities]
        if MessageEntity.BOT_COMMAND in types:
            idx = message.text.find(" ")
            if idx == -1:
                cmd = message.text.lstrip("/")
                argument = ""
            else:
                cmd = message.text[:idx].lstrip("/")
                argument = message.text[idx:].strip()
            return (cmd, argument)
        else:
            return ("", message.text)

    async def handleUpdate(self, update: Update):

        """
            處理接收到的bot update
            不是message類型，或者來源不是配置裡指定的chat_id均會被忽略
            我好像沒打算把bot放群裡面？
        """

        if update.message == None:
            # update without effective message attribute will be ignored
            return
        if update.message.chat_id != int(self.owner.chat_id):
            return
        
        # does not handle caption
        logger.info(f"New message: text={update.message.text}")
        
        command, argument = self.parseCommand(update.message)
        command_handler = self.command_handlers.get(command)
        if command_handler != None:
            logger.info(f"Run /{command} command handler")
            await command_handler.handle(update, self, argument)

    async def start(self):

        """
            啟動bot update監聽
            帶異常自動恢復（可用性存疑）
        """

        while True:
            try:
                bot_commands = []
                for command, command_handler in self.command_handlers.items():
                    bot_commands.append(command_handler.getBotCommand())
                    logger.info(f"Add /{command} command handler")
                await self.updater.bot.setMyCommands(bot_commands)
                break
            except TimedOut:
                logger.warning(f"TimedOut exception when setting bot command, will retry after 5s")
                await sleep(5)
            # 什麼情況
            except Exception as e:
                error_text = f"Unexpected error when setting bot commands: {type(e).__name__}: {str(e)}"
                logger.error(error_text)
                if os.getenv("BILILIVENOTIBOT_DEBUG") != None:
                    await self.owner.sendDebugMessage(error_text)
                exit(1)

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
            except TimedOut:
                logger.warning("TimedOut exception when polling updates, will shutdown and restart after 5s")
                if self.updater.running:
                    await self.updater.stop()
                if self.updater._initialized:
                    await self.updater.shutdown()
                await sleep(5)
                continue
            # 什麼情況
            except Exception as e:
                error_text = f"Unexpected error when polling updates: {type(e).__name__}: {str(e)}"
                logger.error(error_text)
                if os.getenv("BILILIVENOTIBOT_DEBUG") != None:
                    await self.owner.sendDebugMessage(error_text)
                exit(1)

class CommandHandler():

    def __init__(self, command: str, description: str, callback: callable) -> None:

        # from telegram.ext.CommandHandler.__init__
        if not re.match(r"^[\da-z_]{1,32}$", command):
            raise ValueError(f"Command `/{command}` is not a valid bot command")
        
        self.command: str = command
        self.description: str = description
        self.callback: callable = callback

    def getBotCommand(self) -> BotCommand:

        return BotCommand(self.command, self.description)
    
    async def handle(self, update: Update, caller: TinyApplication, argument: str):

        """
            callback函數的signature是：
            `def callback(update: Update, caller: TinyApplication, argument: str)`
        """

        await self.callback(update, caller, argument)