from .tinyapplication import TinyApplication
from telegram import Update
from .util import isValidPositiveInt

"""
    handlefunctions.py: sets of CommandHandler callback functions
"""

async def handleStart(update: Update, caller: TinyApplication, argument: str):

    message = """Bilibili live notification bot 已啟動。
輸入 /subscribe room_id 以添加訂閱的直播間；
輸入 /list 以列出加入訂閱列表的直播間；
輸入 /unsubscribe room_id 以將直播間移出訂閱列表；
輸入 /interval 以顯示輪詢完整訂閱列表的間隔，
輸入 /interval number_int 以修改這一間隔；
輸入 /echo 以查看bot是否在運行；
輸入 /frame room_id 以獲取直播間的關鍵幀
"""
    await update.message.reply_text(message)

async def handleList(update: Update, caller: TinyApplication, argument: str):

    text = ""
    rooms = await caller.owner.getSubscribedRooms()
    for room in rooms.values():
        text += room.generateInfoText(caller.owner.timezone)
        if text != "":
            text += "\n"
    if text == "":
        text = "無關注的直播間"

    await update.message.reply_text(text, parse_mode="MarkdownV2", disable_web_page_preview=True)

async def handleSubscribe(update: Update, caller: TinyApplication, argument: str):

    if not isValidPositiveInt(argument):
        await update.message.reply_text("請給出有效的直播間號")
    else:
        rooms = await caller.owner.getSubscribedRooms()

        if argument in rooms.keys():
            await update.message.reply_text(f"直播間 {argument} 已在訂閱列表中")
        else:
            await caller.owner.subscribeRooms([argument])
            await update.message.reply_text(f"已添加直播間 {argument}")

async def handleUnsubscribe(update: Update, caller: TinyApplication, argument: str):

    if not isValidPositiveInt(argument):
        await update.message.reply_text("請給出有效的直播間號")
    else:
        rooms = await caller.owner.getSubscribedRooms()

        if argument not in rooms.keys():
            await update.message.reply_text(f"直播間 {argument} 不在訂閱列表中")
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
    elif not isValidPositiveInt(argument):
        await update.message.reply_text("請給出有效的輪詢間隔")
    else:
        new_interval = int(argument)
        if old_interval == new_interval:
            await update.message.reply_text("輪詢間隔未發生變化")
        else:
            caller.owner.poll_interval = new_interval
            await update.message.reply_text(f"已修改輪詢間隔： {old_interval}s ==> {new_interval}s")

async def handleFrame(update: Update, caller: TinyApplication, argument: str):
    if update.message != None:
        reply_target = update.message
    elif update.callback_query != None:
        reply_target = update.callback_query.message
    else:
        return

    url, msg = await caller.owner.getKeyFrameUrl(argument)
    if msg != None:
        await reply_target.reply_text(f"獲取關鍵幀失敗： {msg}")
        return

    await reply_target.reply_photo(photo=url, do_quote=True)
        

    
