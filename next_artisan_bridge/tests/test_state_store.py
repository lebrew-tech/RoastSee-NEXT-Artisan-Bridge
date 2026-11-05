import tempfile
import unittest
from pathlib import Path

from next_artisan_bridge.state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def test_round_trips_latest_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "latest.json")
            reading = {"curve_agtron": 84.6, "cnt_record": 12}

            store.write(reading)

            self.assertEqual(store.read(), reading)

    def test_missing_state_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "missing.json")

            self.assertIsNone(store.read())


if __name__ == "__main__":
    unittest.main()
