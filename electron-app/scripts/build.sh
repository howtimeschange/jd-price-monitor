#!/usr/bin/env bash
# build.sh — Full build pipeline: python + dist
# Run from either jd-price-monitor/ root or electron-app/ directory
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ELECTRON_APP_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$ELECTRON_APP_DIR")"

echo "=== Step 1/4: Install electron-app runtime dependencies ==="
npm install --prefix "$ELECTRON_APP_DIR" --omit=dev

echo ""
echo "=== Step 2/4: Install build tools (electron + electron-builder) ==="
npm install --prefix "$PROJECT_ROOT"

echo ""
echo "=== Step 3/4: Download bundled Python ==="
bash "$ELECTRON_APP_DIR/scripts/download-python.sh"

echo ""
echo "=== Step 4/4: Build Electron app ==="
CSC_IDENTITY_AUTO_DISCOVERY=false \
env -u ELECTRON_RUN_AS_NODE \
  "$PROJECT_ROOT/node_modules/.bin/electron-builder" \
  --config "$ELECTRON_APP_DIR/electron-builder.yml"

echo ""
echo "✅ Build complete! Check electron-app/dist/ for the .dmg file."
ls -lh "$ELECTRON_APP_DIR/dist/"*.dmg 2>/dev/null || true
