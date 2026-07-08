#!/usr/bin/env sh
set -eu

print_help() {
  echo "YouSync macOS installer builder"
  echo ""
  echo "Usage:"
  echo "  ./build-macos-installer.sh              Clean then build .app + unsigned GitHub-style DMG"
  echo "  ./build-macos-installer.sh --install    Clean, build, then copy app to /Applications"
  echo "  ./build-macos-installer.sh --version 1.0.1 --install"
  echo "  ./build-macos-installer.sh -version 1.0.1 --install"
  echo "  ./build-macos-installer.sh -v 1.0.1 --install"
  echo "  ./build-macos-installer.sh --clean      Clean only"
  echo "  ./build-macos-installer.sh -c           Clean only"
  echo "  ./build-macos-installer.sh --no-clean   Build without cleaning"
  echo "  ./build-macos-installer.sh --help       Show help"
  echo ""
}

CLEAN_ONLY=false
SKIP_CLEAN=false
INSTALL_APP=false
REQUESTED_VERSION=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --clean|-c)
      CLEAN_ONLY=true
      shift
      ;;
    --no-clean)
      SKIP_CLEAN=true
      shift
      ;;
    --install)
      INSTALL_APP=true
      shift
      ;;
    --version|-version|-v)
      if [ "$#" -lt 2 ]; then
        echo "❌ Missing version value after $1" >&2
        exit 1
      fi
      REQUESTED_VERSION="$2"
      shift 2
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    *)
      echo "❌ Unknown option: $1" >&2
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
VERSION_FILE="$ROOT_DIR/VERSION"

WORKER_BUILD_SCRIPT="$DESKTOP_DIR/scripts/build-python-worker-macos.sh"

INSTALLER_ROOT="$ROOT_DIR/installer"
MACOS_INSTALLER_DIR="$INSTALLER_ROOT/YouSyncInstaller-macOS"

DMG_STAGE_DIR="$DESKTOP_DIR/build/dmg-root"

validate_version() {
  VERSION_TO_VALIDATE="$1"

  if ! printf '%s' "$VERSION_TO_VALIDATE" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "❌ Invalid version: $VERSION_TO_VALIDATE" >&2
    echo "Expected SemVer format: MAJOR.MINOR.PATCH, for example 1.0.1" >&2
    exit 1
  fi
}

read_version() {
  if [ ! -f "$VERSION_FILE" ]; then
    echo "❌ VERSION file not found: $VERSION_FILE" >&2
    echo "Create it with a SemVer value, for example: 1.0.0" >&2
    exit 1
  fi

  VERSION_FROM_FILE=$(tr -d '\r\n[:space:]' < "$VERSION_FILE")
  validate_version "$VERSION_FROM_FILE"
  printf '%s' "$VERSION_FROM_FILE"
}

set_version() {
  VERSION_TO_SET="$1"
  validate_version "$VERSION_TO_SET"
  printf '%s\n' "$VERSION_TO_SET" > "$VERSION_FILE"
}

