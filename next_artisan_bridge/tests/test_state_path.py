import os
from pathlib import Path
import unittest
from unittest.mock import patch

from next_artisan_bridge.artisan_next_poll import default_state_path


class StatePathTests(unittest.TestCase):
    def test_mac_uses_application_support_independent_of_working_directory(self):
        with patch("sys.platform", "darwin"), patch.object(Path, "home", return_value=Path("/Users/test")):
            with patch.dict(os.environ, {"LOCALAPPDATA": "ignored-on-mac"}):
                self.assertEqual(
                    default_state_path(),
                    Path("/Users/test/Library/Application Support/RoastSeeNEXT/latest.json"),
                )

    def test_windows_state_path_is_unchanged(self):
        with patch("sys.platform", "win32"), patch.dict(os.environ, {"LOCALAPPDATA": "test-local"}):
            self.assertEqual(default_state_path(), Path("test-local/RoastSeeNEXT/latest.json"))
