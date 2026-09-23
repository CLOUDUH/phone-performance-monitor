import asyncio
import json
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .beszel import BeszelClient
from .config import ConfigStore
from .snmp import SnmpCollector, safe_sample


STATIC = Path(__file__).resolve().parent / "static"
store = ConfigStore()
beszel = BeszelClient()
snmp = SnmpCollector()
sessions: dict[str, float] = {}
app = FastAPI(title="Phone Performance Monitor", version="1.0.0", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class LoginBody(BaseModel):
    pin: str = ""


def authorized(token: str | None) -> bool:
    config = store.load()
    if not config["security"].get("pin_hash"):
        return True
    if not token or token not in sessions:
        return False
    if sessions[token] < time.time():
        sessions.pop(token, None)
        return False
    return True


def require_auth(token: str | None) -> None:
    if not authorized(token):
        raise HTTPException(401, "请先用管理 PIN 解锁设置")


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/settings")
async def settings_page():
    return FileResponse(STATIC / "settings.html")


@app.get("/api/health")
async def health():
    return {"ok": True, "time": time.time()}


@app.post("/api/login")
async def login(body: LoginBody):
    if not store.verify_pin(body.pin):
        raise HTTPException(401, "PIN 不正确")
    token = secrets.token_urlsafe(32)
    sessions[token] = time.time() + 12 * 3600
    return {"token": token, "expires_in": 43200}


@app.get("/api/config")
async def get_config(x_admin_token: str | None = Header(default=None)):
    require_auth(x_admin_token)
    return store.public()


@app.put("/api/config")
async def put_config(request: Request, x_admin_token: str | None = Header(default=None)):
    require_auth(x_admin_token)
    try:
        return store.update(await request.json())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/test/beszel")
async def test_beszel(x_admin_token: str | None = Header(default=None)):
    require_auth(x_admin_token)
    try:
        return await beszel.test(store.load()["beszel"])
    except Exception as exc:
        raise HTTPException(502, f"Beszel 连接失败：{exc}") from exc


@app.post("/api/snmp/interfaces")
async def snmp_interfaces(x_admin_token: str | None = Header(default=None)):
    require_auth(x_admin_token)
    try:
        return {"items": await snmp.discover(store.load()["snmp"])}
    except Exception as exc:
        raise HTTPException(502, f"SNMP 发现失败：{exc}") from exc


@app.get("/api/snapshot")
async def snapshot():
    config = store.load()
    results = await asyncio.gather(
        beszel.snapshot(config["beszel"]),
        safe_sample(snmp, config["snmp"]),
        return_exceptions=True,
    )
    beszel_data = results[0] if not isinstance(results[0], Exception) else {"systems": [], "error": str(results[0])}
    snmp_data = results[1] if not isinstance(results[1], Exception) else {"status": "error", "error": str(results[1])}
    return {"beszel": beszel_data, "wan": snmp_data, "display": config["display"], "server_time": time.time()}


@app.get("/api/events")
async def events(request: Request):
    async def stream():
        while not await request.is_disconnected():
            config = store.load()
            results = await asyncio.gather(
                beszel.snapshot(config["beszel"]),
                safe_sample(snmp, config["snmp"]),
                return_exceptions=True,
            )
            payload: dict[str, Any] = {
                "beszel": results[0] if not isinstance(results[0], Exception) else {"systems": [], "error": str(results[0])},
                "wan": results[1] if not isinstance(results[1], Exception) else {"status": "error", "error": str(results[1])},
                "display": config["display"],
                "server_time": time.time(),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            seconds = min(float(config["beszel"].get("poll_seconds", 5)), float(config["snmp"].get("poll_seconds", 2)))
            await asyncio.sleep(max(seconds, 1))
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
