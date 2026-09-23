import time
from datetime import datetime
from zoneinfo import ZoneInfo

from cnlunardate import cnlunardate


BEIJING = ZoneInfo("Asia/Shanghai")
WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
ZODIAC = ("鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪")
LUNAR_MONTHS = ("正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊")
LUNAR_DIGITS = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")


def lunar_day(day: int) -> str:
    if day <= 10:
        return "初" + LUNAR_DIGITS[day - 1]
    if day < 20:
        return "十" + LUNAR_DIGITS[day - 11]
    if day == 20:
        return "二十"
    if day < 30:
        return "廿" + LUNAR_DIGITS[day - 21]
    return "三十"


def beijing_calendar(timestamp: float | None = None) -> dict[str, str]:
    local = datetime.fromtimestamp(timestamp if timestamp is not None else time.time(), BEIJING)
    lunar = cnlunardate.fromsolardate(local.date())
    month = ("闰" if lunar.isLeapMonth else "") + LUNAR_MONTHS[lunar.month - 1] + "月"
    return {
        "date": f"{local.year}/{local.month}/{local.day}",
        "weekday": WEEKDAYS[local.weekday()],
        "lunar": f"{ZODIAC[(lunar.year - 4) % 12]}年{month}{lunar_day(lunar.day)}",
    }
