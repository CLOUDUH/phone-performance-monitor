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

    def test_terminal_secrets_are_preserved_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(directory)
            store.update({"terminal": {"host": "192.168.1.83", "password": "ssh-secret", "private_key": "key-data", "key_passphrase": "key-secret"}})
            store.update({"terminal": {"password": "", "private_key": "", "key_passphrase": ""}})
            stored = store.load()["terminal"]
            self.assertEqual(stored["password"], "ssh-secret")
            self.assertEqual(stored["private_key"], "key-data")
            public = store.public()["terminal"]
            self.assertEqual(public["password"], "")
            self.assertEqual(public["private_key"], "")
            self.assertTrue(public["password_set"])
            self.assertTrue(public["private_key_set"])


if __name__ == "__main__":
    unittest.main()
