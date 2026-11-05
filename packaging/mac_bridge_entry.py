"""macOS console entry point, inside a bundle with Bluetooth permission text."""
import sys

from bleak.backends.corebluetooth import client, scanner
from next_artisan_bridge.artisan_next_poll import default_state_path
from next_artisan_bridge.next_ble_bridge import main

raise SystemExit(main(["--state", str(default_state_path()), *sys.argv[1:]]))
