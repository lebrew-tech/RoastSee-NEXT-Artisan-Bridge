import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

if sys.platform == "win32":
    import winreg

    from next_artisan_bridge.artisan_setup import configure_artisan, restore_artisan


@unittest.skipUnless(sys.platform == "win32", "Artisan uses the Windows registry")
class ArtisanSetupTests(unittest.TestCase):
    def setUp(self):
        self.registry = rf"Software\RoastSeeNEXT-Test-{uuid4()}"
        self.addCleanup(self.remove_test_key)
        temporary = tempfile.TemporaryDirectory(prefix="NEXT 桥接 ")
        self.addCleanup(temporary.cleanup)
        work = Path(temporary.name)
        self.backup = work / "backup.json"
        self.state = work / "desktop-latest.json"
        self.poller = work / "artisan_next_poll.exe"
        self.poller.touch()

    def remove_test_key(self):
        for subkey in (r"\Device", r"\ExtraDev", ""):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.registry + subkey)
            except FileNotFoundError:
                pass

    def write(self, address, data, kind):
        section, _, name = address.rpartition("\\")
        key = self.registry + (rf"\{section}" if section else "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
            winreg.SetValueEx(handle, name, 0, kind, data)

    def read(self, address):
        section, _, name = address.rpartition("\\")
        key = self.registry + (rf"\{section}" if section else "")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            return winreg.QueryValueEx(handle, name)[0]

    def configure(self):
        return configure_artisan(self.poller, self.state, self.backup, registry_key=self.registry)

    def test_configures_prog_and_appends_channels_to_existing_devices(self):
        self.write(r"Device\id", 29, winreg.REG_DWORD)
        self.write("externaloutprogramFlag", "true", winreg.REG_SZ)
        self.write(r"ExtraDev\extradevices", ["29", "48"], winreg.REG_MULTI_SZ)
        self.write(r"ExtraDev\extraname1", ["Drum", "Agtron"], winreg.REG_MULTI_SZ)
        self.write(r"ExtraDev\extraLCDvisibility1", ["false", "false"], winreg.REG_MULTI_SZ)

        self.assertTrue(self.configure())

        self.assertEqual(self.read(r"Device\id"), 27)
        self.assertEqual(self.read("externalprogram"), f'"{self.poller.as_posix()}" --state "{self.state.as_posix()}"')
        self.assertEqual(self.read("externaloutprogramFlag"), "false")
        self.assertEqual(self.read(r"ExtraDev\extradevices"), ["29", "48", "49"])
        self.assertEqual(self.read(r"ExtraDev\extraname1"), ["Drum", "Agtron", "NEXT Rate"])
        self.assertEqual(self.read(r"ExtraDev\extraLCDvisibility1")[:3], ["false", "true", "true"])
        self.assertFalse(self.configure())

    def test_restore_removes_added_values_and_restores_the_first_configuration(self):
        self.write(r"Device\id", 29, winreg.REG_DWORD)
        self.write("externalprogram", '"C:/Users/Roaster/Thermometer.exe"', winreg.REG_SZ)
        self.write("Mode", "F", winreg.REG_SZ)
        self.configure()
        self.write("externalprogram", "other.exe", winreg.REG_SZ)
        self.configure()

        restore_artisan(self.backup, registry_key=self.registry)

        self.assertEqual(self.read(r"Device\id"), 29)
        self.assertEqual(self.read("externalprogram"), '"C:/Users/Roaster/Thermometer.exe"')
        self.assertEqual(self.read("Mode"), "F")
        with self.assertRaises(FileNotFoundError):
            self.read(r"ExtraDev\extradevices")
        self.assertFalse(self.backup.exists())

    def test_leaves_full_extra_devices_untouched(self):
        self.write(r"Device\id", 29, winreg.REG_DWORD)
        self.write(r"ExtraDev\extradevices", ["29"] * 10, winreg.REG_MULTI_SZ)

        with self.assertRaises(ValueError):
            self.configure()

        self.assertEqual(self.read(r"Device\id"), 29)
        self.assertFalse(self.backup.exists())

    def test_rejects_cmd_expansion_in_a_bundle_path(self):
        self.poller = self.poller.with_name("%TEMP%.exe")
        self.poller.touch()

        with self.assertRaises(ValueError):
            self.configure()

        self.assertFalse(self.backup.exists())

    def test_setup_and_restore_handle_qt_list_with_empty_device_name(self):
        self.write(r"ExtraDev\extradevices", ["29"], winreg.REG_MULTI_SZ)
        original = "@Variant".encode("utf-16-le") + bytes.fromhex(
            "2800 0000 0000 0000 0900 0000 0000 0000 0100 0000 0000 0000 0a00 0000 0000 0000 0000 2900"
        )
        self.write(r"ExtraDev\extraname1", original, winreg.REG_BINARY)

        self.configure()

        result = self.read(r"ExtraDev\extraname1")
        serialized = result.decode("utf-16-le").encode("latin-1")
        self.assertEqual(serialized[:21], b"@Variant(" + bytes.fromhex("0000000b 00000003 00000000"))
        self.assertFalse(self.configure())
        restore_artisan(self.backup, registry_key=self.registry)
        self.assertEqual(self.read(r"ExtraDev\extraname1"), original)

    def test_failed_registry_write_rolls_back_preceding_changes(self):
        self.write(r"Device\id", 29, winreg.REG_DWORD)
        set_value = winreg.SetValueEx

        def deny_external_program(handle, name, reserved, kind, data):
            if name == "externalprogram":
                raise PermissionError("test write failure")
            return set_value(handle, name, reserved, kind, data)

        with patch.object(winreg, "SetValueEx", deny_external_program), self.assertRaises(PermissionError):
            self.configure()

        self.assertEqual(self.read(r"Device\id"), 29)
        self.assertTrue(self.backup.exists())
