from datetime import datetime
'''
                    Dummy LiveRoom Class
    測試用

    get_room_info(): 
        先取當前時間，然後將其中的秒從0~59映射到0~29，然後根據秒數決定返回： 
        [0, 10): 未開播, 
        [10, 20): 直播中, 使用標題 v1
        [20, 30): 直播中, 標題切換為 v2, 還有別的？（修改分區名稱 
'''
class LiveRoom():
    def __init__(self, room_id: int) -> None:
        self.room_id: str = str(room_id)
        self.start_time: float = 0

    async def get_room_info(self) -> dict:
        second_now = datetime.now().second % 30
        if second_now >= 0 and second_now < 10:
            live_status = 0
            title = ""
            biede = ""
            self.start_time = 0
        elif second_now >= 10 and second_now < 20:
            live_status = 1
            title = "title " + self.room_id + " title v1"
            biede = ""
            if self.start_time == 0:
                self.start_time = datetime.now().timestamp() - 10
        else:
            live_status = 1
            title = "title " + self.room_id + " title v2"
            biede = "???"
            if self.start_time == 0:
                self.start_time = datetime.now().timestamp() - 10

        data = {
            "room_info": {
                "live_status": live_status,
                "title": title,
                "cover": "https://pbs.twimg.com/media/GZmju6EaIAAT1C0?format=jpg&name=medium",
                "parent_area_name": "父分區" + biede,
                "area_name": "子分區" + biede,
                "uid": 114514,
                "live_start_time": self.start_time
            },
            "anchor_info": {
                "base_info": {
                    "uname": "username" + self.room_id + "username"
                }
            }
        }
        print(f"Dummy LiveRoom: live_status: {live_status} title: {title} specified time: {self.start_time}")
        return data