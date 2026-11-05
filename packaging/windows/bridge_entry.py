"""Windows entry point with the same default state path as the poller."""
import sys

# Import the Windows backend here so frozen builds verify their native dependencies.
from bleak.backends.winrt import client, scanner
from next_artisan_bridge.artisan_next_poll import default_state_path
from next_artisan_bridge.next_ble_bridge import main

raise SystemExit(main(["--state", str(default_state_path()), *sys.argv[1:]]))
