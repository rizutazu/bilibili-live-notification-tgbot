from telegram.ext import Updater
from asyncio import Queue, sleep
from telegram import Bot, Message, MessageEntity, Update
from telegram.helpers import escape_markdown
from telegram.error import NetworkError
import logging

logger = logging.getLogger("TinyApplication")

class TinyApplication():
    def __init__(self, tg_bot: Bot, owner) -> None:
        self.update_queue: Queue = Queue()
        self.updater = Updater(tg_bot, self.update_queue)
        self.command_handlers: dict[str, callable] = {}
        self.owner = owner

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
                cmd = message.text[:idx].ltrip("/")
                argument = message.text[idx:].strip()
            return (cmd, argument)
        else:
            return ("", message.text)

    async def handleUpdate(self, update: Update):
        if update.message == None:
            # update without effective message attribute will be ignored
            return
        if update.message.chat_id != int(self.owner.chat_id):
            return
        
        # does not handle caption
        logger.info(f"New message: text={update.message.text}")
        
        command, argument = self.parseCommand(update.message)
        handler = self.command_handlers.get(command)
        if handler != None:
            logger.info(f"Run /{command} command handler")
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
            except NetworkError:
                logger.warning("Telegram NetworkError, will shutdown and restart after 5s")
                if self.updater.running:
                    await self.updater.stop()
                if self.updater._initialized:
                    await self.updater.shutdown()
                await sleep(5)
                continue
