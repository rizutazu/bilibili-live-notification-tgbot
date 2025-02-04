from .tinyapplication import TinyApplication
from telegram import Update
from telegram.helpers import escape_markdown

"""
    handlefunctions.py: sets of CommandHandler callback functions
"""

async def handleStart(update: Update, caller: TinyApplication, argument: str):

    message = """Bilibili live notification bot 已啟動。
輸入 /subscribe room_id 以添加提醒的直播間；
輸入 /list 以列出加入提醒列表的直播間；
輸入 /unsubscribe room_id 以將直播間移出提醒列表；
輸入 /interval 以顯示輪詢完整提醒列表的間隔，
輸入 /interval number_int 以修改這一間隔；
輸入 /echo 以查看bot是否在運行
"""
    await update.message.reply_text(message)

async def handleList(update: Update, caller: TinyApplication, argument: str):

    text = ""

    room_info = await caller.owner.getSubscribedRooms()
    for room_id, info in room_info.items():

        newline = ""
        if info["is_living"] != None:
            live_status_str = ["[🟢]直播中: ", "[🟠]未開播: "]
            newline += live_status_str[0] if info["is_living"] else live_status_str[1]
        else:
            newline += "[❓]未知: "

        newline = escape_markdown(newline, 2)

        newline += f"[直播間 {room_id}](https://live.bilibili.com/{room_id})"

        if info["uname"] != None:
            newline += f": [{escape_markdown(info['uname'], 2)}](https://space.bilibili.com/{info['uid']})\n"
        else:
            newline += "\n"

        text += newline

    await update.message.reply_text(text, parse_mode="MarkdownV2", disable_web_page_preview=True)

async def handleSubscribe(update: Update, caller: TinyApplication, argument: str):

    if not (argument.isnumeric() and argument.isascii()):
        await update.message.reply_text("請給出有效的直播間號")
    else:
        room_info = await caller.owner.getSubscribedRooms()

        if argument in room_info.keys():
            await update.message.reply_text(f"直播間 {argument} 已在提醒列表中")
        else:
            await caller.owner.subscribeRooms([argument])
            await update.message.reply_text(f"已添加直播間 {argument}")

async def handleUnsubscribe(update: Update, caller: TinyApplication, argument: str):

    if not (argument.isnumeric() and argument.isascii()):
        await update.message.reply_text("請給出有效的直播間號")
    else:
        room_info = await caller.owner.getSubscribedRooms()

        if argument not in room_info.keys():
            await update.message.reply_text(f"直播間 {argument} 不在提醒列表中")
        else:
            await caller.owner.unsubscribeRooms([argument])
            await update.message.reply_text(f"已移除直播間 {argument}")

async def handleEcho(update: Update, caller: TinyApplication, argument: str):

    text = argument
    if argument == "":
        text = "Bot is running"
    await update.message.reply_text(text)

async def handleInterval(update: Update, caller: TinyApplication, argument: str):

    old_interval = caller.owner.poll_interval

    if argument == "":  
        await update.message.reply_text(f"當前的輪詢間隔為 {old_interval}s")
    elif not (argument.isnumeric() and argument.isascii()):
        await update.message.reply_text("請給出有效的輪詢間隔")
    else:
        new_interval = int(argument)
        if old_interval == new_interval:
            await update.message.reply_text("輪詢間隔未發生變化")
        else:
            caller.owner.poll_interval = new_interval
            await update.message.reply_text(f"已修改輪詢間隔： {old_interval}s ==> {new_interval}s")