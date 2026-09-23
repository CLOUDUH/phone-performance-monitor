import asyncio
import re
import time
from typing import Any

import asyncssh


ANSI_ESCAPE = re.compile(r"\x1b(?:[@-_][0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def clean_output(value: str, max_lines: int) -> list[str]:
    value = ANSI_ESCAPE.sub("", value).replace("\r", "").replace("\x00", "")
    lines = [line[:600] for line in value.splitlines()]
    return lines[-max_lines:]


class TerminalClient:
    def __init__(self) -> None:
        self._connection: asyncssh.SSHClientConnection | None = None
        self._connection_key = ""
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(cfg: dict[str, Any]) -> str:
        fields = ("host", "port", "username", "password", "private_key", "key_passphrase", "verify_host_key", "known_hosts")
        return "|".join(str(cfg.get(field, "")) for field in fields)

    async def _close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            try:
                await self._connection.wait_closed()
            except (OSError, asyncssh.Error):
                pass
        self._connection = None
        self._connection_key = ""

    async def _connect(self, cfg: dict[str, Any]) -> asyncssh.SSHClientConnection:
        host = str(cfg.get("host") or "").strip()
        username = str(cfg.get("username") or "").strip()
        if not host or not username:
            raise RuntimeError("请先填写 Ubuntu SSH 地址和用户名")
        key = self._key(cfg)
        if self._connection is not None and self._connection_key == key and not self._connection.is_closed():
            return self._connection

        async with self._lock:
            if self._connection is not None and self._connection_key == key and not self._connection.is_closed():
                return self._connection
            await self._close()
            private_key = str(cfg.get("private_key") or "").strip()
            client_keys = None
            if private_key:
                try:
                    client_keys = [asyncssh.import_private_key(private_key, str(cfg.get("key_passphrase") or "") or None)]
                except (ValueError, asyncssh.KeyImportError) as exc:
                    raise RuntimeError(f"SSH 私钥无法读取：{exc}") from exc

            if cfg.get("verify_host_key"):
                known_hosts_text = str(cfg.get("known_hosts") or "").strip()
                if not known_hosts_text:
                    raise RuntimeError("已启用主机密钥校验，但 known_hosts 为空")
                known_hosts: Any = asyncssh.import_known_hosts(known_hosts_text)
            else:
                known_hosts = None

            try:
                self._connection = await asyncio.wait_for(
                    asyncssh.connect(
                        host,
                        port=int(cfg.get("port", 22)),
                        username=username,
                        password=str(cfg.get("password") or "") or None,
                        client_keys=client_keys,
                        known_hosts=known_hosts,
                        config=None,
                    ),
                    timeout=max(2, min(15, int(cfg.get("timeout_seconds", 5)))),
                )
            except (OSError, asyncio.TimeoutError, asyncssh.Error) as exc:
                await self._close()
                raise RuntimeError(f"Ubuntu SSH 连接失败：{exc}") from exc
            self._connection_key = key
            return self._connection

    async def snapshot(self, cfg: dict[str, Any]) -> dict[str, Any]:
        if not cfg.get("enabled", False):
            return {"enabled": False, "status": "disabled", "lines": []}
        command = str(cfg.get("command") or "").strip()
        if not command:
            raise RuntimeError("Ubuntu 日志命令不能为空")
        connection = await self._connect(cfg)
        timeout = max(2, min(15, int(cfg.get("timeout_seconds", 5))))
        max_lines = max(20, min(200, int(cfg.get("max_lines", 80))))
        try:
            result = await connection.run(command, check=False, timeout=timeout)
        except (OSError, asyncio.TimeoutError, asyncssh.Error) as exc:
            await self._close()
            raise RuntimeError(f"Ubuntu 日志读取失败：{exc}") from exc
        output = str(result.stdout or "")
        if result.stderr:
            output += ("\n" if output else "") + str(result.stderr)
        return {
            "enabled": True,
            "status": "up" if result.exit_status == 0 else "error",
            "lines": clean_output(output, max_lines),
            "exit_status": result.exit_status,
            "sampled_at": time.time(),
        }


async def safe_terminal(client: TerminalClient, cfg: dict[str, Any]) -> dict[str, Any]:
    try:
        return await client.snapshot(cfg)
    except (RuntimeError, OSError, asyncio.TimeoutError, asyncssh.Error) as exc:
        return {"enabled": True, "status": "error", "lines": [], "error": str(exc)}