sync_project_versions() {
  VERSION_TO_SYNC="$1"
  validate_version "$VERSION_TO_SYNC"

  echo ""
  echo "🔢 Synchronizing project version..."
  echo "Version: $VERSION_TO_SYNC"

  cd "$DESKTOP_DIR"
  npm version "$VERSION_TO_SYNC" --no-git-tag-version --allow-same-version >/dev/null

  node -e '
const fs = require("fs");
const version = process.argv[1];
const file = "src-tauri/tauri.conf.json";
const data = JSON.parse(fs.readFileSync(file, "utf8"));
data.version = version;
fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
' "$VERSION_TO_SYNC"

  awk -v version="$VERSION_TO_SYNC" '
    BEGIN { in_package = 0; updated = 0 }
    /^\[package\]$/ { in_package = 1; print; next }
    /^\[/ && $0 != "[package]" { in_package = 0 }
    in_package && /^version[[:space:]]*=/ && updated == 0 {
      print "version = \"" version "\"";
      updated = 1;
      next;
    }
    { print }
  ' "$TAURI_DIR/Cargo.toml" > "$TAURI_DIR/Cargo.toml.tmp"
  mv "$TAURI_DIR/Cargo.toml.tmp" "$TAURI_DIR/Cargo.toml"
}

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

if [ -n "$REQUESTED_VERSION" ]; then
  validate_version "$REQUESTED_VERSION"
fi

clean_outputs() {
  echo ""
  echo "🧹 Cleaning previous frontend build..."
  rm -rf "$DESKTOP_DIR/dist"

  echo "🧹 Cleaning previous Tauri bundles..."
  rm -rf "$TAURI_DIR/target/release/bundle"

  echo "🧹 Cleaning previous macOS installer output..."
  rm -rf "$MACOS_INSTALLER_DIR"

  echo "🧹 Cleaning previous DMG staging folder..."
  rm -rf "$DMG_STAGE_DIR"

  echo "🧹 Cleaning previous PyInstaller worker build cache..."
  rm -rf "$DESKTOP_DIR/build/yousync_worker_macos"
  rm -rf "$DESKTOP_DIR/build/pyinstaller-cache"

  echo "🧹 Detaching old mounted YouSync DMG if present..."
  hdiutil detach "/Volumes/YouSync" -force >/dev/null 2>&1 || true

  echo ""
  echo "✅ Clean completed."
}

ad_hoc_sign_app() {
  APP_PATH="$1"

  echo ""
  echo "🔏 Preparing GitHub-style ad-hoc signature..."
  echo "App: $APP_PATH"

  echo "🧹 Removing quarantine/provenance attributes from built app..."
  xattr -cr "$APP_PATH" 2>/dev/null || true

  echo "🧹 Removing old/broken signatures..."
  find "$APP_PATH/Contents/MacOS" -type f | while read f; do
    codesign --remove-signature "$f" >/dev/null 2>&1 || true
  done
  codesign --remove-signature "$APP_PATH" >/dev/null 2>&1 || true
  rm -rf "$APP_PATH/Contents/_CodeSignature"

  echo "🔏 Signing nested executables ad-hoc..."
  find "$APP_PATH/Contents/MacOS" -type f | while read f; do
    if file "$f" | grep -q "Mach-O"; then
      echo "Signing: $f"
      codesign --force --sign - --timestamp=none "$f"
    fi
  done

  echo "🔏 Signing .app bundle ad-hoc..."
  codesign --force --deep --sign - --timestamp=none "$APP_PATH"

  echo ""
  echo "🧪 Checking signature..."
  codesign -vvv --deep --strict "$APP_PATH"

  echo ""
  echo "🧪 Gatekeeper assessment, expected to be rejected because not notarized:"
  spctl --assess --type execute --verbose=4 "$APP_PATH" || true

  echo ""
  echo "✅ Ad-hoc signature completed"
}

if [ "$SKIP_CLEAN" = false ]; then
  clean_outputs
fi

if [ "$CLEAN_ONLY" = true ]; then
  exit 0
fi

mkdir -p "$MACOS_INSTALLER_DIR"

if [ -n "$REQUESTED_VERSION" ]; then
  set_version "$REQUESTED_VERSION"
fi

VERSION=$(read_version)
sync_project_versions "$VERSION"

cd "$DESKTOP_DIR"
ARCH=$(uname -m)

if [ "$ARCH" = "arm64" ]; then
  ARCH_NAME="arm64"
else
  ARCH_NAME="$ARCH"
fi

DMG_OUTPUT="$MACOS_INSTALLER_DIR/YouSyncInstaller-macOS-v$VERSION-$ARCH_NAME.dmg"
APP_OUTPUT="$MACOS_INSTALLER_DIR/YouSync.app"

echo ""
echo "Root:         $ROOT_DIR"
echo "Project:      $PROJECT_DIR"
echo "Desktop:      $DESKTOP_DIR"
echo "Version: $VERSION"
echo "Architecture: $ARCH_NAME"
echo "Install app:  $INSTALL_APP"
echo "DMG: $DMG_OUTPUT"
echo ""

echo "🔨 Building Python worker sidecar..."
"$WORKER_BUILD_SCRIPT"

echo ""
echo "🔨 Building Tauri macOS .app only..."
echo "Command: npm run tauri -- build --bundles app"
echo ""

BUILD_LOG="$DESKTOP_DIR/build/tauri-build-macos.log"
mkdir -p "$DESKTOP_DIR/build"

if ! npm run tauri -- build --bundles app 2>&1 | tee "$BUILD_LOG"; then
  echo ""
  echo "❌ Tauri app build failed."
  echo "Build log:"
  echo "$BUILD_LOG"
  exit 1
fi

echo ""
echo "📦 Searching generated .app..."

APP_BUNDLE=$(find "$TAURI_DIR/target/release/bundle/macos" -name "YouSync.app" -type d | head -n 1 || true)

if [ -z "$APP_BUNDLE" ]; then
  echo "❌ No YouSync.app found in:"
  echo "$TAURI_DIR/target/release/bundle/macos"
  exit 1
fi

echo "📁 Copying .app bundle..."
rm -rf "$APP_OUTPUT"
ditto "$APP_BUNDLE" "$APP_OUTPUT"

ad_hoc_sign_app "$APP_OUTPUT"

echo ""
echo "🔍 Worker inside generated installer .app:"
find "$APP_OUTPUT/Contents" -type f | grep -Ei "worker|aarch64|yousync" | while read f; do
  echo "$f"
  ls -lh "$f"
  shasum -a 256 "$f"
done

echo ""
echo "💿 Creating GitHub-style DMG..."

rm -rf "$DMG_STAGE_DIR"
mkdir -p "$DMG_STAGE_DIR"

ditto "$APP_OUTPUT" "$DMG_STAGE_DIR/YouSync.app"
ln -s /Applications "$DMG_STAGE_DIR/Applications"

rm -f "$DMG_OUTPUT"

hdiutil create \
  -volname "YouSync" \
  -srcfolder "$DMG_STAGE_DIR" \
  -ov \
  -format UDZO \
  "$DMG_OUTPUT"

echo ""
echo "🧹 Removing quarantine from local DMG output..."
xattr -cr "$DMG_OUTPUT" 2>/dev/null || true

echo ""
echo "✅ DMG created:"
echo "$DMG_OUTPUT"

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
  echo "🧪 Checking installed app signature..."
  codesign -vvv --deep --strict "/Applications/YouSync.app"

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
echo "Expected on another Mac:"
echo "  - Not notarized, so macOS may block first launch."
echo "  - It should NOT say damaged because signature is cleaned and ad-hoc signed."
echo "  - User can use right click > Open or Privacy & Security > Open Anyway."
echo ""
