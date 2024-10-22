from .fetchconfig import *
from .bilibililivenotificationbot import BilibiliLiveNotificationBot
from asyncio import gather, run
import os

"""
    __main__.py: fetch config and start bot
"""

async def main():

    token = getTGBotToken()
    chat_id = getTGChatID()
    timezone = getTimezone()
    interval = getPollInterval()
    sub_lst = getSubscribedRooms()

    bilibot = BilibiliLiveNotificationBot(token, chat_id, timezone, interval)

    if os.getenv("BILILIVENOTIBOT_TEST") != None:
        bilibot.poll_interval = 3
        await bilibot.subscribeRooms(["114"])
    else:
        await bilibot.subscribeRooms(sub_lst)

    await gather(bilibot.subscribeStart(), bilibot.appStart())

if __name__ == "__main__":
    run(main())