import asyncio
import time
from typing import Any

import httpx


class BeszelClient:
    def __init__(self) -> None:
        self._token = ""
        self._token_key = ""
        self._lock = asyncio.Lock()

    @staticmethod
    def _base_url(value: str) -> str:
        value = value.strip().rstrip("/")
        if value and not value.startswith(("http://", "https://")):
            value = "http://" + value
        return value

    async def _auth(self, cfg: dict[str, Any], force: bool = False) -> str:
        base = self._base_url(cfg.get("url", ""))
        email = cfg.get("email", "")
        password = cfg.get("password", "")
        key = f"{base}|{email}|{password}"
        if self._token and self._token_key == key and not force:
            return self._token
        if not base or not email or not password:
            raise RuntimeError("请先在设置中填写 Beszel 地址、邮箱和密码")
        async with self._lock:
            if self._token and self._token_key == key and not force:
                return self._token
            async with httpx.AsyncClient(verify=bool(cfg.get("verify_tls", True)), timeout=8) as client:
                response = await client.post(
                    f"{base}/api/collections/users/auth-with-password",
                    json={"identity": email, "password": password},
                )
                response.raise_for_status()
                self._token = response.json()["token"]
                self._token_key = key
                return self._token

    async def _get(self, cfg: dict[str, Any], path: str) -> dict[str, Any]:
        token = await self._auth(cfg)
        base = self._base_url(cfg["url"])
        async with httpx.AsyncClient(verify=bool(cfg.get("verify_tls", True)), timeout=8) as client:
            response = await client.get(f"{base}{path}", headers={"Authorization": token})
            if response.status_code == 401:
                token = await self._auth(cfg, force=True)
                response = await client.get(f"{base}{path}", headers={"Authorization": token})
            response.raise_for_status()
            return response.json()

    async def snapshot(self, cfg: dict[str, Any]) -> dict[str, Any]:
        query = "?page=1&perPage=200&sort=%2Bname&fields=id%2Cname%2Chost%2Cstatus%2Cinfo%2Cupdated"
        payload = await self._get(cfg, "/api/collections/systems/records" + query)
        latest_stats: dict[str, dict[str, Any]] = {}
        try:
            stats_query = (
                "?page=1&perPage=200&sort=-created"
                "&filter=type%3D%271m%27"
                "&fields=system%2Ccreated%2Cstats"
            )
            stats_payload = await self._get(cfg, "/api/collections/system_stats/records" + stats_query)
            for record in stats_payload.get("items", []):
                system_id = record.get("system")
                if system_id and system_id not in latest_stats:
                    latest_stats[system_id] = record.get("stats") or {}
        except (httpx.HTTPError, RuntimeError, KeyError):
            # Restricted or older Beszel installations may deny historical stats.
            pass

        systems = []
        for row in payload.get("items", []):
            info = row.get("info") or {}
            stats = latest_stats.get(row.get("id"), {})
            bandwidth = stats.get("b")
            if not isinstance(bandwidth, list) or len(bandwidth) < 2:
                bandwidth = [0, 0]
            gpu = info.get("g")
            if gpu is None:
                gpu_values = stats.get("g") or {}
                if isinstance(gpu_values, dict):
                    gpu = max(
                        (device.get("u", 0) for device in gpu_values.values() if isinstance(device, dict)),
                        default=None,
                    )
            systems.append({
                "id": row.get("id"),
                "name": row.get("name", "未命名"),
                "host": row.get("host", ""),
                "status": row.get("status", "unknown"),
                "updated": row.get("updated"),
                "cpu": info.get("cpu"),
                "memory": info.get("mp"),
                "disk": info.get("dp"),
                "gpu": gpu,
                "network_bps": info.get("bb") or ((info.get("b") or 0) * 1024 * 1024),
                # Beszel stores bytes/second; the UI displays bits/second.
                "network_up_bps": bandwidth[0] * 8,
                "network_down_bps": bandwidth[1] * 8,
                "uptime_seconds": info.get("u"),
                "temperature": info.get("dt"),
                "load": info.get("la") or [info.get("l1"), info.get("l5"), info.get("l15")],
                "threads": info.get("t") or info.get("c"),
                "agent_version": info.get("v"),
            })
        return {"systems": systems, "source": self._base_url(cfg.get("url", "")), "sampled_at": time.time()}

    async def test(self, cfg: dict[str, Any]) -> dict[str, Any]:
        result = await self.snapshot(cfg)
        return {"ok": True, "systems": len(result["systems"]), "source": result["source"]}
