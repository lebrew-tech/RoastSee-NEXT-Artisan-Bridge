from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "packaging/mac_bridge_entry.py"), str(root / "packaging/poll_entry.py")],
    pathex=[str(root)],
)
pyz = PYZ(a.pure)
bridge = EXE(
    pyz, [s for s in a.scripts if s[0] != "poll_entry"], [],
    exclude_binaries=True, name="RoastSeeNEXTBridge", console=True, target_arch="universal2",
)
poll = EXE(
    pyz, [s for s in a.scripts if s[0] != "mac_bridge_entry"], [],
    exclude_binaries=True, name="artisan_next_poll", console=True, target_arch="universal2",
)
coll = COLLECT(bridge, poll, a.binaries, a.datas, name="macos-runtime")
BUNDLE(
    coll, name="RoastSeeNEXTBridge.app", icon=str(root / "assets/lebrew.icns"),
    bundle_identifier="com.lebrew.nextartisanbridge",
    info_plist={
        "CFBundleShortVersionString": "0.2.2",
        "NSBluetoothAlwaysUsageDescription": "Connect to RoastSee NEXT to receive roast data for Artisan.",
        "NSHighResolutionCapable": True,
    },
)
