"""RoastSee NEXT live BLE frame parsing and Artisan sample formatting."""

from __future__ import annotations

import math
import re
import struct
from typing import Final

SERVICE_UUID: Final[str] = "000000bb-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID: Final[str] = "0000bb01-0000-1000-8000-00805f9b34fb"
FRAME_HEADER: Final[bytes] = b"\xAA\x55"
FRAME_TAIL: Final[bytes] = b"\x53\x42"
PAYLOAD_FORMAT: Final[str] = "<fBffHHBH"
PAYLOAD_SIZE: Final[int] = struct.calcsize(PAYLOAD_FORMAT)

_EVENT_FIELDS: Final[dict[str, str]] = {
    "Y_time": "yellow_time",
    "Y_agtron": "yellow_agtron",
    "Y_ROR": "yellow_ror",
    "FC_time": "fc_time",
    "FC_agtron": "fc_agtron",
    "FC_ROR": "fc_ror",
    "SC_time": "sc_time",
    "SC_agtron": "sc_agtron",
    "SC_ROR": "sc_ror",
    "D_time": "drop_time",
    "D_agtron": "drop_agtron",
    "D_ROR": "drop_ror",
}
_EVENT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<key>Y_time|Y_agtron|Y_ROR|FC_time|FC_agtron|FC_ROR|"
    r"SC_time|SC_agtron|SC_ROR|D_time|D_agtron|D_ROR)\s*:\s*"
    r"(?P<value>-?\d+(?:\.\d+)?)"
)
_ASCII_NUMBER: Final[str] = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_ASCII_LIVE_PATTERN_8: Final[re.Pattern[str]] = re.compile(
    rf"^\s*({_ASCII_NUMBER})\s*,\s*({_ASCII_NUMBER})\s*,\s*"
    rf"({_ASCII_NUMBER})\s*,\s*({_ASCII_NUMBER})\s*,\s*"
    rf"({_ASCII_NUMBER})\s*,\s*({_ASCII_NUMBER})\s*,\s*"
    rf"({_ASCII_NUMBER})\s*,\s*({_ASCII_NUMBER})\s*$"
)
_ASCII_LIVE_PATTERN_7: Final[re.Pattern[str]] = re.compile(
    rf"^\s*({_ASCII_NUMBER})\s*,\s*({_ASCII_NUMBER})\s*,\s*"
    rf"({_ASCII_NUMBER})\s*,\s*({_ASCII_NUMBER})\s*,\s*"
    rf"({_ASCII_NUMBER})\s*,\s*({_ASCII_NUMBER})\s*,\s*"
    rf"({_ASCII_NUMBER})\s*$"
)


