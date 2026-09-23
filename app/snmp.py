import asyncio
import time
from typing import Any

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
    walk_cmd,
)


IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"
IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.18"


class SnmpCollector:
    def __init__(self) -> None:
        self.previous: dict[str, tuple[float, int, int]] = {}

    @staticmethod
    def _oid(template: str, index: int) -> str:
        return template.replace("{ifIndex}", str(index))

    async def _target(self, cfg: dict[str, Any]):
        return await UdpTransportTarget.create(
            (cfg["host"], int(cfg.get("port", 161))),
            timeout=float(cfg.get("timeout_seconds", 2)),
            retries=0,
        )

    async def _get_pair(self, cfg: dict[str, Any]) -> tuple[int, int]:
        index = int(cfg.get("interface_index", 0))
        if index <= 0:
            raise RuntimeError("请先发现并选择爱快 WAN 接口")
        engine = SnmpEngine()
        target = await self._target(cfg)
        result = await get_cmd(
            engine,
            CommunityData(cfg.get("community", "public"), mpModel=1),
            target,
            ContextData(),
            ObjectType(ObjectIdentity(self._oid(cfg["download_oid"], index))),
            ObjectType(ObjectIdentity(self._oid(cfg["upload_oid"], index))),
        )
        error_indication, error_status, _, bindings = result
        engine.close_dispatcher()
        if error_indication:
            raise RuntimeError(str(error_indication))
        if error_status:
            raise RuntimeError(error_status.prettyPrint())
        return int(bindings[0][1]), int(bindings[1][1])

    async def sample(self, cfg: dict[str, Any]) -> dict[str, Any]:
        if not cfg.get("enabled") or not cfg.get("host"):
            return {"enabled": False, "status": "disabled", "download_bps": 0, "upload_bps": 0}
        now = time.monotonic()
        down, up = await self._get_pair(cfg)
        key = f"{cfg['host']}:{cfg.get('port', 161)}:{cfg.get('interface_index', 0)}"
        previous = self.previous.get(key)
        self.previous[key] = (now, down, up)
        if not previous:
            return {"enabled": True, "status": "warming", "download_bps": 0, "upload_bps": 0}
        elapsed = max(now - previous[0], 0.001)
        wrap = 2**64
        down_delta = down - previous[1] if down >= previous[1] else wrap - previous[1] + down
        up_delta = up - previous[2] if up >= previous[2] else wrap - previous[2] + up
        return {
            "enabled": True,
            "status": "up",
            "download_bps": down_delta * 8 / elapsed,
            "upload_bps": up_delta * 8 / elapsed,
            "sampled_at": time.time(),
        }

    async def discover(self, cfg: dict[str, Any]) -> list[dict[str, Any]]:
        if not cfg.get("host") or not cfg.get("community"):
            raise RuntimeError("请先填写 SNMP 地址和团体名")
        engine = SnmpEngine()
        target = await self._target(cfg)
        interfaces: dict[int, dict[str, Any]] = {}
        for base_oid, field in ((IF_NAME, "name"), (IF_ALIAS, "alias")):
            async for error_indication, error_status, _, bindings in walk_cmd(
                engine,
                CommunityData(cfg.get("community", "public"), mpModel=1),
                target,
                ContextData(),
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False,
            ):
                if error_indication:
                    engine.close_dispatcher()
                    raise RuntimeError(str(error_indication))
                if error_status:
                    engine.close_dispatcher()
                    raise RuntimeError(error_status.prettyPrint())
                for oid, value in bindings:
                    index = int(str(oid).split(".")[-1])
                    interfaces.setdefault(index, {"index": index, "name": "", "alias": ""})[field] = value.prettyPrint()
        engine.close_dispatcher()
        return sorted(interfaces.values(), key=lambda item: item["index"])


async def safe_sample(collector: SnmpCollector, cfg: dict[str, Any]) -> dict[str, Any]:
    try:
        return await collector.sample(cfg)
    except (RuntimeError, OSError, asyncio.TimeoutError) as exc:
        return {"enabled": True, "status": "error", "error": str(exc), "download_bps": 0, "upload_bps": 0}

