*：你覺得你是？？的腦殘粉嗎*
*「我覺得我是」*

# Bilibili Live Notification Bot

Telegram bilibili直播開播提醒bot 

## 安裝&&部署

1. clone本倉庫

2. 安裝依賴：

`pip install --no-deps -r requirements.txt`

*不帶`--no-deps` 參數會有dependency conflict，但好像還是能用 ~~just do it~~* 

3. 配置參數：

可以使用`config.json`，或是environment variables。**當environment variables條目存在時，總是優先於`config.json`而生效。**

- `config.json`：

複製出一份`config.example.json`，重命名為`config.json`：

`cp config.example.json config.json`

然後依照下面的提示填寫參數：

```json
{
    "tgbot_token": "114514:aabbccdd",
    // 這個是你的telegram bot的token

    "tg_chat_id": "114514",
    // 這個是bot將會發送開播提醒的對象的chat id，私人用的話就填寫自己的那一串唯一數字id

    "timezone": "Asia/Shanghai",
    // 用於指定開播提醒中時間的時區，可選參數列表參見pytz timezone list

    "poll_interval": 10,
    // 輪詢間隔，用於指定 完整查詢一輪所有關注了的直播間的狀態間 的間隔，單位：秒
    // 實際查詢的間隔還會因bilibili api的rate limit而受限

    "subscribed_rooms": [
        "114",
        "1", 
        "3"
    ]
    // 關注的直播間的列表，對應於live.bilibili.com/後面的一串數字
    // 只有一個關注時可以只填入單一string
}
```

- environment variables

格式為`BILILIVENOTIBOT_` + 上面json中所有出現字段的大寫，如下：

`BILILIVENOTIBOT_TGBOT_TOKEN`

`BILILIVENOTIBOT_TG_CHAT_ID`

`BILILIVENOTIBOT_TIMEZONE`

`BILILIVENOTIBOT_POLL_INTERVAL`

`BILILIVENOTIBOT_SUBSCRIBED_ROOMS`  (多個直播間用`,`分隔開)

4. 啟動

`python -m bili_live_noti_bot`

## 功能

- 開播提醒，提示當前直播狀態，標題/分區發生變化時自動更新

- 記錄開播時間、結束時間和直播時長（如果可用）
<p align="center">
<img src="assets/image.png" alt="" width="50%"><img src="assets/image-1.png" alt="" width="50%">
</p>

除了在啟動時配置的參數，bot也提供了一些有用的命令，可用於修改部分參數：

```
輸入 /subscribe room_id 以添加提醒的直播間；
輸入 /list 以列出加入提醒列表的直播間；
輸入 /unsubscribe room_id 以將直播間移出提醒列表；
輸入 /interval 以顯示輪詢完整提醒列表的間隔，
輸入 /interval number_int 以修改這一間隔；
輸入 /echo 以查看bot是否在運行
```