#!/usr/bin/env sh
set -eu

print_help() {
  echo "YouSync macOS installer builder"
  echo ""
  echo "Usage:"
  echo "  ./build-macos-installer.sh              Clean then build"
  echo "  ./build-macos-installer.sh --install    Clean, build, then copy app to /Applications"
  echo "  ./build-macos-installer.sh --clean      Clean only"
  echo "  ./build-macos-installer.sh -c           Clean only"
  echo "  ./build-macos-installer.sh --no-clean   Build without cleaning"
  echo "  ./build-macos-installer.sh --help       Show help"
  echo ""
}

CLEAN_ONLY=false
SKIP_CLEAN=false
INSTALL_APP=false

for arg in "$@"; do
  case "$arg" in
    --clean|-c)
      CLEAN_ONLY=true
      ;;
    --no-clean)
      SKIP_CLEAN=true
      ;;
    --install)
      INSTALL_APP=true
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    *)
      echo "❌ Unknown option: $arg" >&2
      echo ""
      print_help
      exit 1
      ;;
  esac
done

if [ "$CLEAN_ONLY" = true ] && [ "$SKIP_CLEAN" = true ]; then
  echo "❌ You cannot use --clean and --no-clean together." >&2
  exit 1
fi

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

clean_outputs() {
  echo ""
  echo "🧹 Cleaning previous frontend build..."
  rm -rf "$DESKTOP_DIR/dist"

  echo "🧹 Cleaning previous Tauri bundles..."
  rm -rf "$TAURI_DIR/target/release/bundle"

  echo "🧹 Cleaning previous macOS installer output..."
  rm -rf "$MACOS_INSTALLER_DIR"

  echo "🧹 Cleaning previous PyInstaller worker build cache..."
  rm -rf "$DESKTOP_DIR/build/yousync_worker_macos"
  rm -rf "$DESKTOP_DIR/build/pyinstaller-cache"

  echo ""
  echo "✅ Clean completed."
}

if [ "$SKIP_CLEAN" = false ]; then
  clean_outputs
fi

if [ "$CLEAN_ONLY" = true ]; then
  exit 0
fi

mkdir -p "$MACOS_INSTALLER_DIR"

cd "$DESKTOP_DIR"

VERSION=$(node -p "require('./package.json').version" 2>/dev/null || echo "0.1.0")
ARCH=$(uname -m)

if [ "$ARCH" = "arm64" ]; then
  ARCH_NAME="arm64"
else
  ARCH_NAME="$ARCH"
fi

echo ""
echo "Root:         $ROOT_DIR"
echo "Project:      $PROJECT_DIR"
echo "Desktop:      $DESKTOP_DIR"
echo "Version:      $VERSION"
echo "Architecture: $ARCH_NAME"
echo "Install app:  $INSTALL_APP"
echo ""

echo "🔨 Building Python worker sidecar..."
"$WORKER_BUILD_SCRIPT"

echo ""
echo "🔨 Building Tauri macOS app..."
npm run tauri -- build --bundles app

echo ""
echo "📦 Searching generated artifacts..."

APP_BUNDLE=$(find "$TAURI_DIR/target/release/bundle/macos" -name "YouSync.app" -type d | head -n 1 || true)
DMG_FILE=$(find "$TAURI_DIR/target/release/bundle/dmg" -name "*.dmg" -type f | head -n 1 || true)

if [ -z "$APP_BUNDLE" ]; then
  echo "❌ No YouSync.app found in:"
  echo "$TAURI_DIR/target/release/bundle/macos"
  exit 1
fi

DMG_OUTPUT="$MACOS_INSTALLER_DIR/YouSyncInstaller-macOS-v$VERSION-$ARCH_NAME.dmg"
APP_OUTPUT="$MACOS_INSTALLER_DIR/YouSync.app"

if [ -n "$DMG_FILE" ]; then
  echo "📁 Copying DMG..."
  cp "$DMG_FILE" "$DMG_OUTPUT"
else
  echo "⚠️ No DMG generated, skipping DMG copy."
  DMG_OUTPUT=""
fi

echo "📁 Copying .app bundle..."
ditto "$APP_BUNDLE" "$APP_OUTPUT"

echo ""
echo "🔍 Worker inside generated .app:"
find "$APP_OUTPUT/Contents" -type f | grep -Ei "worker|aarch64|yousync" | while read f; do
  echo "$f"
  ls -lh "$f"
  shasum -a 256 "$f"
done

if [ "$INSTALL_APP" = true ]; then
  echo ""
  echo "🛑 Closing installed YouSync app if running..."
  osascript -e 'tell application "YouSync" to quit' >/dev/null 2>&1 || true
  sleep 1

  echo "🗑️ Removing old /Applications/YouSync.app..."
  rm -rf "/Applications/YouSync.app"

  echo "📥 Installing new app to /Applications..."
  ditto "$APP_OUTPUT" "/Applications/YouSync.app"

  echo ""
  echo "🔍 Worker inside /Applications/YouSync.app:"
  find "/Applications/YouSync.app/Contents" -type f | grep -Ei "worker|aarch64|yousync" | while read f; do
    echo "$f"
    ls -lh "$f"
    shasum -a 256 "$f"
  done

  echo ""
  echo "✅ Installed:"
  echo "/Applications/YouSync.app"
fi

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
