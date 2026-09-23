import unittest
from unittest.mock import AsyncMock

from app.beszel import BeszelClient


class BeszelClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_combines_system_summary_and_latest_network_stats(self):
        client = BeszelClient()
        client._get = AsyncMock(side_effect=[
            {
                "items": [{
                    "id": "ub-id",
                    "name": "UB",
                    "host": "192.168.1.10",
                    "status": "up",
                    "updated": "2026-09-23 00:00:00Z",
                    "info": {"cpu": 21.4, "mp": 48.2, "g": 67, "u": 3600, "v": "0.13.2", "la": [1.25, 1.1, 0.9], "t": 28},
                }]
            },
            {
                "items": [{
                    "system": "ub-id",
                    "created": "2026-09-23 00:00:00Z",
                    "stats": {"b": [125000, 875000]},
                }]
            },
        ])

        result = await client.snapshot({"url": "http://beszel.local"})
        system = result["systems"][0]
        self.assertEqual(system["gpu"], 67)
        self.assertEqual(system["network_up_bps"], 1000000)
        self.assertEqual(system["network_down_bps"], 7000000)
        self.assertEqual(system["load"], [1.25, 1.1, 0.9])
        self.assertEqual(system["threads"], 28)

    async def test_snapshot_falls_back_when_stats_collection_is_unavailable(self):
        client = BeszelClient()
        client._get = AsyncMock(side_effect=[
            {
                "items": [{
                    "id": "nas-id",
                    "name": "NAS",
                    "status": "up",
                    "info": {"cpu": 5, "mp": 30, "dt": 42},
                }]
            },
            RuntimeError("stats forbidden"),
        ])

        result = await client.snapshot({"url": "http://beszel.local"})
        system = result["systems"][0]
        self.assertEqual(system["temperature"], 42)
        self.assertEqual(system["network_up_bps"], 0)
        self.assertEqual(system["network_down_bps"], 0)


if __name__ == "__main__":
    unittest.main()
