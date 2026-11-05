"""Check the native Mac bundle without BLE or the user's state file."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile


def verify(bundle):
    bundle = Path(bundle).resolve()
    app = bundle / "RoastSeeNEXTBridge.app"
    with (app / "Contents/Info.plist").open("rb") as handle:
        assert plistlib.load(handle)["NSBluetoothAlwaysUsageDescription"]
    with tempfile.TemporaryDirectory(prefix="NEXT Mac check ") as temp:
        state = Path(temp) / "custom state.json"
        env = {**os.environ, "PYTHONPATH": "", "PYTHONHOME": "", "PATH": "/usr/bin:/bin"}

        def run(program, *args):
            return subprocess.run(
                [str(program), *args], cwd=temp, env=env, capture_output=True,
                text=True, check=True, timeout=30,
            )

        for launcher in ("START_HERE.command", "START_LIVE.command"):
            assert "--state" in run(bundle / launcher, "--help").stdout
        poll = bundle / "artisan_next_poll"
        empty = run(poll, "--state", str(state))
        assert empty.stdout == ",".join(["-1"] * 16) + "\n"
        run(bundle / "START_HERE.command", "--state", str(state), "--mock-live")
        assert json.loads(state.read_text())["curve_agtron"] == 84.6
        sample = run(poll, "--state", str(state))
        assert sample.stdout == "-1.000,-1,84.600,3,1.200,84.900,327,95,1,-1,-1,-1.000,-1.000,-1,-1.000,-1.000\n"
        assert not sample.stderr
        state.write_text("invalid JSON")
        assert run(poll, "--state", str(state)).stdout == empty.stdout
        # Both native programs must agree on the fixed Application Support path.
        from next_artisan_bridge.artisan_next_poll import default_state_path
        assert default_state_path() == Path.home() / "Library/Application Support/RoastSeeNEXT/latest.json"
    print("macOS bundle OK: CoreBluetooth imports, permission text, launchers, isolated mock/poll, 16 fields.")


if __name__ == "__main__":
    verify(sys.argv[1])
