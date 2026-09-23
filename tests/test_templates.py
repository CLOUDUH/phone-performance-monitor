import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TemplateTests(unittest.TestCase):
    def test_builtin_templates_have_unique_widgets_and_valid_grid(self):
        for name in ("landscape", "portrait"):
            data = json.loads((ROOT / "templates" / f"{name}.json").read_text("utf-8"))
            self.assertEqual(data["schemaVersion"], 1)
            ids = [widget["id"] for widget in data["widgets"]]
            self.assertEqual(len(ids), len(set(ids)))
            for widget in data["widgets"]:
                self.assertGreaterEqual(widget["x"], 1)
                self.assertLessEqual(widget["x"] + widget["w"] - 1, data["columns"])
                self.assertIn(widget["type"], {"wan", "systems", "status", "clock"})


if __name__ == "__main__":
    unittest.main()

