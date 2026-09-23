import asyncio
import time
from typing import Any

import httpx


def weather_text(code: int) -> str:
    if code == 0:
        return "晴"
    if code == 1:
        return "晴间多云"
    if code == 2:
        return "多云"
    if code == 3:
        return "阴"
    if code in (45, 48):
        return "雾"
    if 51 <= code <= 57:
        return "毛毛雨"
    if 61 <= code <= 67:
        return "雨"
    if 71 <= code <= 77:
        return "雪"
    if 80 <= code <= 82:
        return "阵雨"
    if 85 <= code <= 86:
        return "阵雪"
    if 95 <= code <= 99:
        return "雷雨"
    return "天气未知"


class WeatherClient:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(cfg: dict[str, Any]) -> str:
        return f"{float(cfg.get('latitude', 39.9042)):.4f},{float(cfg.get('longitude', 116.4074)):.4f}"

    async def snapshot(self, cfg: dict[str, Any]) -> dict[str, Any]:
        if not cfg.get("enabled", True):
            return {"enabled": False, "status": "disabled"}
        latitude = float(cfg.get("latitude", 39.9042))
        longitude = float(cfg.get("longitude", 116.4074))
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise RuntimeError("天气经纬度超出有效范围")
        key = self._key(cfg)
        refresh_seconds = max(10, min(180, int(cfg.get("refresh_minutes", 30)))) * 60
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and now - cached[0] < refresh_seconds:
            return dict(cached[1])

        async with self._lock:
            now = time.monotonic()
            cached = self._cache.get(key)
            if cached and now - cached[0] < refresh_seconds:
                return dict(cached[1])
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    response = await client.get(
                        "https://api.open-meteo.com/v1/forecast",
                        params={
                            "latitude": latitude,
                            "longitude": longitude,
                            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                            "timezone": "Asia/Shanghai",
                            "forecast_days": 1,
                        },
                    )
                    response.raise_for_status()
                    daily = response.json()["daily"]
                result = {
                    "enabled": True,
                    "status": "up",
                    "location": str(cfg.get("location") or ""),
                    "minimum": float(daily["temperature_2m_min"][0]),
                    "maximum": float(daily["temperature_2m_max"][0]),
                    "condition": weather_text(int(daily["weather_code"][0])),
                    "precipitation_probability": int(daily["precipitation_probability_max"][0] or 0),
                    "sampled_at": time.time(),
                }
                self._cache[key] = (now, result)
                return dict(result)
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                if cached:
                    stale = dict(cached[1])
                    stale["status"] = "stale"
                    stale["error"] = str(exc)
                    return stale
                raise RuntimeError(f"天气数据获取失败：{exc}") from exc


async def safe_weather(client: WeatherClient, cfg: dict[str, Any]) -> dict[str, Any]:
    try:
        return await client.snapshot(cfg)
    except (RuntimeError, OSError, asyncio.TimeoutError) as exc:
        return {"enabled": True, "status": "error", "error": str(exc)}
