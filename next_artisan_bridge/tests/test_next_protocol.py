import unittest

from next_artisan_bridge.next_protocol import (
    LiveFrameParser,
    build_live_frame,
    format_artisan_sample,
    parse_event_summary,
)


READING = {
    "et": -1,
    "curve_agtron": 84.6,
    "voice": 3,
    "agtron_rate": 1.2,
    "weighted_median_mean_agtron": 84.9,
    "distance": 327,
    "time_yellow": 95,
    "flag_yellow": 1,
    "cnt_record": 12,
    "fc_time": 95,
    "fc_agtron": 72.0,
    "fc_ror": 2.3,
    "sc_time": 180,
    "sc_agtron": 60.5,
    "sc_ror": 1.1,
}


class LiveFrameParserTests(unittest.TestCase):
    def test_parses_current_ascii_live_frame_without_et(self):
        parser = LiveFrameParser()

        readings = parser.feed(b"84.6,3,1.2,84.9,327,95,1\r\n\x00")

        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0]["et"], -1)
        self.assertAlmostEqual(readings[0]["curve_agtron"], 84.6, places=3)
        self.assertEqual(readings[0]["voice"], 3)
        self.assertEqual(readings[0]["distance"], 327)
        self.assertEqual(readings[0]["time_yellow"], 95)
        self.assertEqual(readings[0]["flag_yellow"], 1)

    def test_parses_legacy_ascii_live_frame_with_nul_terminator(self):
        parser = LiveFrameParser()

        readings = parser.feed(b" 84.6, 3, 1.2, 84.9, 327, 95, 1\r\n\x00")

        self.assertEqual(len(readings), 1)
        self.assertAlmostEqual(readings[0]["curve_agtron"], 84.6, places=3)
        self.assertEqual(readings[0]["voice"], 3)
        self.assertAlmostEqual(readings[0]["agtron_rate"], 1.2, places=3)
        self.assertEqual(readings[0]["distance"], 327)
        self.assertEqual(readings[0]["time_yellow"], 95)
        self.assertEqual(readings[0]["flag_yellow"], 1)
        self.assertEqual(readings[0]["cnt_record"], -1)

    def test_parses_forward_compatible_ascii_live_frame_with_et(self):
        parser = LiveFrameParser()

        readings = parser.feed(b"45.5,84.6,3,1.2,84.9,327,95,1\r\n\x00")

        self.assertEqual(len(readings), 1)
        self.assertAlmostEqual(readings[0]["et"], 45.5, places=3)
        self.assertAlmostEqual(readings[0]["curve_agtron"], 84.6, places=3)

    def test_parses_voice_without_altering_its_value(self):
        parser = LiveFrameParser()

        readings = parser.feed(b"84.6,37,1.2,84.9,327,95,1\r\n\x00")

        self.assertEqual(readings[0]["voice"], 37)
        self.assertEqual(len(readings), 1)

    def test_reassembles_fragmented_ascii_live_frame(self):
        parser = LiveFrameParser()

        self.assertEqual(parser.feed(b"84.6,3,1.2,84."), [])
        readings = parser.feed(b"9,327,95,1\r\n\x00")

        self.assertEqual(len(readings), 1)
        self.assertAlmostEqual(readings[0]["weighted_median_mean_agtron"], 84.9, places=3)

    def test_parses_valid_binary_frame(self):
        parser = LiveFrameParser()

        readings = parser.feed(build_live_frame(READING))

        self.assertEqual(len(readings), 1)
        self.assertAlmostEqual(readings[0]["curve_agtron"], 84.6, places=4)
        self.assertEqual(readings[0]["voice"], 3)
        self.assertEqual(readings[0]["distance"], 327)
        self.assertEqual(readings[0]["cnt_record"], 12)

    def test_parses_binary_frame_reported_by_bluetooth_assistant(self):
        parser = LiveFrameParser()
        frame = bytes.fromhex(
            "AA 55 14 11 D5 70 42 00 00 00 00 00 85 ED 08 42 "
            "EE 00 02 00 00 06 00 B6 D8 53 42"
        )

        readings = parser.feed(frame)

        self.assertEqual(len(readings), 1)
        self.assertAlmostEqual(readings[0]["curve_agtron"], 60.20807, places=4)
        self.assertEqual(readings[0]["voice"], 0)
        self.assertAlmostEqual(readings[0]["weighted_median_mean_agtron"], 34.23195, places=4)
        self.assertEqual(readings[0]["distance"], 238)
        self.assertEqual(readings[0]["time_yellow"], 2)
        self.assertEqual(readings[0]["flag_yellow"], 0)
        self.assertEqual(readings[0]["cnt_record"], 6)

    def test_discards_noise_before_binary_frame_even_when_payload_contains_nul(self):
        parser = LiveFrameParser()
        frame = bytes.fromhex(
            "AA 55 14 AF 1D AB 42 00 00 F8 18 3F AB AA A1 3C "
            "11 00 13 00 00 01 00 54 23 53 42"
        )

        self.assertEqual(parser.feed(bytes(range(15))), [])
        readings = parser.feed(frame)

        self.assertEqual(len(readings), 1)
        self.assertAlmostEqual(readings[0]["curve_agtron"], 85.558, places=3)
        self.assertEqual(readings[0]["distance"], 17)
        self.assertEqual(readings[0]["time_yellow"], 19)

    def test_reassembles_fragmented_frame(self):
        parser = LiveFrameParser()
        frame = build_live_frame(READING)

        self.assertEqual(parser.feed(frame[:7]), [])
        self.assertEqual(parser.feed(frame[7:19]), [])
        readings = parser.feed(frame[19:])

        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0]["time_yellow"], 95)

    def test_rejects_bad_crc_without_returning_a_reading(self):
        parser = LiveFrameParser()
        frame = bytearray(build_live_frame(READING))
        frame[8] ^= 0x01

        self.assertEqual(parser.feed(bytes(frame)), [])


