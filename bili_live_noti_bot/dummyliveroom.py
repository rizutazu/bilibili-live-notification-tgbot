from datetime import datetime
'''
                    Dummy LiveRoom Class
    測試用

    get_room_info(): 
        先取當前時間，然後將其中的秒從0~59映射到0~29，然後根據秒數決定返回： 
        [0, 10): 未開播, 
        [10, 20): 直播中, 標題隨時間變動
        [20, 30): 直播中, 標題隨時間變動, 修改分區名稱 
'''
class LiveRoom():
    def __init__(self) -> None:
        self.start_time: float = 0
        self.last_sent_title: str = ""
        self.last_sent_area: tuple[str, str] = ("", "")

    def addRoom(self, room_id: str) -> None:
        pass

    def removeRoom(self, room_id: str) -> None:
        pass

    async def getRoomInfo(self, room_id: str) -> dict:
        second_now = datetime.now().second % 30
        if second_now >= 0 and second_now < 10:
            live_status = 0
            title = self.last_sent_title
            p_area = self.last_sent_area[0]
            area = self.last_sent_area[1]
            self.start_time = 0
        elif second_now >= 10 and second_now < 20:
            live_status = 1
            title = "rtitle" + room_id + "title v" + str(second_now)
            p_area = "父分區"
            area = "子分區"
            if self.start_time == 0:
                self.start_time = datetime.now().timestamp() - 10
        else:
            live_status = 1
            title = "rtitle" + room_id + "title v" + str(second_now)
            p_area = "父分區區"
            area = "子分區區"
            if self.start_time == 0:
                self.start_time = datetime.now().timestamp() - 10

        data = {
            "room_info": {
                "live_status": live_status,
                "title": title,
                "cover": "https://pbs.twimg.com/media/GZmju6EaIAAT1C0?format=jpg&name=medium",
                "parent_area_name": p_area,
                "area_name": area,
                "uid": 114514,
                "live_start_time": self.start_time
            },
            "anchor_info": {
                "base_info": {
                    "uname": "username" + room_id + "username"
                }
            }
        }
        self.last_sent_title = title
        self.last_sent_area = (p_area, area)
        print(f"Dummy LiveRoom: live_status: {live_status} title: {title} specified time: {self.start_time} area/biede: {p_area}-{p_area}")
        return data