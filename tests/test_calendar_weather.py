import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.calendar_info import beijing_calendar
from app.weather import WeatherClient, weather_text


class CalendarTests(unittest.TestCase):
    def test_requested_beijing_date_and_lunar_date(self):
        timestamp = datetime(2026, 9, 23, 13, 59, 55, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()
        self.assertEqual(beijing_calendar(timestamp), {
            "date": "2026/9/23",
            "weekday": "星期三",
            "lunar": "马年八月十三",
        })


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "daily": {
                "temperature_2m_min": [23.1],
                "temperature_2m_max": [29.4],
                "weather_code": [0],
                "precipitation_probability_max": [75],
            }
        }


class FakeClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, *args, **kwargs):
        FakeClient.calls += 1
        return FakeResponse()


class WeatherTests(unittest.IsolatedAsyncioTestCase):
    async def test_weather_snapshot_is_formatted_and_cached(self):
        FakeClient.calls = 0
        client = WeatherClient()
        config = {"enabled": True, "location": "北京", "latitude": 39.9042, "longitude": 116.4074, "refresh_minutes": 30}
        with patch("app.weather.httpx.AsyncClient", FakeClient):
            first = await client.snapshot(config)
            second = await client.snapshot(config)
        self.assertEqual(first["condition"], "晴")
        self.assertEqual(first["minimum"], 23.1)
        self.assertEqual(first["maximum"], 29.4)
        self.assertEqual(first["precipitation_probability"], 75)
        self.assertEqual(second["status"], "up")
        self.assertEqual(FakeClient.calls, 1)

    def test_weather_codes(self):
        self.assertEqual(weather_text(3), "阴")
        self.assertEqual(weather_text(61), "雨")
        self.assertEqual(weather_text(95), "雷雨")
