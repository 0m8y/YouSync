#!/usr/bin/env sh
set -eu

echo "=============================="
echo " YouSync macOS installer build"
echo "=============================="

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR="$ROOT_DIR/YouSyncDev"
DESKTOP_DIR="$PROJECT_DIR/desktop"
TAURI_DIR="$DESKTOP_DIR/src-tauri"

WORKER_BUILD_SCRIPT="$DESKTOP_DIR/scripts/build-python-worker-macos.sh"

INSTALLER_ROOT="$ROOT_DIR/installer"
MACOS_INSTALLER_DIR="$INSTALLER_ROOT/YouSyncInstaller-macOS"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "❌ This script must be run on macOS." >&2
  exit 1
fi

if [ ! -d "$DESKTOP_DIR" ]; then
  echo "❌ Desktop folder not found: $DESKTOP_DIR" >&2
  exit 1
fi

if [ ! -x "$WORKER_BUILD_SCRIPT" ]; then
  echo "❌ Worker build script not found or not executable:"
  echo "$WORKER_BUILD_SCRIPT"
  echo ""
  echo "Run:"
  echo "chmod +x \"$WORKER_BUILD_SCRIPT\""
  exit 1
fi

cd "$DESKTOP_DIR"

VERSION=$(node -p "require('./package.json').version" 2>/dev/null || echo "0.1.0")
ARCH=$(uname -m)

if [ "$ARCH" = "arm64" ]; then
  ARCH_NAME="arm64"
else
  ARCH_NAME="$ARCH"
fi

echo ""
echo "Root: $ROOT_DIR"
echo "Project: $PROJECT_DIR"
echo "Desktop: $DESKTOP_DIR"
echo "Version: $VERSION"
echo "Architecture: $ARCH_NAME"
echo ""

echo "🧹 Cleaning previous frontend build..."
rm -rf "$DESKTOP_DIR/dist"

echo "🧹 Cleaning previous Tauri bundles..."
rm -rf "$TAURI_DIR/target/release/bundle"

echo "🧹 Cleaning previous macOS installer output..."
rm -rf "$MACOS_INSTALLER_DIR"
mkdir -p "$MACOS_INSTALLER_DIR"

echo ""
echo "🔨 Building Python worker sidecar..."
"$WORKER_BUILD_SCRIPT"

echo ""
echo "🔨 Building Tauri macOS app..."

if npm run | grep -q "build:macos"; then
  npm run build:macos
else
  npm run tauri -- build
fi

echo ""
echo "📦 Searching generated artifacts..."

DMG_FILE=$(find "$TAURI_DIR/target/release/bundle/dmg" -name "*.dmg" -type f | head -n 1)
APP_BUNDLE=$(find "$TAURI_DIR/target/release/bundle/macos" -name "YouSync.app" -type d | head -n 1)

if [ -z "$DMG_FILE" ]; then
  echo "❌ No DMG file found in:"
  echo "$TAURI_DIR/target/release/bundle/dmg"
  exit 1
fi

if [ -z "$APP_BUNDLE" ]; then
  echo "❌ No YouSync.app found in:"
  echo "$TAURI_DIR/target/release/bundle/macos"
  exit 1
fi

DMG_OUTPUT="$MACOS_INSTALLER_DIR/YouSyncInstaller-macOS-v$VERSION-$ARCH_NAME.dmg"
APP_OUTPUT="$MACOS_INSTALLER_DIR/YouSync.app"

echo "📁 Copying DMG..."
cp "$DMG_FILE" "$DMG_OUTPUT"

echo "📁 Copying .app bundle..."
ditto "$APP_BUNDLE" "$APP_OUTPUT"

echo ""
echo "✅ macOS installer build completed!"
echo ""
echo "Output folder:"
echo "$MACOS_INSTALLER_DIR"
echo ""
echo "DMG:"
echo "$DMG_OUTPUT"
echo ""
echo "App:"
echo "$APP_OUTPUT"
echo ""
