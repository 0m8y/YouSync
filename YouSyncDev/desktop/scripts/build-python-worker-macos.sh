#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DESKTOP_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$DESKTOP_DIR/.." && pwd)
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "The macOS worker sidecar can only be built on macOS." >&2
  exit 1
fi

if [ "$(uname -m)" != "arm64" ]; then
  echo "This script currently builds the aarch64-apple-darwin worker sidecar." >&2
  exit 1
fi

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python virtualenv not found at $PYTHON_BIN" >&2
  exit 1
fi

mkdir -p "$DESKTOP_DIR/src-tauri/binaries"
mkdir -p "$DESKTOP_DIR/build/pyinstaller-cache"

export PYINSTALLER_CONFIG_DIR="$DESKTOP_DIR/build/pyinstaller-cache"

cd "$DESKTOP_DIR"
"$PYTHON_BIN" -m PyInstaller \
  --clean \
  --noconfirm \
  --distpath "$DESKTOP_DIR/src-tauri/binaries" \
  --workpath "$DESKTOP_DIR/build/yousync_worker_macos" \
  python/yousync_worker_macos.spec
