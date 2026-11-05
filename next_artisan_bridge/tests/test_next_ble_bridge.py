import unittest
import tempfile
from pathlib import Path

from next_artisan_bridge.next_ble_bridge import (
    NextBleBridge,
    command_delay,
    live_commands,
    mock_live_once,
)
from next_artisan_bridge.state_store import StateStore


class BleBridgeTests(unittest.TestCase):
    def test_live_commands_are_empty_for_read_only_bridge(self):
        self.assertEqual(live_commands(), [])

    def test_auto_start_live_commands_enter_page_then_start(self):
        self.assertEqual(
            live_commands(auto_start_live=True),
            [b"roasting\r\n", b"start\r\n"],
        )

    def test_page_transition_gets_time_before_start(self):
        self.assertGreaterEqual(command_delay(b"roasting\r\n"), 1.0)

    def test_notification_writes_event_summary_into_artisan_state(self):
        payload = (
            b"Y_time:12, Y_agtron:83.5, Y_ROR:1.2, "
            b"FC_time:95, FC_agtron:72.0, FC_ROR:2.3, "
            b"SC_time:180, SC_agtron:60.5, SC_ROR:1.1, "
            b"D_time:240, D_agtron:55.0, D_ROR:0.4 \r\n\x00"
            + bytes([0xA5]) * 20
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "latest.json")
            live = {"curve_agtron": 84.6, "cnt_record": 12}
            store.write(live)
            bridge = NextBleBridge(store)

            bridge.on_notification(object(), bytearray(payload))

            self.assertEqual(bridge.last_event_summary["drop_time"], 240)
            saved = store.read()
            self.assertEqual(saved["curve_agtron"], 84.6)
            self.assertEqual(saved["fc_time"], 95)
            self.assertEqual(saved["fc_agtron"], 72.0)
            self.assertEqual(saved["fc_ror"], 2.3)
            self.assertEqual(saved["sc_time"], 180)
            self.assertEqual(saved["sc_agtron"], 60.5)
            self.assertEqual(saved["sc_ror"], 1.1)

    def test_new_roast_clears_previous_event_summary_from_artisan_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "latest.json")
            store.write(
                {
                    "curve_agtron": 55.0,
                    "fc_time": 95,
                    "fc_agtron": 72.0,
                    "fc_ror": 2.3,
                    "sc_time": 180,
                    "sc_agtron": 60.5,
                    "sc_ror": 1.1,
                }
            )
            bridge = NextBleBridge(store)

            bridge.on_notification(
                object(),
                bytearray(b"84.6,3,1.2,84.9,327,0,0\r\n\x00"),
            )

            saved = store.read()
            self.assertIsNotNone(saved)
            self.assertNotIn("fc_time", saved)
            self.assertNotIn("sc_time", saved)

    def test_notification_writes_legacy_ascii_live_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "latest.json")
            bridge = NextBleBridge(store)

            bridge.on_notification(
                object(),
                bytearray(b"84.6,3,1.2,84.9,327,95,1\r\n\x00"),
            )

            reading = store.read()
            self.assertIsNotNone(reading)
            self.assertEqual(reading["et"], -1)
            self.assertAlmostEqual(reading["curve_agtron"], 84.6, places=3)
            self.assertEqual(reading["distance"], 327)
            self.assertEqual(reading["cnt_record"], -1)

    def test_bridge_latches_yellow_time_and_emits_yellow_flag_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "latest.json")
            bridge = NextBleBridge(store)

            def send(time_yellow: int, flag_yellow: int) -> dict[str, float | int]:
                bridge.on_notification(
                    object(),
                    bytearray(f"84.6,3,1.2,84.9,327,{time_yellow},{flag_yellow}\r\n\x00", "ascii"),
                )
                reading = store.read()
                self.assertIsNotNone(reading)
                return reading

            self.assertEqual(send(0, 0)["time_yellow"], 0)
            first_yellow = send(95, 0)
            self.assertEqual(first_yellow["time_yellow"], 95)
            self.assertEqual(first_yellow["flag_yellow"], 1)
            following_yellow = send(95, 1)
            self.assertEqual(following_yellow["time_yellow"], 95)
            self.assertEqual(following_yellow["flag_yellow"], 0)
            self.assertEqual(send(0, 0)["time_yellow"], 0)

    def test_notification_writes_user_reported_binary_live_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "latest.json")
            bridge = NextBleBridge(store)

            bridge.on_notification(
                object(),
                bytearray(
                    bytes.fromhex(
                        "AA 55 14 4e 1b 03 42 00 00 00 00 00 00 00 00 00 "
                        "63 00 02 00 00 02 00 02 5e 53 42"
                    )
                ),
            )

            reading = store.read()
            self.assertIsNotNone(reading)
            self.assertAlmostEqual(reading["curve_agtron"], 32.77666, places=4)
            self.assertEqual(reading["distance"], 99)
            self.assertEqual(reading["time_yellow"], 2)
            self.assertEqual(reading["cnt_record"], 2)

    def test_unparsed_notification_is_available_in_debug_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "latest.json")
            bridge = NextBleBridge(store)

            with self.assertLogs("next_artisan_bridge", level="DEBUG") as captured:
                bridge.on_notification(object(), bytearray(b"\x99\x01"))

            self.assertIn("received BLE notification: 99 01", "\n".join(captured.output))

    def test_mock_live_once_writes_a_sample_that_artisan_can_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateStore(Path(tmp) / "latest.json")

            reading = mock_live_once(store)

            self.assertEqual(reading["et"], -1)
            self.assertEqual(reading["cnt_record"], -1)
            self.assertAlmostEqual(reading["curve_agtron"], 84.6, places=3)
            self.assertEqual(store.read(), reading)


if __name__ == "__main__":
    unittest.main()
