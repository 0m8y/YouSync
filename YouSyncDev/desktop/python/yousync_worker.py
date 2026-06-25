#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import threading
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yousync_bridge as bridge

ORIGINAL_STDOUT = sys.stdout


def log(message: str) -> None:
    print(f"[YouSync worker] {message}", file=sys.stderr, flush=True)


def write_response(payload: Dict[str, Any]) -> None:
    ORIGINAL_STDOUT.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
    ORIGINAL_STDOUT.flush()


def write_child_result(payload: Dict[str, Any]) -> None:
    ORIGINAL_STDOUT.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
    ORIGINAL_STDOUT.flush()


def progress_jobs_dir() -> Path:
    jobs_dir = Path(tempfile.gettempdir()) / "yousync_jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


def create_progress_path() -> Path:
    return progress_jobs_dir() / f"{uuid.uuid4().hex}.json"


def write_progress(progress_path: Optional[str], payload: Dict[str, Any]) -> None:
    if not progress_path:
        return

    try:
        path = Path(progress_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = Path(f"{progress_path}.tmp")

        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, separators=(",", ":"), ensure_ascii=False)

        os.replace(tmp_path, path)
    except Exception as exc:
        log(f"failed to write progress: {exc}")


def read_progress(progress_path: Optional[str]) -> Dict[str, Any]:
    if not progress_path:
        return {}

    try:
        with open(progress_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        log(f"failed to read progress: {exc}")
        return {}


def audio_title(audio_manager: Any) -> str:
    metadata = audio_manager.metadata
    return str(
        getattr(metadata, "video_title", "")
        or getattr(metadata, "title", "")
        or audio_manager.url
    )


def playlist_progress(
    status: str,
    phase: str,
    current: int = 0,
    total: int = 0,
    current_track: str = "",
    failed_count: int = 0,
    message: str = "",
) -> Dict[str, Any]:
    return {
        "status": status,
        "phase": phase,
        "current": current,
        "total": total,
        "currentTrack": current_track,
        "failedCount": failed_count,
        "message": message,
    }


def write_playlist_progress(
    progress_path: Optional[str],
    progress_state: Dict[str, Any],
    playlist_id: str,
    playlist_state: Dict[str, Any],
    progress_lock: Optional[threading.Lock] = None,
) -> None:
    def update() -> None:
        playlists = progress_state.get("playlists")
        if not isinstance(playlists, dict):
            playlists = {}

        playlists[playlist_id] = playlist_state
        progress_state["playlists"] = playlists
        update_payload = {
            "playlistId": playlist_id,
            "phase": playlist_state.get("phase", progress_state.get("phase", "idle")),
            "current": playlist_state.get("current", 0),
            "total": playlist_state.get("total", 0),
            "currentTrack": playlist_state.get("currentTrack", ""),
            "failedCount": playlist_state.get("failedCount", 0),
            "message": playlist_state.get("message", ""),
        }

        # For single-playlist jobs, the top-level status must follow the
        # playlist status. Otherwise, after a completed sync the worker can
        # keep reading a stale top-level "syncing" state from the progress file
        # and incorrectly refuse the next sync.
        if progress_state.get("jobType") != "all":
            update_payload["status"] = playlist_state.get(
                "status",
                progress_state.get("status", "idle"),
            )

        progress_state.update(update_payload)
        write_progress(progress_path, progress_state)

    if progress_lock is None:
        update()
        return

    with progress_lock:
        update()


def download_incomplete_audios(
    manager: Any,
    playlist_id: str,
    progress_path: Optional[str] = None,
    job_type: str = "single",
    playlist_title: str = "",
    playlist_current: Optional[int] = None,
    playlist_total: Optional[int] = None,
    initial_failed_count: int = 0,
    progress_state: Optional[Dict[str, Any]] = None,
    progress_lock: Optional[threading.Lock] = None,
) -> Dict[str, Any]:
    audio_managers = manager.get_audio_managers(playlist_id) or []
    incomplete_audio_managers = [
        audio_manager
        for audio_manager in audio_managers
        if (
            not audio_manager.metadata.is_downloaded
            or not audio_manager.metadata.metadata_updated
        )
    ]

    failed_downloads = 0
    total = len(incomplete_audio_managers)

    if progress_state is None:
        progress_state = {
            "jobType": job_type,
            "playlistId": playlist_id,
            "playlistTitle": playlist_title,
            "status": "syncing",
            "phase": "downloading" if total else "completed",
            "current": 0,
            "total": total,
            "currentTrack": "",
            "failedCount": initial_failed_count,
            "message": f"Downloading 0 / {total}" if total else "No missing downloads.",
            "playlistCurrent": playlist_current,
            "playlistTotal": playlist_total,
            "playlists": {},
        }
    else:
        progress_state.update(
            {
                "jobType": job_type,
                "playlistId": playlist_id,
                "playlistTitle": playlist_title,
                "status": "syncing",
                "playlistCurrent": playlist_current,
                "playlistTotal": playlist_total,
            }
        )

    write_playlist_progress(
        progress_path,
        progress_state,
        playlist_id,
        playlist_progress(
            "syncing",
            "downloading" if total else "completed",
            total=total,
            failed_count=initial_failed_count,
            message=f"Downloading 0 / {total}" if total else "No missing downloads.",
        ),
        progress_lock,
    )

    def download_audio(audio_manager: Any) -> Tuple[str, Optional[str]]:
        title = ""
        try:
            title = audio_title(audio_manager)
            audio_manager.download()
            return title, None
        except Exception as exc:
            return title or "Unknown audio", str(exc)

    if total:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []

            for audio_manager in incomplete_audio_managers:
                title = audio_title(audio_manager)
                write_playlist_progress(
                    progress_path,
                    progress_state,
                    playlist_id,
                    playlist_progress(
                        "syncing",
                        "downloading",
                        current=0,
                        total=total,
                        current_track=title,
                        failed_count=initial_failed_count + failed_downloads,
                        message=f"Downloading 0 / {total}",
                    ),
                    progress_lock,
                )
                futures.append(executor.submit(download_audio, audio_manager))

            for future in as_completed(futures):
                title, error = future.result()

                if error:
                    failed_downloads += 1
                    log(f"download failed for {playlist_id} / {title}: {error}")

                completed = len([item for item in futures if item.done()])
                write_playlist_progress(
                    progress_path,
                    progress_state,
                    playlist_id,
                    playlist_progress(
                        "syncing",
                        "downloading",
                        current=completed,
                        total=total,
                        current_track=title,
                        failed_count=initial_failed_count + failed_downloads,
                        message=f"Downloading {completed} / {total}",
                    ),
                    progress_lock,
                )

    return {
        "attemptedDownloads": len(incomplete_audio_managers),
        "failedDownloads": failed_downloads,
    }


def sync_playlist_and_download_missing(
    manager: Any,
    playlist_id: str,
    progress_path: Optional[str] = None,
    job_type: str = "single",
    playlist_current: Optional[int] = None,
    playlist_total: Optional[int] = None,
    initial_failed_count: int = 0,
    progress_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    playlist = manager.get_playlist(playlist_id)
    playlist_title = playlist.title if playlist else ""
    if progress_state is None:
        progress_state = {
            "jobType": job_type,
            "playlistId": playlist_id,
            "playlistTitle": playlist_title,
            "status": "syncing",
            "phase": "syncing",
            "current": 0,
            "total": 0,
            "currentTrack": "",
            "failedCount": initial_failed_count,
            "message": "Syncing playlist...",
            "playlistCurrent": playlist_current,
            "playlistTotal": playlist_total,
            "playlists": {},
        }
    else:
        progress_state.update(
            {
                "jobType": job_type,
                "playlistId": playlist_id,
                "playlistTitle": playlist_title,
                "status": "syncing",
                "phase": "syncing",
                "current": 0,
                "total": 0,
                "currentTrack": "",
                "failedCount": initial_failed_count,
                "message": "Syncing playlist...",
                "playlistCurrent": playlist_current,
                "playlistTotal": playlist_total,
            }
        )

    write_playlist_progress(
        progress_path,
        progress_state,
        playlist_id,
        playlist_progress(
            "syncing",
            "syncing",
            failed_count=initial_failed_count,
            message="Syncing playlist...",
        ),
    )

    message = manager.update_playlist(playlist_id)

    if message:
        write_playlist_progress(
            progress_path,
            progress_state,
            playlist_id,
            playlist_progress(
                "error",
                "error",
                failed_count=initial_failed_count + 1,
                message=message,
            ),
        )
        return {
            "ok": False,
            "playlistId": playlist_id,
            "playlistTitle": playlist_title,
            "message": message,
            "attemptedDownloads": 0,
            "failedDownloads": 0,
        }

    download_result = download_incomplete_audios(
        manager,
        playlist_id,
        progress_path=progress_path,
        job_type=job_type,
        playlist_title=playlist_title,
        playlist_current=playlist_current,
        playlist_total=playlist_total,
        initial_failed_count=initial_failed_count,
        progress_state=progress_state,
    )
    failed_downloads = int(download_result["failedDownloads"])

    if failed_downloads > 0:
        message = f"Sync completed with {failed_downloads} failed downloads."
    else:
        message = "Sync completed."

    write_playlist_progress(
        progress_path,
        progress_state,
        playlist_id,
        playlist_progress(
            "completed",
            "completed",
            current=int(download_result["attemptedDownloads"]),
            total=int(download_result["attemptedDownloads"]),
            failed_count=initial_failed_count + failed_downloads,
            message=message,
        ),
    )

    return {
        "ok": True,
        "playlistId": playlist_id,
        "playlistTitle": playlist_title,
        "message": message,
        **download_result,
    }


def run_sync_child(playlist_id: str, progress_path: Optional[str] = None) -> int:
    """Run one playlist synchronization in an isolated Python process."""
    try:
        bridge.ensure_project_root_on_path()

        with redirect_stdout(sys.stderr):
            from core.CentralManager import CentralManager

            manager = CentralManager("playlists.json")
            manager.instantiate_playlist_managers()
            result = sync_playlist_and_download_missing(
                manager,
                playlist_id,
                progress_path=progress_path,
                job_type="single",
            )

        write_child_result(result)

        if not result.get("ok"):
            log(f"sync child failed for {playlist_id}: {result.get('message')}")
            return 1

        return 0
    except Exception as exc:
        result = {
            "ok": False,
            "playlistId": playlist_id,
            "message": "Sync failed.",
        }
        write_progress(
            progress_path,
            {
                "jobType": "single",
                "playlistId": playlist_id,
                "status": "error",
                "phase": "error",
                "current": 0,
                "total": 0,
                "currentTrack": "",
                "failedCount": 1,
                "message": "Sync failed.",
            },
        )
        write_child_result(result)
        log(f"sync child crashed for {playlist_id}: {exc}")
        return 1


def run_sync_all_child(progress_path: Optional[str] = None) -> int:
    """Run all playlist synchronizations in an isolated Python process."""
    try:
        bridge.ensure_project_root_on_path()

        with redirect_stdout(sys.stderr):
            from core.CentralManager import CentralManager

            manager = CentralManager("playlists.json")
            manager.instantiate_playlist_managers()
            playlists = manager.list_playlists()
            failed_playlists = 0
            failed_downloads = 0
            attempted_downloads = 0
            playlist_total = len(playlists)
            progress_state = {
                "jobType": "all",
                "playlistId": None,
                "playlistTitle": "",
                "status": "syncing",
                "phase": "syncing",
                "current": 0,
                "total": playlist_total,
                "currentTrack": "",
                "failedCount": 0,
                "message": "Sync all running...",
                "playlistCurrent": 0,
                "playlistTotal": playlist_total,
                "playlists": {
                    playlist.id: playlist_progress(
                        "queued",
                        "queued",
                        message="Queued",
                    )
                    for playlist in playlists
                },
            }
            write_progress(progress_path, progress_state)

            for playlist_index, playlist in enumerate(playlists, start=1):
                result = sync_playlist_and_download_missing(
                    manager,
                    playlist.id,
                    progress_path=progress_path,
                    job_type="all",
                    playlist_current=playlist_index,
                    playlist_total=playlist_total,
                    initial_failed_count=failed_playlists + failed_downloads,
                    progress_state=progress_state,
                )
                attempted_downloads += int(result.get("attemptedDownloads", 0))
                failed_downloads += int(result.get("failedDownloads", 0))

                if not result.get("ok"):
                    failed_playlists += 1
                    log(f"sync all child failed for {playlist.id}: {result.get('message')}")

        failures = []

        if failed_playlists:
            failures.append(
                f"{failed_playlists} failed playlist{'s' if failed_playlists != 1 else ''}"
            )

        if failed_downloads:
            failures.append(
                f"{failed_downloads} failed download{'s' if failed_downloads != 1 else ''}"
            )

        message = (
            "Sync all completed with " + " and ".join(failures) + "."
            if failures
            else "Sync all completed."
        )
        write_child_result(
            {
                "ok": True,
                "message": message,
                "failedPlaylists": failed_playlists,
                "attemptedDownloads": attempted_downloads,
                "failedDownloads": failed_downloads,
            }
        )
        write_progress(
            progress_path,
            {
                **progress_state,
                "jobType": "all",
                "playlistId": None,
                "playlistTitle": "",
                "status": "completed",
                "phase": "completed",
                "current": playlist_total,
                "total": playlist_total,
                "currentTrack": "",
                "failedCount": failed_playlists + failed_downloads,
                "message": message,
                "playlistCurrent": playlist_total,
                "playlistTotal": playlist_total,
            },
        )

        return 0
    except Exception as exc:
        write_progress(
            progress_path,
            {
                "jobType": "all",
                "playlistId": None,
                "status": "error",
                "phase": "error",
                "current": 0,
                "total": 0,
                "currentTrack": "",
                "failedCount": 1,
                "message": "Sync all failed.",
            },
        )
        write_child_result(
            {
                "ok": False,
                "message": "Sync all failed.",
            }
        )
        log(f"sync all child crashed: {exc}")
        return 1


def run_download_missing_child(playlist_id: str, progress_path: Optional[str] = None) -> int:
    """Download incomplete audios for one playlist in an isolated Python process."""
    try:
        bridge.ensure_project_root_on_path()

        with redirect_stdout(sys.stderr):
            from core.CentralManager import CentralManager

            manager = CentralManager("playlists.json")
            manager.instantiate_playlist_managers()
            playlist = manager.get_playlist(playlist_id)
            playlist_title = playlist.title if playlist else ""
            progress_state = {
                "jobType": "download_missing",
                "playlistId": playlist_id,
                "playlistTitle": playlist_title,
                "status": "syncing",
                "phase": "downloading",
                "current": 0,
                "total": 0,
                "currentTrack": "",
                "failedCount": 0,
                "message": "Preparing downloads...",
                "playlists": {},
            }
            if not playlist:
                result = {
                    "ok": False,
                    "playlistId": playlist_id,
                    "message": f"Playlist with ID {playlist_id} not found.",
                }
                write_playlist_progress(
                    progress_path,
                    progress_state,
                    playlist_id,
                    playlist_progress(
                        "error",
                        "error",
                        failed_count=1,
                        message=result["message"],
                    ),
                )
                write_child_result(result)
                return 1

            result = download_incomplete_audios(
                manager,
                playlist_id,
                progress_path=progress_path,
                job_type="download_missing",
                playlist_title=playlist_title,
                progress_state=progress_state,
            )

        failed_downloads = int(result["failedDownloads"])

        if failed_downloads > 0:
            message = f"Download missing completed with {failed_downloads} failed downloads."
        else:
            message = "Download missing completed."

        write_playlist_progress(
            progress_path,
            progress_state,
            playlist_id,
            playlist_progress(
                "completed",
                "completed",
                current=int(result["attemptedDownloads"]),
                total=int(result["attemptedDownloads"]),
                failed_count=failed_downloads,
                message=message,
            ),
        )
        write_child_result(
            {
                "ok": True,
                "playlistId": playlist_id,
                "message": message,
                **result,
            }
        )

        return 0
    except Exception as exc:
        write_progress(
            progress_path,
            {
                "jobType": "download_missing",
                "playlistId": playlist_id,
                "status": "error",
                "phase": "error",
                "current": 0,
                "total": 0,
                "currentTrack": "",
                "failedCount": 1,
                "message": "Download missing failed.",
            },
        )
        write_child_result(
            {
                "ok": False,
                "playlistId": playlist_id,
                "message": "Download missing failed.",
            }
        )
        log(f"download missing child crashed for {playlist_id}: {exc}")
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
        # A single global process is kept for Sync All. Individual playlist
        # sync/download tasks are tracked separately so several playlists can
        # run at the same time.
        self.sync_process: Optional[subprocess.Popen[Any]] = None
        self.manager_refreshed_for_sync = False
        self.sync_tasks: Dict[str, Dict[str, Any]] = {}
        self.sync_state: Dict[str, Any] = {
            "jobType": None,
            "playlistId": None,
            "playlistIds": [],
            "playlistTitle": "",
            "status": "idle",
            "phase": "idle",
            "current": 0,
            "total": 0,
            "currentTrack": "",
            "failedCount": 0,
            "message": "",
            "progressPath": None,
            "playlists": {},
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

    def playlist_details(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()

        if not playlist_id:
            raise ValueError("A playlist id is required.")

        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                playlist = next(
                    (
                        playlist
                        for playlist in self.manager.list_playlists()
                        if playlist.id == playlist_id
                    ),
                    None,
                )

        if playlist is None:
            raise ValueError(f"Playlist with ID {playlist_id} not found.")

        cache = bridge.read_playlist_cache(playlist.path)
        audios = cache.get("audios", [])
        if not isinstance(audios, list):
            audios = []

        def audio_title(audio: Dict[str, Any]) -> str:
            title = str(audio.get("title") or audio.get("video_title") or "").strip()
            if title:
                return title

            file_path = str(audio.get("path_to_save_audio_with_title") or "").strip()
            if file_path:
                return Path(file_path).stem

            return "—"

        def audio_status(audio: Dict[str, Any]) -> str:
            if bridge.audio_has_error(audio):
                return "Error"

            is_downloaded = audio.get("is_downloaded") is True
            metadata_updated = audio.get("metadata_updated") is True

            if is_downloaded and metadata_updated:
                return "Synced"
            if is_downloaded:
                return "Downloaded"
            if metadata_updated:
                return "Metadata"
            return "Missing"

        tracks = []
        for index, raw_audio in enumerate(audios, start=1):
            if not isinstance(raw_audio, dict):
                continue

            duration = raw_audio.get("duration") or raw_audio.get("duration_string")
            tracks.append(
                {
                    "index": index,
                    "title": audio_title(raw_audio),
                    "artist": str(raw_audio.get("artist") or "").strip() or "—",
                    "duration": str(duration).strip() if duration else "—",
                    "status": audio_status(raw_audio),
                    "url": raw_audio.get("url") or None,
                }
            )

        summary = bridge.map_core_playlist(playlist)

        return {
            "playlist": {
                **summary,
                "sourceUrl": cache.get("playlist_url") or playlist.url,
            },
            "tracks": tracks,
        }

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

    def playlist_ids(self) -> List[str]:
        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                return [playlist.id for playlist in self.manager.list_playlists()]

    def playlist_title(self, playlist_id: str) -> str:
        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                playlist = next(
                    (
                        playlist
                        for playlist in self.manager.list_playlists()
                        if playlist.id == playlist_id
                    ),
                    None,
                )

        return playlist.title if playlist else ""

    def merge_state_progress(self, state: Dict[str, Any]) -> Dict[str, Any]:
        progress = read_progress(state.get("progressPath"))
        if not progress:
            return state

        return {**state, **progress}

    def merge_progress(self, state: Dict[str, Any]) -> Dict[str, Any]:
        merged = self.merge_state_progress(state)
        self.sync_state = merged
        return merged

    def merge_playlist_task_progress_locked(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        task = self.sync_tasks.get(playlist_id)

        if task is None:
            return None

        state = self.merge_state_progress(dict(task.get("state") or {}))
        task["state"] = state
        return state

    def poll_playlist_task_locked(self, playlist_id: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Update one individual playlist task. Must be called with sync_lock held."""
        task = self.sync_tasks.get(playlist_id)

        if task is None:
            return None, False

        state = self.merge_playlist_task_progress_locked(playlist_id) or {}
        process = task.get("process")
        should_refresh_manager = False

        if state.get("status") == "syncing" and process is not None:
            return_code = process.poll()

            if return_code is None:
                return state, False

            task["process"] = None
            child_ok = return_code == 0
            state = self.merge_playlist_task_progress_locked(playlist_id) or state
            failed_count = state.get("failedCount")

            if failed_count in (None, ""):
                failed_count = 0

            if child_ok:
                progress_status = state.get("status")
                progress_phase = state.get("phase")
                task["state"] = {
                    **state,
                    "status": progress_status if progress_status in {"completed", "error"} else "completed",
                    "phase": progress_phase if progress_phase in {"completed", "error"} else "completed",
                    "failedCount": failed_count,
                    "message": state.get("message") or "Sync completed.",
                }
            else:
                task["state"] = {
                    **state,
                    "status": "error",
                    "phase": "error",
                    "failedCount": failed_count,
                    "message": state.get("message") or "Sync failed.",
                }

            task["refreshed"] = False
            should_refresh_manager = True
            state = dict(task["state"])

        elif state.get("status") in {"completed", "error"} and not task.get("refreshed"):
            should_refresh_manager = True

        return state, should_refresh_manager

    def poll_playlist_tasks_locked(self) -> bool:
        """Poll every individual playlist task. Must be called with sync_lock held."""
        should_refresh_manager = False

        for playlist_id in list(self.sync_tasks.keys()):
            _state, should_refresh_task = self.poll_playlist_task_locked(playlist_id)
            should_refresh_manager = should_refresh_manager or should_refresh_task

        return should_refresh_manager

    def is_playlist_task_running_locked(self, playlist_id: str) -> bool:
        task = self.sync_tasks.get(playlist_id)

        if task is None:
            return False

        process = task.get("process")

        if process is not None and process.poll() is None:
            return True

        state = task.get("state") if isinstance(task.get("state"), dict) else {}
        return bool(state.get("status") == "syncing" and process is not None)

    def has_running_playlist_tasks_locked(self) -> bool:
        self.poll_playlist_tasks_locked()
        return any(
            self.is_playlist_task_running_locked(playlist_id)
            for playlist_id in list(self.sync_tasks.keys())
        )

    def refresh_after_completed_playlist_task(self, playlist_id: str, should_refresh_manager: bool) -> None:
        if not should_refresh_manager:
            return

        try:
            self.refresh_manager()
            with self.sync_lock:
                task = self.sync_tasks.get(playlist_id)

                if task is not None:
                    task["refreshed"] = True
        except Exception as exc:
            log(f"failed to refresh manager after playlist task: {exc}")

    def refresh_after_completed_playlist_tasks(self, should_refresh_manager: bool) -> None:
        if not should_refresh_manager:
            return

        try:
            self.refresh_manager()
            with self.sync_lock:
                for task in self.sync_tasks.values():
                    state = task.get("state") if isinstance(task.get("state"), dict) else {}

                    if state.get("status") in {"completed", "error"}:
                        task["refreshed"] = True
        except Exception as exc:
            log(f"failed to refresh manager after playlist tasks: {exc}")

    def poll_sync_process_locked(self) -> Tuple[Dict[str, Any], bool]:
        """Update sync_state from subprocess status. Must be called with sync_lock held."""
        state = self.merge_progress(dict(self.sync_state))
        process = self.sync_process
        should_refresh_manager = False

        if state.get("status") == "syncing" and process is not None:
            return_code = process.poll()

            if return_code is None:
                return state, False

            self.sync_process = None
            child_ok = return_code == 0

            # The progress JSON file is the source of truth. Child stdout is
            # intentionally discarded to avoid deadlocks during noisy downloads.
            state = self.merge_progress(dict(self.sync_state))
            failed_count = state.get("failedCount")
            if failed_count in (None, ""):
                failed_count = 0

            if child_ok:
                progress_status = state.get("status")
                progress_phase = state.get("phase")
                self.sync_state = {
                    **state,
                    "status": progress_status if progress_status in {"completed", "error"} else "completed",
                    "phase": progress_phase if progress_phase in {"completed", "error"} else "completed",
                    "failedCount": failed_count,
                    "message": state.get("message") or "Sync completed.",
                }
                should_refresh_manager = True
            else:
                self.sync_state = {
                    **state,
                    "status": "error",
                    "phase": "error",
                    "failedCount": failed_count,
                    "message": state.get("message") or "Sync failed.",
                }
                should_refresh_manager = True

            state = dict(self.sync_state)

        elif state.get("status") in {"completed", "error"} and not self.manager_refreshed_for_sync:
            should_refresh_manager = True

        return state, should_refresh_manager

    def refresh_after_completed_sync(self, should_refresh_manager: bool) -> None:
        if not should_refresh_manager:
            return

        try:
            self.refresh_manager()
            with self.sync_lock:
                self.manager_refreshed_for_sync = True
        except Exception as exc:
            log(f"failed to refresh manager after sync: {exc}")

    def start_sync_process(self, args: List[str]) -> subprocess.Popen[Any]:
        script_path = Path(__file__).resolve()
        return subprocess.Popen(
            [sys.executable, "-u", str(script_path), *args],
            cwd=str(bridge.project_root()),
            stdin=subprocess.DEVNULL,
            # Never keep child stdout as a pipe: the core/downloader may print a
            # lot during sync. If the pipe fills, the child blocks forever and
            # the worker keeps thinking that "A sync is already running".
            # Progress is already reported through the progress JSON file.
            stdout=subprocess.DEVNULL,
            stderr=sys.stderr,
        )

    def is_long_task_running_locked(self, state: Optional[Dict[str, Any]] = None) -> bool:
        """Return true only while a child sync/download process is actually active."""
        process = self.sync_process

        if process is not None and process.poll() is None:
            return True

        if any(
            self.is_playlist_task_running_locked(playlist_id)
            for playlist_id in list(self.sync_tasks.keys())
        ):
            return True

        return bool(
            state
            and state.get("status") == "syncing"
            and process is not None
        )

    def start_playlist_sync_task_locked(self, playlist_id: str, job_type: str = "single") -> bool:
        self.poll_playlist_task_locked(playlist_id)

        if self.is_playlist_task_running_locked(playlist_id):
            return False

        progress_path = str(create_progress_path())
        playlist_title = self.playlist_title(playlist_id)
        process = self.start_sync_process(["--sync-child", playlist_id, progress_path])
        message = "Syncing playlist..."
        task_state = {
            "jobType": job_type,
            "playlistId": playlist_id,
            "playlistIds": [playlist_id],
            "playlistTitle": playlist_title,
            "status": "syncing",
            "phase": "syncing",
            "current": 0,
            "total": 0,
            "currentTrack": "",
            "failedCount": 0,
            "message": message,
            "progressPath": progress_path,
            "playlists": {
                playlist_id: playlist_progress(
                    "syncing",
                    "syncing",
                    message=message,
                )
            },
        }
        self.sync_tasks[playlist_id] = {
            "process": process,
            "state": task_state,
            "refreshed": False,
        }
        return True

    def sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()

        if not playlist_id:
            raise ValueError("A playlist id is required.")

        with self.sync_lock:
            global_state, _should_refresh_global = self.poll_sync_process_locked()

            if self.sync_process is not None and self.sync_process.poll() is None:
                return {
                    "started": False,
                    "playlistId": playlist_id,
                    "message": "Sync all is already running.",
                }

            if not self.start_playlist_sync_task_locked(playlist_id):
                return {
                    "started": False,
                    "playlistId": playlist_id,
                    "message": "This playlist is already syncing.",
                }

            # Keep the global Sync All state idle if no global job is running.
            if global_state.get("jobType") == "all" and global_state.get("status") != "syncing":
                self.sync_state = {**self.sync_state, "status": "idle", "phase": "idle"}

        return {
            "started": True,
            "playlistId": playlist_id,
        }

    def download_missing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()

        if not playlist_id:
            raise ValueError("A playlist id is required.")

        with self.sync_lock:
            self.poll_sync_process_locked()

            if self.sync_process is not None and self.sync_process.poll() is None:
                return {
                    "started": False,
                    "playlistId": playlist_id,
                    "message": "Sync all is already running.",
                }

            self.poll_playlist_task_locked(playlist_id)

            if self.is_playlist_task_running_locked(playlist_id):
                return {
                    "started": False,
                    "playlistId": playlist_id,
                    "message": "This playlist is already syncing or downloading.",
                }

            progress_path = str(create_progress_path())
            playlist_title = self.playlist_title(playlist_id)
            process = self.start_sync_process(["--download-missing-child", playlist_id, progress_path])
            task_state = {
                "jobType": "download_missing",
                "playlistId": playlist_id,
                "playlistIds": [playlist_id],
                "playlistTitle": playlist_title,
                "status": "syncing",
                "phase": "downloading",
                "current": 0,
                "total": 0,
                "currentTrack": "",
                "failedCount": 0,
                "message": "Preparing downloads...",
                "progressPath": progress_path,
                "playlists": {
                    playlist_id: playlist_progress(
                        "syncing",
                        "downloading",
                        message="Preparing downloads...",
                    )
                },
            }
            self.sync_tasks[playlist_id] = {
                "process": process,
                "state": task_state,
                "refreshed": False,
            }

        return {
            "started": True,
            "playlistId": playlist_id,
        }

    def cancel_playlist_sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()

        if not playlist_id:
            raise ValueError("A playlist id is required.")

        with self.sync_lock:
            task = self.sync_tasks.get(playlist_id)

            if task is None:
                return {
                    "ok": False,
                    "playlistId": playlist_id,
                    "message": "No active sync for this playlist.",
                }

            state = self.merge_playlist_task_progress_locked(playlist_id) or {}
            process = task.get("process")

            if process is None or process.poll() is not None:
                return {
                    "ok": False,
                    "playlistId": playlist_id,
                    "message": "No active sync for this playlist.",
                }

            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

            task["process"] = None
            cancelled_state = {
                **state,
                "status": "cancelled",
                "phase": "cancelled",
                "currentTrack": "",
                "message": "Sync cancelled.",
            }
            playlists = cancelled_state.get("playlists") if isinstance(cancelled_state.get("playlists"), dict) else {}
            playlists[playlist_id] = {
                **(playlists.get(playlist_id) if isinstance(playlists.get(playlist_id), dict) else {}),
                "status": "cancelled",
                "phase": "cancelled",
                "currentTrack": "",
                "message": "Sync cancelled.",
            }
            cancelled_state["playlists"] = playlists
            task["state"] = cancelled_state
            task["refreshed"] = False
            write_progress(cancelled_state.get("progressPath"), cancelled_state)

        return {
            "ok": True,
            "playlistId": playlist_id,
            "message": "Sync cancelled.",
        }

    def cancel_sync_all(self, _payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.sync_lock:
            state = self.aggregate_sync_all_state_locked()
            running_playlist_ids = [
                playlist_id
                for playlist_id in state.get("playlistIds", [])
                if self.is_playlist_task_running_locked(playlist_id)
            ]

            if state.get("jobType") != "all" or not running_playlist_ids:
                return {
                    "ok": False,
                    "message": "No sync all is running.",
                }

            for playlist_id in running_playlist_ids:
                task = self.sync_tasks.get(playlist_id)
                if task is None:
                    continue

                task_state = self.merge_playlist_task_progress_locked(playlist_id) or {}
                process = task.get("process")

                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)

                playlists = task_state.get("playlists") if isinstance(task_state.get("playlists"), dict) else {}
                playlists[playlist_id] = {
                    **(playlists.get(playlist_id) if isinstance(playlists.get(playlist_id), dict) else {}),
                    "status": "cancelled",
                    "phase": "cancelled",
                    "currentTrack": "",
                    "message": "Sync all cancelled.",
                }
                task_state = {
                    **task_state,
                    "status": "cancelled",
                    "phase": "cancelled",
                    "currentTrack": "",
                    "message": "Sync all cancelled.",
                    "playlists": playlists,
                }
                task["process"] = None
                task["state"] = task_state
                task["refreshed"] = False
                write_progress(task_state.get("progressPath"), task_state)

            self.sync_state = {
                **self.aggregate_sync_all_state_locked(),
                "status": "cancelled",
                "phase": "cancelled",
                "message": "Sync all cancelled.",
            }

        return {
            "ok": True,
            "message": "Sync all cancelled.",
        }

    def delete_playlist(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()

        if not playlist_id:
            raise ValueError("A playlist id is required.")

        with self.sync_lock:
            state, should_refresh_manager = self.poll_sync_process_locked()
            should_refresh_manager = self.poll_playlist_tasks_locked() or should_refresh_manager

            if self.is_long_task_running_locked(state):
                return {
                    "ok": False,
                    "message": "Cannot remove playlist while a sync or download is running.",
                }

        self.refresh_after_completed_sync(should_refresh_manager)
        self.refresh_after_completed_playlist_tasks(should_refresh_manager)

        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                playlist = self.manager.get_playlist(playlist_id)

                if playlist is None:
                    return {
                        "ok": False,
                        "message": f"Playlist with ID {playlist_id} not found.",
                    }

                self.manager.remove_playlist(playlist_id)

        self.managers_loaded = False

        return {
            "ok": True,
            "message": "Playlist removed.",
        }

    def aggregate_sync_all_state_locked(self) -> Dict[str, Any]:
        playlist_ids = (
            self.sync_state.get("playlistIds")
            if isinstance(self.sync_state.get("playlistIds"), list)
            else []
        )

        if self.sync_state.get("jobType") != "all" or not playlist_ids:
            return {
                "jobType": None,
                "status": "idle",
                "phase": "idle",
                "playlistIds": [],
                "message": "",
                "playlists": {},
            }

        playlists: Dict[str, Any] = {}

        for playlist_id in playlist_ids:
            task_state = self.merge_playlist_task_progress_locked(playlist_id) or {}
            task_playlists = (
                task_state.get("playlists")
                if isinstance(task_state.get("playlists"), dict)
                else {}
            )
            playlist_state = (
                task_playlists.get(playlist_id)
                if isinstance(task_playlists.get(playlist_id), dict)
                else {}
            )
            playlists[playlist_id] = {
                "status": playlist_state.get("status", task_state.get("status", "idle")),
                "phase": playlist_state.get("phase", task_state.get("phase", "idle")),
                "current": playlist_state.get("current", task_state.get("current", 0)),
                "total": playlist_state.get("total", task_state.get("total", 0)),
                "currentTrack": playlist_state.get("currentTrack", task_state.get("currentTrack", "")),
                "failedCount": playlist_state.get("failedCount", task_state.get("failedCount", 0)),
                "message": playlist_state.get("message", task_state.get("message", "")),
            }

        statuses = [playlist.get("status") for playlist in playlists.values()]
        active_count = sum(
            1
            for playlist in playlists.values()
            if playlist.get("status") == "syncing"
            or playlist.get("phase") in {"syncing", "downloading"}
        )
        completed_count = sum(1 for status in statuses if status == "completed")
        cancelled_count = sum(1 for status in statuses if status == "cancelled")
        error_count = sum(1 for status in statuses if status == "error")

        if active_count:
            status = "syncing"
            phase = "syncing"
            message = "Syncing playlists..."
        elif cancelled_count == len(playlist_ids):
            status = "cancelled"
            phase = "cancelled"
            message = "Sync all cancelled."
        elif error_count == len(playlist_ids):
            status = "error"
            phase = "error"
            message = "Sync all failed."
        else:
            status = "completed"
            phase = "completed"
            message = "Sync all completed."

        return {
            **self.sync_state,
            "jobType": "all",
            "status": status,
            "phase": phase,
            "playlistIds": playlist_ids,
            "playlistId": None,
            "playlistTitle": "",
            "current": completed_count + cancelled_count + error_count,
            "total": len(playlist_ids),
            "currentTrack": "",
            "failedCount": error_count,
            "message": message,
            "playlistCurrent": completed_count + cancelled_count + error_count,
            "playlistTotal": len(playlist_ids),
            "playlists": playlists,
        }

    def sync_all(self, _payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_ids = self.playlist_ids()

        if not playlist_ids:
            return {
                "started": False,
                "playlistIds": [],
                "message": "No playlists to synchronize.",
            }

        with self.sync_lock:
            started_playlist_ids = []

            for playlist_id in playlist_ids:
                if self.start_playlist_sync_task_locked(playlist_id, job_type="all"):
                    started_playlist_ids.append(playlist_id)

            if not started_playlist_ids:
                return {
                    "started": False,
                    "playlistIds": [],
                    "message": "No playlist sync was started.",
                }

            self.sync_state = {
                "jobType": "all",
                "playlistId": None,
                "playlistIds": started_playlist_ids,
                "playlistTitle": "",
                "status": "syncing",
                "phase": "syncing",
                "current": 0,
                "total": len(started_playlist_ids),
                "currentTrack": "",
                "failedCount": 0,
                "message": "Syncing playlists...",
                "playlistCurrent": 0,
                "playlistTotal": len(started_playlist_ids),
                "progressPath": None,
                "playlists": {
                    playlist_id: (self.sync_tasks[playlist_id]["state"].get("playlists") or {}).get(
                        playlist_id,
                        playlist_progress("syncing", "syncing", message="Syncing playlist..."),
                    )
                    for playlist_id in started_playlist_ids
                },
            }

        return {
            "started": True,
            "playlistIds": started_playlist_ids,
        }

    def sync_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()

        if not playlist_id:
            raise ValueError("A playlist id is required.")

        with self.sync_lock:
            playlist_task_state, should_refresh_playlist = self.poll_playlist_task_locked(playlist_id)

            if playlist_task_state is not None:
                state = playlist_task_state
                playlists = state.get("playlists") if isinstance(state.get("playlists"), dict) else {}
                playlist_state = playlists.get(playlist_id) if isinstance(playlists.get(playlist_id), dict) else {}
            else:
                state, should_refresh_global = self.poll_sync_process_locked()
                job_type = state.get("jobType")
                playlist_ids = state.get("playlistIds") if isinstance(state.get("playlistIds"), list) else []
                matches_all = job_type == "all" and playlist_id in playlist_ids

                if not matches_all:
                    return {
                        "playlistId": playlist_id,
                        "status": "idle",
                        "message": "",
                    }

                should_refresh_playlist = should_refresh_global
                playlists = state.get("playlists") if isinstance(state.get("playlists"), dict) else {}
                playlist_state = playlists.get(playlist_id) if isinstance(playlists.get(playlist_id), dict) else {}

        if playlist_task_state is not None:
            self.refresh_after_completed_playlist_task(playlist_id, should_refresh_playlist)
        else:
            self.refresh_after_completed_sync(should_refresh_playlist)

        return {
            "playlistId": playlist_id,
            "jobType": state.get("jobType"),
            "playlistTitle": state.get("playlistTitle", ""),
            "status": playlist_state.get("status", state.get("status", "idle")),
            "phase": playlist_state.get("phase", state.get("phase", "idle")),
            "current": playlist_state.get("current", state.get("current", 0)),
            "total": playlist_state.get("total", state.get("total", 0)),
            "currentTrack": playlist_state.get("currentTrack", state.get("currentTrack", "")),
            "failedCount": playlist_state.get("failedCount", state.get("failedCount", 0)),
            "message": playlist_state.get("message", state.get("message", "")),
            "playlistCurrent": state.get("playlistCurrent"),
            "playlistTotal": state.get("playlistTotal"),
            "playlists": playlists,
        }

    def sync_all_status(self, _payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.sync_lock:
            should_refresh_manager = self.poll_playlist_tasks_locked()
            state = self.aggregate_sync_all_state_locked()
            self.sync_state = state

            if state.get("jobType") != "all":
                return {
                    "status": "idle",
                    "playlistIds": [],
                    "message": "",
                }

        self.refresh_after_completed_playlist_tasks(should_refresh_manager)

        playlist_ids = state.get("playlistIds") if isinstance(state.get("playlistIds"), list) else []
        return {
            "jobType": state.get("jobType"),
            "status": state.get("status", "idle"),
            "playlistIds": playlist_ids,
            "playlistId": state.get("playlistId"),
            "playlistTitle": state.get("playlistTitle", ""),
            "phase": state.get("phase", "idle"),
            "current": state.get("current", 0),
            "total": state.get("total", 0),
            "currentTrack": state.get("currentTrack", ""),
            "failedCount": state.get("failedCount", 0),
            "message": state.get("message", ""),
            "playlistCurrent": state.get("playlistCurrent"),
            "playlistTotal": state.get("playlistTotal"),
            "playlists": state.get("playlists") if isinstance(state.get("playlists"), dict) else {},
        }

    def sync_tasks_status(self, _payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.sync_lock:
            should_refresh_manager = self.poll_playlist_tasks_locked()
            sync_all_state = self.aggregate_sync_all_state_locked()
            self.sync_state = sync_all_state if sync_all_state.get("jobType") == "all" else self.sync_state
            playlists: Dict[str, Any] = {}

            for playlist_id in list(self.sync_tasks.keys()):
                task_state = self.merge_playlist_task_progress_locked(playlist_id) or {}
                task_playlists = (
                    task_state.get("playlists")
                    if isinstance(task_state.get("playlists"), dict)
                    else {}
                )
                playlist_state = (
                    task_playlists.get(playlist_id)
                    if isinstance(task_playlists.get(playlist_id), dict)
                    else {}
                )
                playlists[playlist_id] = {
                    "playlistId": playlist_id,
                    "jobType": task_state.get("jobType"),
                    "playlistTitle": task_state.get("playlistTitle", ""),
                    "status": playlist_state.get("status", task_state.get("status", "idle")),
                    "phase": playlist_state.get("phase", task_state.get("phase", "idle")),
                    "current": playlist_state.get("current", task_state.get("current", 0)),
                    "total": playlist_state.get("total", task_state.get("total", 0)),
                    "currentTrack": playlist_state.get("currentTrack", task_state.get("currentTrack", "")),
                    "failedCount": playlist_state.get("failedCount", task_state.get("failedCount", 0)),
                    "message": playlist_state.get("message", task_state.get("message", "")),
                }

        self.refresh_after_completed_playlist_tasks(should_refresh_manager)

        return {
            "playlists": playlists,
            "syncAll": sync_all_state if sync_all_state.get("jobType") == "all" else None,
        }

    def handle(self, command: str, payload: Dict[str, Any]) -> Any:
        if command == "detect":
            return self.detect(payload)

        if command == "preview":
            return self.preview(payload)

        if command == "list":
            return self.list()

        if command == "playlist_details":
            return self.playlist_details(payload)

        if command == "add":
            return self.add(payload)

        if command == "sync":
            return self.sync(payload)

        if command == "download_missing":
            return self.download_missing(payload)

        if command == "cancel_playlist_sync":
            return self.cancel_playlist_sync(payload)

        if command == "cancel_sync_all":
            return self.cancel_sync_all(payload)

        if command == "delete_playlist":
            return self.delete_playlist(payload)

        if command == "sync_status":
            return self.sync_status(payload)

        if command == "sync_all":
            return self.sync_all(payload)

        if command == "sync_all_status":
            return self.sync_all_status(payload)

        if command == "sync_tasks_status":
            return self.sync_tasks_status(payload)

        raise ValueError(f"Unknown command: {command}")


def read_request(line: str) -> Dict[str, Any]:
    request = json.loads(line)

    if not isinstance(request, dict):
        raise ValueError("Request must be a JSON object.")

    return request


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--sync-child":
        progress_path = sys.argv[3] if len(sys.argv) >= 4 else None
        return run_sync_child(sys.argv[2], progress_path)

    if len(sys.argv) >= 2 and sys.argv[1] == "--sync-all-child":
        progress_path = sys.argv[2] if len(sys.argv) >= 3 else None
        return run_sync_all_child(progress_path)

    if len(sys.argv) >= 3 and sys.argv[1] == "--download-missing-child":
        progress_path = sys.argv[3] if len(sys.argv) >= 4 else None
        return run_download_missing_child(sys.argv[2], progress_path)

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
