import unittest
from unittest.mock import AsyncMock, patch

from app.terminal import TerminalClient, clean_output


class FakeResult:
    stdout = "\x1b[32mepoch 1\x1b[0m\nepoch 2\nepoch 3\n"
    stderr = ""
    exit_status = 0


class EmptyResult:
    stdout = ""
    stderr = ""
    exit_status = 0


class FailedResult:
    stdout = ""
    stderr = "tail: cannot open '/missing.log'"
    exit_status = 1


class FakeConnection:
    def __init__(self):
        self.run = AsyncMock(return_value=FakeResult())

    def is_closed(self):
        return False

    def close(self):
        return None

    async def wait_closed(self):
        return None


class TerminalTests(unittest.IsolatedAsyncioTestCase):
    def test_clean_output_removes_ansi_and_keeps_latest_lines(self):
        self.assertEqual(clean_output("\x1b[31mone\x1b[0m\ntwo\nthree", 2), ["two", "three"])

    async def test_snapshot_runs_remote_command(self):
        connection = FakeConnection()
        client = TerminalClient()
        config = {
            "enabled": True,
            "host": "192.168.1.83",
            "port": 22,
            "username": "monitor",
            "password": "secret",
            "verify_host_key": False,
            "command": "tail -n 80 ~/training.log",
            "max_lines": 20,
            "timeout_seconds": 5,
        }
        with patch("app.terminal.asyncssh.connect", AsyncMock(return_value=connection)):
            result = await client.snapshot(config)
        self.assertEqual(result["status"], "up")
        self.assertEqual(result["lines"], ["epoch 1", "epoch 2", "epoch 3"])
        connection.run.assert_awaited_once_with(config["command"], check=False, timeout=5)

    async def test_disabled_terminal_does_not_connect(self):
        client = TerminalClient()
        result = await client.snapshot({"enabled": False})
        self.assertEqual(result["status"], "disabled")

    async def test_empty_success_is_reported_as_connected(self):
        client = TerminalClient()
        client._connection = FakeConnection()
        client._connection.run = AsyncMock(return_value=EmptyResult())
        client._connection_key = client._key({"enabled": True, "host": "ub", "username": "monitor", "command": "true"})
        config = {"enabled": True, "host": "ub", "username": "monitor", "command": "true"}
        result = await client.snapshot(config)
        self.assertEqual(result["status"], "up")
        self.assertEqual(result["lines"], [])

    async def test_failed_command_includes_exit_status_and_stderr(self):
        connection = FakeConnection()
        connection.run = AsyncMock(return_value=FailedResult())
        client = TerminalClient()
        config = {"enabled": True, "host": "ub", "username": "monitor", "command": "tail -n 80 /missing.log"}
        with patch("app.terminal.asyncssh.connect", AsyncMock(return_value=connection)):
            result = await client.snapshot(config)
        self.assertEqual(result["status"], "error")
        self.assertIn("退出码 1", result["error"])
        self.assertIn("missing.log", result["error"])


if __name__ == "__main__":
    unittest.main()
