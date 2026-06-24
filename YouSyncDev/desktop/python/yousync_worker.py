#!/usr/bin/env python3
import json
import subprocess
import sys
import threading
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict, Optional

import yousync_bridge as bridge

ORIGINAL_STDOUT = sys.stdout


def log(message: str) -> None:
    print(f"[YouSync worker] {message}", file=sys.stderr, flush=True)


def write_response(payload: Dict[str, Any]) -> None:
    ORIGINAL_STDOUT.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
    ORIGINAL_STDOUT.flush()


def run_sync_child(playlist_id: str) -> int:
    """Run one playlist synchronization in an isolated Python process.

    The persistent worker must stay responsive while Spotify/Apple/Youtube syncs run.
    This child mode keeps all core stdout redirected away from the worker protocol.
    """
    try:
        bridge.ensure_project_root_on_path()

        with redirect_stdout(sys.stderr):
            from core.CentralManager import CentralManager

            manager = CentralManager("playlists.json")
            manager.instantiate_playlist_managers()
            message = manager.update_playlist(playlist_id)

        if message:
            log(f"sync child failed for {playlist_id}: {message}")
            return 1

        return 0
    except Exception as exc:
        log(f"sync child crashed for {playlist_id}: {exc}")
        return 1


class YouSyncWorker:
    def __init__(self) -> None:
        bridge.ensure_project_root_on_path()

        with redirect_stdout(sys.stderr):
            from core.CentralManager import CentralManager, Platform

            self.platform_enum = Platform
            self.manager = CentralManager("playlists.json")

        self.managers_loaded = False
        self.sync_lock = threading.Lock()
        self.manager_lock = threading.Lock()
        self.sync_process: Optional[subprocess.Popen[Any]] = None
        self.manager_refreshed_for_sync = False
        self.sync_state: Dict[str, Any] = {
            "playlistId": None,
            "status": "idle",
            "message": "",
        }
        log("started")

    def detect(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return bridge.detect_platform(str(payload.get("url", "")))

    def preview(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with redirect_stdout(sys.stderr):
            return bridge.preview_playlist(payload)

    def refresh_manager(self) -> None:
        """Reload CentralManager state after a subprocess changed playlist files."""
        with redirect_stdout(sys.stderr):
            from core.CentralManager import CentralManager

            with self.manager_lock:
                self.manager = CentralManager("playlists.json")
                self.managers_loaded = False

    def list(self) -> Any:
        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                playlists = self.manager.list_playlists()

        return [bridge.map_core_playlist(playlist) for playlist in playlists]

    def add(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = str(payload.get("url", "")).strip()
        folder = str(payload.get("folder", "")).strip()
        detection = bridge.detect_platform(url)

        if not detection.get("supported"):
            return {
                "ok": False,
                "message": "A supported playlist URL is required.",
            }

        if not folder:
            return {
                "ok": False,
                "message": "A destination folder is required.",
            }

        folder_path = Path(folder).expanduser()

        if not folder_path.exists():
            return {
                "ok": False,
                "message": "The selected destination folder does not exist.",
            }

        if not folder_path.is_dir():
            return {
                "ok": False,
                "message": "The selected destination is not a folder.",
            }

        platform_map = {
            "youtube": self.platform_enum.YOUTUBE,
            "spotify": self.platform_enum.SPOTIFY,
            "apple": self.platform_enum.APPLE,
        }
        platform = platform_map.get(detection["platform"])

        if platform is None:
            return {
                "ok": False,
                "message": "This platform is not supported yet.",
            }

        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                message = self.manager.add_playlist(url, str(folder_path), platform)
                playlists = self.manager.list_playlists()

        self.managers_loaded = False

        playlist = next(
            (
                bridge.map_core_playlist(playlist, cover_wait_seconds=1.0)
                for playlist in playlists
                if playlist.url == url
            ),
            None,
        )
        ok = message == "Playlist added successfully."
        response: Dict[str, Any] = {
            "ok": ok,
            "message": message,
        }

        if playlist is not None:
            response["playlist"] = playlist

        return response

    def sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()

        if not playlist_id:
            raise ValueError("A playlist id is required.")

        with self.sync_lock:
            if self.sync_state.get("status") == "syncing":
                return {
                    "started": False,
                    "playlistId": playlist_id,
                    "message": "A sync is already running.",
                }

            script_path = Path(__file__).resolve()
            self.sync_process = subprocess.Popen(
                [sys.executable, "-u", str(script_path), "--sync-child", playlist_id],
                cwd=str(bridge.project_root()),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=sys.stderr,
            )

            self.manager_refreshed_for_sync = False
            self.sync_state = {
                "playlistId": playlist_id,
                "status": "syncing",
                "message": "",
            }

        return {
            "started": True,
            "playlistId": playlist_id,
        }

    def sync_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()

        if not playlist_id:
            raise ValueError("A playlist id is required.")

        should_refresh_manager = False

        with self.sync_lock:
            state = dict(self.sync_state)
            process = self.sync_process

            if state.get("playlistId") != playlist_id:
                return {
                    "playlistId": playlist_id,
                    "status": "idle",
                    "message": "",
                }

            if state.get("status") == "syncing" and process is not None:
                return_code = process.poll()

                if return_code is None:
                    return {
                        "playlistId": playlist_id,
                        "status": "syncing",
                        "message": "",
                    }

                self.sync_process = None

                if return_code == 0:
                    self.sync_state = {
                        "playlistId": playlist_id,
                        "status": "completed",
                        "message": "Sync completed.",
                    }
                    should_refresh_manager = True
                else:
                    self.sync_state = {
                        "playlistId": playlist_id,
                        "status": "error",
                        "message": "Sync failed.",
                    }

                state = dict(self.sync_state)

            elif state.get("status") == "completed" and not self.manager_refreshed_for_sync:
                should_refresh_manager = True

        if should_refresh_manager:
            try:
                self.refresh_manager()
                with self.sync_lock:
                    self.manager_refreshed_for_sync = True
            except Exception as exc:
                log(f"failed to refresh manager after sync: {exc}")

        return {
            "playlistId": playlist_id,
            "status": state.get("status", "idle"),
            "message": state.get("message", ""),
        }

    def handle(self, command: str, payload: Dict[str, Any]) -> Any:
        if command == "detect":
            return self.detect(payload)

        if command == "preview":
            return self.preview(payload)

        if command == "list":
            return self.list()

        if command == "add":
            return self.add(payload)

        if command == "sync":
            return self.sync(payload)

        if command == "sync_status":
            return self.sync_status(payload)

        raise ValueError(f"Unknown command: {command}")


def read_request(line: str) -> Dict[str, Any]:
    request = json.loads(line)

    if not isinstance(request, dict):
        raise ValueError("Request must be a JSON object.")

    return request


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--sync-child":
        return run_sync_child(sys.argv[2])

    try:
        worker = YouSyncWorker()
    except Exception as exc:
        log(f"failed to start: {exc}")
        return 1

    for line in sys.stdin:
        request_id: Optional[str] = None

        if not line.strip():
            continue

        try:
            request = read_request(line)
            request_id = request.get("id")
            command = str(request.get("command", ""))
            payload = request.get("payload") or {}

            if not isinstance(payload, dict):
                raise ValueError("Request payload must be a JSON object.")

            data = worker.handle(command, payload)
            write_response({"id": request_id, "ok": True, "data": data})
        except Exception as exc:
            log(str(exc))
            write_response({"id": request_id, "ok": False, "message": str(exc)})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
