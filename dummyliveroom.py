from datetime import datetime
'''
                    Dummy LiveRoom Class
    測試用

    get_room_info(): 
        先取當前時間，然後將其中的秒從0~59映射到0~29，然後根據秒數決定返回： 
        [0, 10): 未開播, 
        [10, 20): 直播中, 使用標題 v1
        [20, 30): 直播中, 標題切換為 v2, 還有別的？ 
'''
class LiveRoom():
    def __init__(self, room_id: int, credential) -> None:
        self.room_id: str = str(room_id)

    async def get_room_info(self) -> dict:
        second_now = datetime.now().second % 30
        if second_now >= 0 and second_now < 10:
            live_status = 0
            title = ""
            biede = ""
        elif second_now >= 10 and second_now < 20:
            live_status = 1
            title = "title " + self.room_id + " title v1"
            biede = ""
        else:
            live_status = 1
            title = "title " + self.room_id + " title v2"
            biede = "???"
        data = {
            "room_info": {
                "live_status": live_status,
                "title": title,
                "cover": "https://pbs.twimg.com/media/GZmju6EaIAAT1C0?format=jpg&name=medium",
                "parent_area_name": "父分區" + biede,
                "area_name": "子分區" + biede,
                "uid": 114514
            },
            "anchor_info": {
                "base_info": {
                    "uname": "username" + self.room_id + "username"
                }
            }
        }
        print(f"Dummy LiveRoom: live_status: {live_status} title: {title}")
        return data