def crc16_modbus(data: bytes) -> int:
    """Calculate CRC-16/Modbus using the NEXT firmware parameters."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 0x0001 else crc >> 1
    return crc & 0xFFFF


def parse_event_summary(data: bytes | bytearray | str) -> dict[str, float | int] | None:
    """Parse the ASCII roast-event summary sent on BB01 after a roast.

    The firmware sends a fixed-size buffer.  Only the text before the first
    NUL or 0xA5 padding byte is meaningful, so padding is deliberately ignored.
    """
    if isinstance(data, str):
        text = data.split("\x00", 1)[0]
    else:
        raw = bytes(data)
        raw = raw.split(b"\x00", 1)[0]
        raw = raw.split(b"\xA5", 1)[0]
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError:
            return None

    if not text.lstrip().startswith("Y_time:"):
        return None

    values: dict[str, float | int] = {}
    for match in _EVENT_PATTERN.finditer(text):
        source_key = match.group("key")
        target_key = _EVENT_FIELDS[source_key]
        number = float(match.group("value"))
        values[target_key] = int(number) if number.is_integer() else number

    if set(values) != set(_EVENT_FIELDS.values()):
        return None
    return values


def parse_ascii_live_frame(data: bytes | bytearray | str) -> dict[str, float | int] | None:
    """Parse current seven-value or forward-compatible eight-value notifications."""
    if isinstance(data, str):
        text = data.split("\x00", 1)[0]
    else:
        raw = bytes(data).split(b"\x00", 1)[0]
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError:
            return None

    match = _ASCII_LIVE_PATTERN_8.fullmatch(text)
    frame_version = 8
    if match is None:
        match = _ASCII_LIVE_PATTERN_7.fullmatch(text)
        frame_version = 7
    if match is None:
        return None

    numbers = [float(value) for value in match.groups()]
    if not all(math.isfinite(value) for value in numbers):
        return None
    integer_indexes = (2, 5, 6, 7) if frame_version == 8 else (1, 4, 5, 6)
    if any(numbers[index] != int(numbers[index]) for index in integer_indexes):
        return None

    if frame_version == 8:
        et = numbers[0]
        curve_agtron = numbers[1]
        voice = numbers[2]
        agtron_rate = numbers[3]
        filtered = numbers[4]
        distance = numbers[5]
        time_yellow = numbers[6]
        flag_yellow = numbers[7]
    else:
        et = -1
        curve_agtron = numbers[0]
        voice = numbers[1]
        agtron_rate = numbers[2]
        filtered = numbers[3]
        distance = numbers[4]
        time_yellow = numbers[5]
        flag_yellow = numbers[6]

    return {
        "et": et,
        "curve_agtron": curve_agtron,
        # Keep NEXT acoustic samples unchanged (no bridge-side smoothing/filtering).
        "voice": int(voice),
        "agtron_rate": agtron_rate,
        "weighted_median_mean_agtron": filtered,
        "distance": int(distance),
        "time_yellow": int(time_yellow),
        "flag_yellow": int(flag_yellow),
        # Record Counter is intentionally unused by the current interface.
        "cnt_record": -1,
    }


def _payload_from_reading(reading: dict[str, float | int]) -> bytes:
    return struct.pack(
        PAYLOAD_FORMAT,
        float(reading["curve_agtron"]),
        int(reading["voice"]),
        float(reading["agtron_rate"]),
        float(reading["weighted_median_mean_agtron"]),
        int(reading["distance"]),
        int(reading["time_yellow"]),
        int(reading["flag_yellow"]),
        int(reading["cnt_record"]),
    )


def build_live_frame(reading: dict[str, float | int]) -> bytes:
    """Build a valid legacy binary NEXT live frame for tests."""
    payload = _payload_from_reading(reading)
    body = bytes((len(payload),)) + payload
    crc = crc16_modbus(body)
    return FRAME_HEADER + body + struct.pack("<H", crc) + FRAME_TAIL


def _decode_payload(payload: bytes) -> dict[str, float | int]:
    values = struct.unpack(PAYLOAD_FORMAT, payload)
    return {
        # The legacy binary payload has no ET field.
        "et": -1,
        "curve_agtron": values[0],
        "voice": values[1],
        "agtron_rate": values[2],
        "weighted_median_mean_agtron": values[3],
        "distance": values[4],
        "time_yellow": values[5],
        "flag_yellow": values[6],
        "cnt_record": values[7],
    }


class LiveFrameParser:
    """Incrementally parse current ASCII and legacy binary NEXT live frames."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[dict[str, float | int]]:
        self._buffer.extend(chunk)
        readings: list[dict[str, float | int]] = []

        while True:
            # NUL is the terminator used by the current firmware.  Discard it
            # before looking for either a binary header or an ASCII line.
            while self._buffer[:1] in (b"\x00", b"\r", b"\n"):
                del self._buffer[:1]
            if not self._buffer:
                break

            header_at = self._buffer.find(FRAME_HEADER)
            line_end = self._buffer.find(b"\r\n")
            nul_end = self._buffer.find(b"\x00")

            if header_at != 0 and line_end >= 0 and (header_at < 0 or line_end < header_at):
                raw_line = bytes(self._buffer[:line_end])
                del self._buffer[: line_end + 2]
                reading = parse_ascii_live_frame(raw_line)
                if reading is not None:
                    readings.append(reading)
                continue

            if (
                header_at != 0
                and nul_end >= 0
                and (header_at < 0 or nul_end < header_at)
                and (line_end < 0 or nul_end < line_end)
            ):
                raw_line = bytes(self._buffer[:nul_end])
                del self._buffer[: nul_end + 1]
                reading = parse_ascii_live_frame(raw_line)
                if reading is not None:
                    readings.append(reading)
                continue

            if header_at < 0:
                # Keep a possible first header byte or an incomplete ASCII line.
                if self._buffer[-1:] == FRAME_HEADER[:1]:
                    del self._buffer[:-1]
                elif len(self._buffer) > 512:
                    del self._buffer[:-512]
                break
            if header_at:
                del self._buffer[:header_at]
            if len(self._buffer) < 3:
                break

            payload_len = self._buffer[2]
            frame_len = 2 + 1 + payload_len + 2 + 2
            if len(self._buffer) < frame_len:
                break

            frame = bytes(self._buffer[:frame_len])
            payload_end = 3 + payload_len
            received_crc = frame[payload_end] | (frame[payload_end + 1] << 8)
            valid = (
                frame[-2:] == FRAME_TAIL
                and payload_len == PAYLOAD_SIZE
                and crc16_modbus(frame[2:payload_end]) == received_crc
            )
            del self._buffer[:frame_len]
            if valid:
                readings.append(_decode_payload(frame[3:payload_end]))

        return readings


def format_artisan_sample(reading: dict[str, float | int] | None) -> str:
    """Format the main placeholders plus NEXT values for Artisan Program slots."""
    if reading is None:
        return "-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1\n"
    return (
        "{et:.3f},-1,{curve:.3f},{voice},{rate:.3f},{filtered:.3f},"
        "{distance},{time_yellow},{flag_yellow},-1,"
        "{fc_time},{fc_agtron:.3f},{fc_ror:.3f},"
        "{sc_time},{sc_agtron:.3f},{sc_ror:.3f}\n"
    ).format(
        et=float(reading.get("et", -1)),
        curve=float(reading.get("curve_agtron", -1)),
        voice=int(reading.get("voice", -1)),
        rate=float(reading.get("agtron_rate", -1)),
        filtered=float(reading.get("weighted_median_mean_agtron", -1)),
        distance=int(reading.get("distance", -1)),
        time_yellow=int(reading.get("time_yellow", -1)),
        flag_yellow=int(reading.get("flag_yellow", -1)),
        fc_time=int(reading.get("fc_time", -1)),
        fc_agtron=float(reading.get("fc_agtron", -1)),
        fc_ror=float(reading.get("fc_ror", -1)),
        sc_time=int(reading.get("sc_time", -1)),
        sc_agtron=float(reading.get("sc_agtron", -1)),
        sc_ror=float(reading.get("sc_ror", -1)),
    )
