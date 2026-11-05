import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ArtisanPollerTests(unittest.TestCase):
    def test_outputs_sixteen_fields_from_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "latest.json"
            state_path.write_text(
                json.dumps(
                    {
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
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "next_artisan_bridge.artisan_next_poll",
                    "--state",
                    str(state_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout,
                "-1.000,-1,84.600,3,1.200,84.900,327,95,1,-1,95,72.000,2.300,180,60.500,1.100\n",
            )

    def test_outputs_placeholders_when_state_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "next_artisan_bridge.artisan_next_poll",
                    "--state",
                    str(Path(tmp) / "missing.json"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1\n")


if __name__ == "__main__":
    unittest.main()
