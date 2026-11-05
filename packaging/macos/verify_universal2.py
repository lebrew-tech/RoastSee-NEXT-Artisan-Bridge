"""Reject a universal Mac package if any Mach-O file lacks either CPU slice."""
from pathlib import Path
import subprocess
import sys

MACH_O = {
    bytes.fromhex(h) for h in (
        "feedface", "cefaedfe", "feedfacf", "cffaedfe",
        "cafebabe", "bebafeca", "cafebabf", "bfbafeca",
    )
}
count = 0
for path in Path(sys.argv[1]).rglob("*"):
    if not path.is_file():
        continue
    with path.open("rb") as handle:
        if handle.read(4) not in MACH_O:
            continue
    arches = subprocess.check_output(["lipo", "-archs", str(path)], text=True).split()
    if not {"arm64", "x86_64"}.issubset(arches):
        raise RuntimeError(f"Not universal2: {path}: {arches}")
    count += 1
assert count >= 2, "No bridge/poller Mach-O binaries found"
print(f"Universal2 OK: all {count} Mach-O paths contain arm64 and x86_64.")
