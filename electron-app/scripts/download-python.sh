#!/usr/bin/env bash
# download-python.sh — Download python-build-standalone and install Python deps
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ELECTRON_APP_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_VERSION="3.11.9"
PYTHON_RELEASE="20240814"  # cpython-3.11.9+20240814
DEST_DIR="$ELECTRON_APP_DIR/resources/python"

# ── Detect arch ──────────────────────────────────────────────────────────────
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
  PLATFORM="aarch64-apple-darwin"
else
  PLATFORM="x86_64-apple-darwin"
fi

FILENAME="cpython-${PYTHON_VERSION}+${PYTHON_RELEASE}-${PLATFORM}-install_only.tar.gz"
URL="https://github.com/indygreg/python-build-standalone/releases/download/${PYTHON_RELEASE}/${FILENAME}"

echo "▶ Detected arch: $ARCH"
echo "▶ Download URL: $URL"

# ── Already exists? ───────────────────────────────────────────────────────────
if [ -f "$DEST_DIR/bin/python3" ]; then
  echo "✓ Python already present at $DEST_DIR — skipping download"
else
  echo "▶ Downloading Python $PYTHON_VERSION for $PLATFORM …"
  TMPFILE=$(mktemp /tmp/python-standalone.XXXXXX.tar.gz)
  trap "rm -f '$TMPFILE'" EXIT

  curl -L --progress-bar -o "$TMPFILE" "$URL"

  echo "▶ Extracting to $DEST_DIR …"
  rm -rf "$DEST_DIR"
  mkdir -p "$DEST_DIR"
  tar -xzf "$TMPFILE" --strip-components=1 -C "$DEST_DIR"
  echo "✓ Python extracted"
fi

PYTHON_BIN="$DEST_DIR/bin/python3"

# ── Install Python deps ───────────────────────────────────────────────────────
echo "▶ Installing Python dependencies …"
"$PYTHON_BIN" -m pip install --upgrade pip --quiet
"$PYTHON_BIN" -m pip install pyyaml openpyxl python-dateutil requests --quiet

echo ""
echo "✅ Done! Python ready at: $DEST_DIR"
"$PYTHON_BIN" --version
