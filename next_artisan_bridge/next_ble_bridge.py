"""Long-running RoastSee NEXT BLE client and state writer."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from .next_protocol import CHARACTERISTIC_UUID, SERVICE_UUID, LiveFrameParser, parse_event_summary
from .state_store import StateStore

LOG = logging.getLogger("next_artisan_bridge")


def live_commands(auto_start_live: bool = False) -> list[bytes]:
    """Return optional commands for entering and starting live measurement.

    The bridge remains read-only by default.  The explicit auto-start mode
    first changes the NEXT screen, then starts its live measurement switch.
    """
    if not auto_start_live:
        return []
    return [b"roasting\r\n", b"start\r\n"]


def command_delay(command: bytes) -> float:
    """Return the minimum wait after a command before sending the next one."""
    # The firmware changes the LVGL screen in response to ``roasting`` and
    # accepts ``start`` only after flag_RoastingLiveEnter becomes true.
    return 1.5 if command == b"roasting\r\n" else 0.2


def mock_live_once(store: StateStore) -> dict[str, float | int]:
    """Inject one protocol-valid live frame for an offline bridge test."""
    parsed = LiveFrameParser().feed(b"84.6,3,1.2,84.9,327,95,1\r\n\x00")
    if len(parsed) != 1:
        raise RuntimeError("mock live frame failed protocol parsing")
    store.write(parsed[0])
    LOG.info("mock live frame written: %s", parsed[0])
    return parsed[0]


class NextBleBridge:
    def __init__(
        self,
        store: StateStore,
        scan_timeout: float = 10.0,
        auto_start_live: bool = False,
    ) -> None:
        self.store = store
        self.scan_timeout = scan_timeout
        self.auto_start_live = auto_start_live
        self.parser = LiveFrameParser()
        self.last_event_summary: dict[str, float | int] | None = None
        self._yellow_time_latched: int | None = None
        self._yellow_flag_pending = False

    def _normalize_yellow_fields(self, reading: dict[str, float | int]) -> dict[str, float | int]:
        """Latch the first reported yellow time and expose a one-shot flag."""
        raw_time = int(reading["time_yellow"])

        if raw_time <= 0:
            # NEXT resets this field at the start of a new roast.
            self._yellow_time_latched = None
            self._yellow_flag_pending = False
        elif self._yellow_time_latched is None:
            self._yellow_time_latched = raw_time
            self._yellow_flag_pending = True

        reading["time_yellow"] = self._yellow_time_latched or 0
        reading["flag_yellow"] = int(self._yellow_flag_pending)
        self._yellow_flag_pending = False
        return reading

    def on_notification(self, _sender: object, data: bytearray) -> None:
        raw = bytes(data)
        LOG.debug("received BLE notification: %s", raw.hex(" "))
        event_summary = parse_event_summary(data)
        if event_summary is not None:
            self.last_event_summary = event_summary
            latest_reading = self.store.read() or {}
            latest_reading.update(event_summary)
            try:
                self.store.write(latest_reading)
            except OSError:
                LOG.exception("failed to write event summary to %s", self.store.path)
            LOG.info(
                "received roast event summary: drop_time=%s drop_agtron=%.3f",
                event_summary["drop_time"],
                event_summary["drop_agtron"],
            )
            return

        readings = self.parser.feed(raw)
        LOG.debug("accepted %d live frame(s) from notification", len(readings))
        for reading in readings:
            reading = self._normalize_yellow_fields(reading)
            try:
                self.store.write(reading)
            except OSError:
                LOG.exception("failed to write latest state to %s", self.store.path)
                continue
            LOG.info(
                "received live sample: agtron=%.3f distance=%s",
                reading["curve_agtron"],
                reading["distance"],
            )

    async def _find_device(self):
        from bleak import BleakScanner

        LOG.info("scanning for RoastSeeNEXT")
        devices = await BleakScanner.discover(timeout=self.scan_timeout)
        for device in devices:
            name = (device.name or "").lower()
            if name == "roastseenext" or "roastseenext" in name:
                return device
        return None

    async def run_once(self) -> None:
        from bleak import BleakClient

        device = await self._find_device()
        if device is None:
            raise RuntimeError("RoastSeeNEXT was not found during BLE scan")

        LOG.info("connecting to %s (%s)", device.name, device.address)
        async with BleakClient(device) as client:
            await client.start_notify(CHARACTERISTIC_UUID, self.on_notification)
            LOG.info("subscribed to %s", CHARACTERISTIC_UUID)
            for command in live_commands(auto_start_live=self.auto_start_live):
                await client.write_gatt_char(CHARACTERISTIC_UUID, command, response=True)
                LOG.info("sent BLE command: %s", command.decode("ascii").strip())
                await asyncio.sleep(command_delay(command))
            while client.is_connected:
                await asyncio.sleep(1.0)

    async def run_forever(self, retry_seconds: float = 3.0) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # BLE backends expose varied exception types.
                LOG.warning("BLE session ended: %s; retrying in %.1fs", exc, retry_seconds)
                await asyncio.sleep(retry_seconds)


def dry_run(store: StateStore, hex_text: str) -> int:
    parser = LiveFrameParser()
    raw = bytes.fromhex(hex_text)
    readings = parser.feed(raw)
    for reading in readings:
        store.write(reading)
    LOG.info("dry-run parsed %d valid frame(s)", len(readings))
    return 0 if readings else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--dry-run", metavar="HEX", help="parse a hexadecimal frame without BLE")
    parser.add_argument("--mock-live", action="store_true", help="write one synthetic live frame without BLE")
    parser.add_argument(
        "--auto-start-live",
        action="store_true",
        help="send roasting and start commands after connecting",
    )
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")
    store = StateStore(args.state)
    if args.mock_live:
        mock_live_once(store)
        return 0
    if args.dry_run:
        return dry_run(store, args.dry_run)

    try:
        asyncio.run(NextBleBridge(store, auto_start_live=args.auto_start_live).run_forever())
    except KeyboardInterrupt:
        LOG.info("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
