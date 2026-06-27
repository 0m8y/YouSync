#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DESKTOP_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$DESKTOP_DIR/.." && pwd)
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

echo "=============================="
echo " YouSync Python worker build"
echo "=============================="
echo "Project: $PROJECT_DIR"
echo "Desktop: $DESKTOP_DIR"
echo "Python:  $PYTHON_BIN"
echo ""

if [ "$(uname -s)" != "Darwin" ]; then
  echo "❌ The macOS worker sidecar can only be built on macOS." >&2
  exit 1
fi

if [ "$(uname -m)" != "arm64" ]; then
  echo "❌ This script currently builds the aarch64-apple-darwin worker sidecar." >&2
  exit 1
fi

if [ ! -x "$PYTHON_BIN" ]; then
  echo "❌ Python virtualenv not found at $PYTHON_BIN" >&2
  exit 1
fi

cd "$PROJECT_DIR"

echo "🧪 Checking Python syntax..."
"$PYTHON_BIN" -m py_compile \
  core/utils.py \
  core/playlist_managers/SpotifyPlaylistManager.py \
  desktop/python/yousync_worker.py

echo "✅ Python syntax OK"
echo ""

mkdir -p "$DESKTOP_DIR/src-tauri/binaries"
mkdir -p "$DESKTOP_DIR/build/pyinstaller-cache"

export PYINSTALLER_CONFIG_DIR="$DESKTOP_DIR/build/pyinstaller-cache"

echo "🧹 Cleaning previous worker build..."
rm -rf "$DESKTOP_DIR/build/yousync_worker_macos"
rm -rf "$DESKTOP_DIR/build/pyinstaller-cache"
mkdir -p "$DESKTOP_DIR/build/pyinstaller-cache"

echo "🧹 Cleaning previous worker binary..."
rm -f "$DESKTOP_DIR/src-tauri/binaries/"*aarch64-apple-darwin* 2>/dev/null || true

echo "🔨 Building Python worker sidecar..."
cd "$DESKTOP_DIR"

"$PYTHON_BIN" -m PyInstaller \
  --clean \
  --noconfirm \
  --distpath "$DESKTOP_DIR/src-tauri/binaries" \
  --workpath "$DESKTOP_DIR/build/yousync_worker_macos" \
  python/yousync_worker_macos.spec

echo ""
echo "📦 Python sidecar binaries:"
find "$DESKTOP_DIR/src-tauri/binaries" -maxdepth 1 -type f -print -exec ls -lh {} \; -exec shasum -a 256 {} \;

SIDECAR_COUNT=$(find "$DESKTOP_DIR/src-tauri/binaries" -maxdepth 1 -type f -name "*aarch64-apple-darwin*" | wc -l | tr -d " ")

if [ "$SIDECAR_COUNT" = "0" ]; then
  echo "❌ No aarch64-apple-darwin sidecar binary found." >&2
  exit 1
fi

echo ""
echo "✅ Python worker sidecar built"
