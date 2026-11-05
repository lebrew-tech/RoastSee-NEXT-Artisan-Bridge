#!/bin/sh
set -eu
BRIDGE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$BRIDGE_DIR/RoastSeeNEXTBridge.app/Contents/MacOS/RoastSeeNEXTBridge" "$@"
