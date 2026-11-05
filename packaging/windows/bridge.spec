from pathlib import Path

root = Path(SPECPATH).parents[1]
a = Analysis(
    [str(root / "packaging/windows/bridge_entry.py"), str(root / "packaging/common/poll_entry.py")],
    pathex=[str(root)],
)
pyz = PYZ(a.pure)
# Both programs share one dependency analysis and one runtime directory.
bridge = EXE(
    pyz, [s for s in a.scripts if s[0] != "poll_entry"], [],
    exclude_binaries=True, name="RoastSeeNEXTBridge", console=True, upx=False,
)
poll = EXE(
    pyz, [s for s in a.scripts if s[0] != "bridge_entry"], [],
    exclude_binaries=True, name="artisan_next_poll", console=True, upx=False,
)
COLLECT(bridge, poll, a.binaries, a.datas, name="RoastSeeNEXT-Artisan-Windows-x64", upx=False)
