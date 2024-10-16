from getsecret import *
from bilibililivenotificationbot import BilibiliLiveNotificationBot
from asyncio import gather, run

async def main():

    bot = BilibiliLiveNotificationBot(get_tg_bot_token(), get_tg_chat_id(), "Asia/Shanghai")
    await bot.subscribeRooms(get_subscribed_rooms())
    await gather(bot.subscribeStart(), bot.appStart())

if __name__ == "__main__":
    run(main())