from pathlib import Path

root = Path(SPECPATH).parents[1]
a = Analysis(
    [
        str(root / "packaging/windows/desktop_entry.py"),
        str(root / "packaging/windows/bridge_entry.py"),
        str(root / "packaging/common/poll_entry.py"),
    ],
    pathex=[str(root)],
)
pyz = PYZ(a.pure)
# All three entry points share the dependency analysis and runtime directory.
desktop = EXE(
    pyz, [s for s in a.scripts if s[0] not in ("bridge_entry", "poll_entry")], [],
    exclude_binaries=True, name="RoastSeeNEXT-Artisan", console=False, upx=False,
    icon=str(root / "assets/brand/lebrew.ico"),
)
bridge = EXE(
    pyz, [s for s in a.scripts if s[0] not in ("desktop_entry", "poll_entry")], [],
    exclude_binaries=True, name="RoastSeeNEXTBridge", console=True, upx=False,
)
poll = EXE(
    pyz, [s for s in a.scripts if s[0] not in ("desktop_entry", "bridge_entry")], [],
    exclude_binaries=True, name="artisan_next_poll", console=True, upx=False,
)
COLLECT(desktop, bridge, poll, a.binaries, a.datas, name="RoastSeeNEXT-Artisan-Windows-x64", upx=False)
