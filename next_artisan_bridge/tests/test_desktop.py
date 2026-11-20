import sys
import tempfile
import unittest
from pathlib import Path

if sys.platform == "win32":
    import tkinter as tk
    from unittest.mock import patch

    from next_artisan_bridge.desktop import BridgeWindow, SYSTEM_LANGUAGE, load_language


@unittest.skipUnless(sys.platform == "win32", "Windows desktop preferences")
class DesktopLanguageTests(unittest.TestCase):
    def test_saved_language_overrides_the_system_language(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "desktop-language.txt"
            for language in ("en", "zh-CN"):
                path.write_text(language, encoding="ascii")
                self.assertEqual(load_language(path), language)

    def test_unsupported_saved_language_uses_the_system_language(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "desktop-language.txt"
            path.write_text("unknown", encoding="ascii")

            self.assertEqual(load_language(path), SYSTEM_LANGUAGE)

    def test_picker_switches_the_existing_window_and_saves_the_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            root = tk.Tk()
            root.withdraw()
            try:
                with patch("next_artisan_bridge.desktop.default_state_path", return_value=folder / "latest.json"):
                    app = BridgeWindow(root, folder / "artisan_next_poll.exe")
                self.assertEqual(app.language_picker.cget("values"), ("简体中文", "English"))
                app.auto_start.set(True)
                for index, code, expected in (
                    (1, "en", "Connect NEXT"),
                    (0, "zh-CN", "连接 NEXT"),
                ):
                    app.language_picker.current(index)
                    app.change_language()
                    self.assertEqual(app.connect_button.cget("text"), expected)
                    self.assertEqual(load_language(folder / "desktop-language.txt"), code)
                    self.assertTrue(app.auto_start.get())
            finally:
                root.destroy()
