# YouSync Desktop Packaging

## macOS worker sidecar

The desktop app uses a persistent Python worker for playlist operations. In dev,
Rust launches the source worker through the project virtualenv. For packaged
macOS builds, the worker is bundled as a Tauri sidecar.

Build the macOS sidecar:

```sh
npm run build:worker:macos
```

This creates:

```text
src-tauri/binaries/yousync-worker-aarch64-apple-darwin
```

Tauri is configured with:

```json
"externalBin": ["binaries/yousync-worker"]
```

During `tauri build`, Tauri copies the platform-specific sidecar into the app
bundle and exposes it as `yousync-worker`.

## macOS app build

```sh
npm run tauri -- build
```

The Tauri build command runs the worker sidecar build first, then the frontend
build.

## Dev mode

```sh
npm run tauri -- dev
```

Dev mode still launches:

```text
../.venv/bin/python -u desktop/python/yousync_worker.py
```

If the virtualenv is missing, it falls back to `python3` on macOS/Linux.