class ArtisanFormatterTests(unittest.TestCase):
    def test_formats_live_and_fc_sc_fields_for_artisan(self):
        output = format_artisan_sample(READING)

        self.assertEqual(
            output,
            "-1.000,-1,84.600,3,1.200,84.900,327,95,1,-1,95,72.000,2.300,180,60.500,1.100\n",
        )

    def test_formats_preserves_voice_value(self):
        reading = dict(READING)
        reading["voice"] = 42
        output = format_artisan_sample(reading)

        self.assertEqual(
            output,
            "-1.000,-1,84.600,42,1.200,84.900,327,95,1,-1,95,72.000,2.300,180,60.500,1.100\n",
        )

    def test_formats_missing_reading_as_sixteen_placeholders(self):
        output = format_artisan_sample(None)

        self.assertEqual(output, "-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1\n")


class EventSummaryParserTests(unittest.TestCase):
    def test_parses_ascii_event_summary_and_ignores_a5_padding(self):
        payload = (
            b"Y_time:12, Y_agtron:83.5, Y_ROR:1.2, "
            b"FC_time:95, FC_agtron:72.0, FC_ROR:2.3, "
            b"SC_time:180, SC_agtron:60.5, SC_ROR:1.1, "
            b"D_time:240, D_agtron:55.0, D_ROR:0.4 \r\n\x00\x00"
            + bytes([0xA5]) * 40
        )

        event = parse_event_summary(payload)

        self.assertEqual(
            event,
            {
                "yellow_time": 12,
                "yellow_agtron": 83.5,
                "yellow_ror": 1.2,
                "fc_time": 95,
                "fc_agtron": 72.0,
                "fc_ror": 2.3,
                "sc_time": 180,
                "sc_agtron": 60.5,
                "sc_ror": 1.1,
                "drop_time": 240,
                "drop_agtron": 55.0,
                "drop_ror": 0.4,
            },
        )

    def test_rejects_other_ascii_notifications(self):
        self.assertIsNone(parse_event_summary(b"Agtron: 55.0\r\n"))


if __name__ == "__main__":
    unittest.main()
