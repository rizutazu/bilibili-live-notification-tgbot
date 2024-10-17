from .fetchconfig import *
from .bilibililivenotificationbot import BilibiliLiveNotificationBot
from asyncio import gather, run

async def main():

    token = getTGBotToken()
    chat_id = getTGChatID()
    timezone = getTimezone()
    interval = getPollInterval()
    sub_lst = getSubscribeRooms()

    bot = BilibiliLiveNotificationBot(token, chat_id, timezone, interval)
    await bot.subscribeRooms(sub_lst)

    await gather(bot.subscribeStart(), bot.appStart())

if __name__ == "__main__":
    run(main())