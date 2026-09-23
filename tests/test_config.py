import tempfile
import unittest

from app.config import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    def test_secrets_are_preserved_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            store.update({"beszel": {"password": "secret"}, "snmp": {"community": "private"}})
            store.update({"beszel": {"password": ""}, "snmp": {"community": ""}})
            self.assertEqual(store.load()["beszel"]["password"], "secret")
            self.assertEqual(store.load()["snmp"]["community"], "private")
            public = store.public()
            self.assertEqual(public["beszel"]["password"], "")
            self.assertTrue(public["beszel"]["password_set"])
            self.assertEqual(public["snmp"]["community"], "")
            self.assertTrue(public["snmp"]["community_set"])

    def test_pin_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            store.update({"admin_pin": "2468"})
            self.assertTrue(store.verify_pin("2468"))
            self.assertFalse(store.verify_pin("1357"))

    def test_weather_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            store.update({"weather": {"location": "广州", "latitude": 23.1291, "longitude": 113.2644}})
            weather = store.load()["weather"]
            self.assertEqual(weather["location"], "广州")
            self.assertEqual(weather["latitude"], 23.1291)
            self.assertEqual(weather["longitude"], 113.2644)


if __name__ == "__main__":
    unittest.main()
