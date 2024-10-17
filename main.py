from getsecret import *
from bilibililivenotificationbot import BilibiliLiveNotificationBot
from asyncio import gather, run
import logging

logging.basicConfig(
    format="[%(levelname)s][%(asctime)s]%(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO
)

async def main():

    bot = BilibiliLiveNotificationBot(get_tg_bot_token(), get_tg_chat_id(), "Asia/Shanghai")
    await bot.subscribeRooms(get_subscribed_rooms())
    # await bot.subscribeRooms(["114514"])
    await gather(bot.subscribeStart(), bot.appStart())

if __name__ == "__main__":
    run(main())