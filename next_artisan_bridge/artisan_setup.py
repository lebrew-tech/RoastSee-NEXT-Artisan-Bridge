"""Set up the Artisan Program input and restore its previous Windows settings."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import struct
import tempfile
import winreg

ARTISAN_KEY = r"Software\artisan-scope\Artisan"
PROGRAM_GROUPS = {"48": ("NEXT Agtron", "NEXT Voice"), "49": ("NEXT Rate", "NEXT Variation")}
EXTRA_FIELDS = {
    "extraname1": "Extra 1",
    "extraname2": "Extra 2",
    "extraLCDvisibility1": "false",
    "extraLCDvisibility2": "false",
    "extraCurveVisibility1": "true",
    "extraCurveVisibility2": "true",
}
DEVICE_ID = r"Device\id"
PROGRAM = "externalprogram"
OUTPUT = "externaloutprogramFlag"
EXTRA_DEVICES = r"ExtraDev\extradevices"
SETTINGS = (DEVICE_ID, PROGRAM, OUTPUT, EXTRA_DEVICES, *(rf"ExtraDev\{field}" for field in EXTRA_FIELDS))


def _read_settings(registry_key):
    values = {}
    for address in SETTINGS:
        section, _, name = address.rpartition("\\")
        key = rf"{registry_key}\{section}" if section else registry_key
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                values[address] = winreg.QueryValueEx(handle, name)
        except FileNotFoundError:
            values[address] = None
    return values


def _set_setting(registry_key, address, entry):
    section, _, name = address.rpartition("\\")
    key = rf"{registry_key}\{section}" if section else registry_key
    if entry is None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as handle:
                winreg.DeleteValue(handle, name)
        except FileNotFoundError:
            pass
    else:
        value, kind = entry
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
            winreg.SetValueEx(handle, name, 0, kind, value)


def _apply(registry_key, before, changes):
    written = []
    try:
        for address, entry in changes.items():
            _set_setting(registry_key, address, entry)
            written.append(address)
    except OSError:
        for address in reversed(written):
            _set_setting(registry_key, address, before[address])
        raise


def _strings(entry):
    if entry is None:
        return []
    value, kind = entry
    if kind == winreg.REG_MULTI_SZ:
        return [text[1:] if text.startswith("@@") else text for text in value]
    # Qt stores lists with empty strings as a Qt 4.0 streamed QVariant.
    if kind == winreg.REG_BINARY:
        try:
            raw = value.decode("utf-16-le").encode("latin-1")
            if raw.startswith(b"@Variant(") and raw.endswith(b")"):
                stream = io.BytesIO(raw[9:-1])
                list_type, count = struct.unpack(">II", stream.read(8))
                if list_type in (9, 11) and count <= 10:
                    entries = []
                    for _ in range(count):
                        if list_type == 9 and stream.read(4) != struct.pack(">I", 10):
                            raise ValueError("Expected a Qt string")
                        length, = struct.unpack(">I", stream.read(4))
                        text = b"" if length == 0xFFFFFFFF else stream.read(length)
                        if length != 0xFFFFFFFF and len(text) != length:
                            raise ValueError("Incomplete Qt string")
                        entries.append(text.decode("utf-16-be"))
                    if not stream.read(1):
                        return entries
        except (struct.error, ValueError):
            pass
    raise ValueError("Artisan has an unsupported format for one of its Extra Devices settings.")


def _string_list(values):
    if all(value and "\x00" not in value for value in values):
        return [f"@{value}" if value.startswith("@") else value for value in values], winreg.REG_MULTI_SZ
    encoded = bytearray(struct.pack(">II", 11, len(values)))
    for value in values:
        string = value.encode("utf-16-be")
        encoded.extend(struct.pack(">I", len(string)))
        encoded.extend(string)
    variant = b"@Variant(" + encoded + b")"
    return variant.decode("latin-1").encode("utf-16-le"), winreg.REG_BINARY


def poll_command(poller: Path, state: Path) -> str:
    if not poller.is_file():
        raise FileNotFoundError("Extract the full bridge ZIP so artisan_next_poll.exe is available.")
    executable, state_path = poller.resolve().as_posix(), state.resolve().as_posix()
    # Artisan's Windows Program input passes this command through cmd.exe.
    if any(character in executable or character in state_path for character in '%!"\r\n'):
        raise ValueError('Artisan needs paths without percent signs, exclamation marks, or quotes.')
    return f'"{executable}" --state "{state_path}"'


def _changes(before, command):
    changes = {}
    if before[DEVICE_ID] is None or str(before[DEVICE_ID][0]) != "27":
        changes[DEVICE_ID] = (27, winreg.REG_DWORD)
    if before[PROGRAM] != (command, winreg.REG_SZ):
        changes[PROGRAM] = (command, winreg.REG_SZ)
    if before[OUTPUT] is not None and str(before[OUTPUT][0]).lower() not in ("false", "0"):
        changes[OUTPUT] = ("false", winreg.REG_SZ)

    current_devices = _strings(before[EXTRA_DEVICES])
    devices = current_devices + [group for group in PROGRAM_GROUPS if group not in current_devices]
    if len(devices) > 10:
        raise ValueError("Artisan supports up to ten Extra Devices. Free a slot for each missing Program group.")
    if devices != current_devices:
        changes[EXTRA_DEVICES] = _string_list(devices)

    for field, default in EXTRA_FIELDS.items():
        address = rf"ExtraDev\{field}"
        current = _strings(before[address])
        values = current + [default] * max(0, len(devices) - len(current))
        for group, labels in PROGRAM_GROUPS.items():
            index = devices.index(group)
            if field.startswith("extraname"):
                if index >= len(current_devices) or not values[index] or values[index] == default:
                    values[index] = labels[int(field[-1]) - 1]
            else:
                values[index] = "true"
        if values != current:
            changes[address] = _string_list(values)
    return changes


def _save_backup(backup, before):
    values = {
        key: None if entry is None else [entry[1], entry[0].hex() if isinstance(entry[0], bytes) else entry[0]]
        for key, entry in before.items()
    }
    backup.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=backup.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(values, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        _load_backup(temporary)
        os.replace(temporary, backup)
    finally:
        temporary.unlink(missing_ok=True)


def _load_backup(backup):
    values = json.loads(backup.read_text(encoding="utf-8"))
    if not isinstance(values, dict) or values.keys() != set(SETTINGS):
        raise ValueError("The Artisan settings backup has an invalid format.")
    before = {}
    for address, entry in values.items():
        if entry is None:
            before[address] = None
            continue
        if not isinstance(entry, list) or len(entry) != 2 or type(entry[0]) is not int:
            raise ValueError("The Artisan settings backup has an invalid registry entry.")
        kind, value = entry
        if kind in (winreg.REG_BINARY, winreg.REG_NONE) and isinstance(value, str):
            value = bytes.fromhex(value)
        elif kind in (winreg.REG_DWORD, winreg.REG_QWORD) and type(value) is int and 0 <= value < 2 ** (32 if kind == winreg.REG_DWORD else 64):
            pass
        elif kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and isinstance(value, str) and "\x00" not in value:
            pass
        elif kind == winreg.REG_MULTI_SZ and isinstance(value, list) and all(isinstance(item, str) and "\x00" not in item for item in value):
            pass
        else:
            raise ValueError("The Artisan settings backup has an invalid registry value.")
        before[address] = (value, kind)
    return before


def artisan_configured(poller: Path, state: Path) -> bool:
    return not _changes(_read_settings(ARTISAN_KEY), poll_command(poller, state))


def configure_artisan(poller: Path, state: Path, backup: Path, *, registry_key=ARTISAN_KEY) -> bool:
    before = _read_settings(registry_key)
    changes = _changes(before, poll_command(poller, state))
    if not changes:
        return False
    if backup.exists():
        _load_backup(backup)
    else:
        _save_backup(backup, before)
    _apply(registry_key, before, changes)
    return True


def restore_artisan(backup: Path, *, registry_key=ARTISAN_KEY) -> None:
    original = _load_backup(backup)
    _apply(registry_key, _read_settings(registry_key), original)
    backup.unlink()
