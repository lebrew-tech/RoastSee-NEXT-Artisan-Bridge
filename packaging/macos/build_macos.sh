#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python -m unittest discover -s next_artisan_bridge/tests -v
python -m PyInstaller --noconfirm --workpath build/macos --distpath build/macos/output packaging/macos/bridge-macos.spec
BUNDLE="dist/macos/RoastSeeNEXT-Artisan-macOS-universal2"
mkdir -p "$BUNDLE"
ditto build/macos/output/RoastSeeNEXTBridge.app "$BUNDLE/RoastSeeNEXTBridge.app"
cp packaging/macos/START_HERE.command packaging/macos/START_LIVE.command packaging/macos/artisan_next_poll "$BUNDLE/"
chmod +x "$BUNDLE/START_HERE.command" "$BUNDLE/START_LIVE.command" "$BUNDLE/artisan_next_poll"
cp README.md README.zh-CN.md LICENSE "$BUNDLE/"
cp -R assets licenses "$BUNDLE/"
python packaging/macos/collect_macos_notices.py "$BUNDLE"
codesign --force --deep --sign - "$BUNDLE/RoastSeeNEXTBridge.app"
codesign --verify --deep --strict "$BUNDLE/RoastSeeNEXTBridge.app"
PYTHONPATH=. python packaging/macos/verify_macos.py "$BUNDLE"
python packaging/macos/verify_universal2.py "$BUNDLE/RoastSeeNEXTBridge.app"
file "$BUNDLE/RoastSeeNEXTBridge.app/Contents/MacOS/RoastSeeNEXTBridge"
ditto -c -k --sequesterRsrc --keepParent "$BUNDLE" "$BUNDLE.zip"
