"""Exercise the frozen programs without Bluetooth or the user's state file."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def verify(bundle):
    bundle = Path(bundle).resolve()
    bridge = bundle / "RoastSeeNEXTBridge.exe"
    poll = bundle / "artisan_next_poll.exe"
    with tempfile.TemporaryDirectory(prefix="NEXT bridge 验收 ") as temp:
        env = {
            **os.environ, "LOCALAPPDATA": temp, "PYTHONPATH": "", "PYTHONHOME": "",
            "PATH": str(Path(os.environ["SystemRoot"]) / "System32"),
        }

        def run(program, *args):
            return subprocess.run(
                [str(program), *args], cwd=temp, env=env,
                capture_output=True, text=True, check=True, timeout=20,
            )

        for exe in (bridge, poll):
            assert "--state" in run(exe, "--help").stdout
        for launcher in ("START_HERE.cmd", "START_LIVE.cmd"):
            result = subprocess.run(
                [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(bundle / launcher), "--help"],
                cwd=temp, env=env, capture_output=True, text=True, check=True, timeout=20,
            )
            assert "--state" in result.stdout
        missing = run(poll)
        assert missing.stdout == ",".join(["-1"] * 16) + "\n"
        assert not missing.stderr
        run(bridge, "--mock-live")
        state = Path(temp) / "RoastSeeNEXT" / "latest.json"
        assert json.loads(state.read_text())["curve_agtron"] == 84.6
        sample = run(poll)
        assert sample.stdout == "-1.000,-1,84.600,3,1.200,84.900,327,95,1,-1,-1,-1.000,-1.000,-1,-1.000,-1.000\n"
        assert not sample.stderr
        override = Path(temp) / "custom state.json"
        run(bridge, "--state", str(override), "--mock-live")
        assert run(poll, "--state", str(override)).stdout == sample.stdout
        override.write_text("invalid JSON")
        assert run(poll, "--state", str(override)).stdout == missing.stdout
    print("Frozen bundle OK: native backend imports, help, default/override state, 16 fields, missing/corrupt state.")


if __name__ == "__main__":
    verify(sys.argv[1])
