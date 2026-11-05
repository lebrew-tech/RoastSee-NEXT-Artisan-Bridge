"""Artisan external-program adapter for the NEXT BLE bridge."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .next_protocol import format_artisan_sample
from .state_store import StateStore


def default_state_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "RoastSeeNEXT" / "latest.json"
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "RoastSeeNEXT" / "latest.json"
    return Path.cwd() / ".roastsee_next" / "latest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=default_state_path())
    args = parser.parse_args(argv)

    reading = StateStore(args.state).read()
    print(format_artisan_sample(reading), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
