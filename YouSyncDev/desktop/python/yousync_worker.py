#!/usr/bin/env python3
import json
import os
import shutil
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


def run_redownload_track_child(playlist_id: str, track_index: int, progress_path: Optional[str] = None) -> int:
    """Redownload one track in an isolated Python process."""
    progress_state = {
        "jobType": "redownload_track",
        "playlistId": playlist_id,
        "playlistTitle": "",
        "status": "syncing",
        "phase": "downloading",
        "current": 0,
        "total": 1,
        "currentTrack": "",
        "failedCount": 0,
        "message": "Preparing track redownload...",
        "playlists": {},
    }

    try:
        bridge.ensure_project_root_on_path()

        with redirect_stdout(sys.stderr):
            from core.CentralManager import CentralManager

            manager = CentralManager("playlists.json")
            manager.instantiate_playlist_managers()
            playlist = manager.get_playlist(playlist_id)
            playlist_title = playlist.title if playlist else ""
            progress_state["playlistTitle"] = playlist_title

            if playlist is None:
                result = {
                    "ok": False,
                    "playlistId": playlist_id,
                    "trackIndex": track_index,
                    "message": f"Playlist with ID {playlist_id} not found.",
                }
                write_playlist_progress(
                    progress_path,
                    progress_state,
                    playlist_id,
                    playlist_progress(
                        "error",
                        "error",
                        current=0,
                        total=1,
                        failed_count=1,
                        message=result["message"],
                    ),
                )
                write_child_result(result)
                return 1

            audio_managers = manager.get_audio_managers(playlist_id) or []

            if track_index < 1 or track_index > len(audio_managers):
                result = {
                    "ok": False,
                    "playlistId": playlist_id,
                    "trackIndex": track_index,
                    "message": "Track not found.",
                }
                write_playlist_progress(
                    progress_path,
                    progress_state,
                    playlist_id,
                    playlist_progress(
                        "error",
                        "error",
                        current=0,
                        total=1,
                        failed_count=1,
                        message=result["message"],
                    ),
                )
                write_child_result(result)
                return 1

            audio_manager = audio_managers[track_index - 1]
            title = audio_title(audio_manager)
            write_playlist_progress(
                progress_path,
                progress_state,
                playlist_id,
                playlist_progress(
                    "syncing",
                    "downloading",
                    current=0,
                    total=1,
                    current_track=title,
                    message="Redownloading track...",
                ),
            )

            metadata = getattr(audio_manager, "metadata", None)

            if metadata is not None:
                if hasattr(metadata, "is_downloaded"):
                    metadata.is_downloaded = False
                if hasattr(metadata, "metadata_updated"):
                    metadata.metadata_updated = False

                try:
                    audio_manager.update_data()
                except Exception as exc:
                    log(f"failed to persist redownload reset for {playlist_id} / {title}: {exc}")

            audio_manager.download()

        message = "Track redownloaded."
        write_playlist_progress(
            progress_path,
            progress_state,
            playlist_id,
            playlist_progress(
                "completed",
                "completed",
                current=1,
                total=1,
                current_track=title,
                message=message,
            ),
        )
        write_child_result(
            {
                "ok": True,
                "playlistId": playlist_id,
                "trackIndex": track_index,
                "message": message,
            }
        )
        return 0
    except Exception as exc:
        message = "Track redownload failed."
        write_playlist_progress(
            progress_path,
            progress_state,
            playlist_id,
            playlist_progress(
                "error",
                "error",
                current=0,
                total=1,
                failed_count=1,
                message=message,
            ),
        )
        write_child_result(
            {
                "ok": False,
                "playlistId": playlist_id,
                "trackIndex": track_index,
                "message": message,
            }
        )
        log(f"redownload track child crashed for {playlist_id} / {track_index}: {exc}")
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

    def fallback_playlist_summary(self, playlist: Any, status_label: str = "Folder missing") -> Dict[str, Any]:
        url = str(getattr(playlist, "url", "") or "")
        detection = bridge.detect_platform(url)
        platform = detection.get("platform") if isinstance(detection, dict) else "unknown"

        if platform not in {"youtube", "spotify", "apple", "soundcloud"}:
            platform = "unknown"

        return {
            "id": str(getattr(playlist, "id", "") or ""),
            "title": str(getattr(playlist, "title", "") or "Untitled playlist"),
            "path": str(getattr(playlist, "path", "") or ""),
            "platform": platform,
            "tracks": 0,
            "coverPath": None,
            "sourceUrl": url or None,
            "status": {
                "type": "missing",
                "label": status_label,
            },
            "lastSynced": str(getattr(playlist, "last_update", "") or "Never"),
        }

    def safe_map_core_playlist(self, playlist: Any, cover_wait_seconds: float = 0.0) -> Dict[str, Any]:
        try:
            return bridge.map_core_playlist(playlist, cover_wait_seconds=cover_wait_seconds)
        except Exception as exc:
            log(f"failed to map playlist {getattr(playlist, 'id', '')}: {exc}")
            return self.fallback_playlist_summary(playlist)

    def list(self) -> Any:
        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                playlists = self.manager.list_playlists()

        mapped_playlists = []
        for playlist in playlists:
            mapped_playlist = self.safe_map_core_playlist(playlist)
            mapped_playlist["sourceUrl"] = getattr(playlist, "url", None)

            if self.is_playlist_path_missing(playlist):
                mapped_playlist["status"] = {
                    "type": "missing",
                    "label": "Folder missing",
                }

            mapped_playlists.append(mapped_playlist)

        return mapped_playlists

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

        def first_text(audio: Dict[str, Any], keys: List[str]) -> str:
            for key in keys:
                value = audio.get(key)
                if value is None:
                    continue

                text = str(value).strip()
                if text:
                    return text

            return ""

        def audio_title(audio: Dict[str, Any]) -> str:
            title = first_text(audio, ["title", "video_title", "name"])
            if title:
                return title

            file_path = audio_local_path(audio)
            if file_path:
                return Path(file_path).stem

            return "—"

        def audio_local_path(audio: Dict[str, Any]) -> str:
            return first_text(
                audio,
                [
                    "path_to_save_audio_with_title",
                    "path_to_save_audio",
                    "local_path",
                    "localPath",
                    "file_path",
                    "filePath",
                    "path",
                ],
            )

        def audio_source_url(audio: Dict[str, Any]) -> str:
            return first_text(
                audio,
                [
                    "url",
                    "source_url",
                    "sourceUrl",
                    "webpage_url",
                    "webpageUrl",
                    "video_url",
                    "videoUrl",
                ],
            )

        def audio_file_exists(file_path: str) -> bool:
            try:
                return bool(file_path) and Path(file_path).is_file()
            except OSError:
                return False

        def audio_is_downloaded(audio: Dict[str, Any]) -> bool:
            local_path = audio_local_path(audio)
            return audio.get("is_downloaded") is True and audio_file_exists(local_path)

        def audio_status(audio: Dict[str, Any]) -> str:
            if bridge.audio_has_error(audio):
                return "Error"

            is_downloaded = audio_is_downloaded(audio)
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
            source_url = audio_source_url(raw_audio)
            local_path = audio_local_path(raw_audio)
            tracks.append(
                {
                    "index": index,
                    "title": audio_title(raw_audio),
                    "artist": str(raw_audio.get("artist") or "").strip() or "—",
                    "duration": str(duration).strip() if duration else "—",
                    "status": audio_status(raw_audio),
                    "url": source_url or None,
                    "sourceUrl": source_url or None,
                    "localPath": local_path or None,
                    "isDownloaded": audio_is_downloaded(raw_audio),
                }
            )

        summary = self.safe_map_core_playlist(playlist)

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
                self.safe_map_core_playlist(playlist, cover_wait_seconds=1.0)
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

    def playlist_storage_folder(self, playlist: Any) -> Optional[Path]:
        raw_path = str(getattr(playlist, "path", "") or "").strip()

        if not raw_path:
            return None

        playlist_path = Path(raw_path).expanduser()

        if playlist_path.name == ".yousync":
            return playlist_path

        parent = playlist_path.parent

        if parent.name == ".yousync":
            return parent

        return parent / ".yousync"

    def playlist_root_folder(self, playlist: Any) -> Optional[Path]:
        storage_folder = self.playlist_storage_folder(playlist)

        if storage_folder is None:
            return None

        if storage_folder.name == ".yousync" and storage_folder.parent != storage_folder:
            return storage_folder.parent

        return storage_folder

    def is_playlist_path_missing(self, playlist: Any) -> bool:
        storage_folder = self.playlist_storage_folder(playlist)

        if storage_folder is None:
            return False

        try:
            return not storage_folder.exists()
        except OSError:
            return True

    def map_broken_playlist(self, playlist: Any) -> Dict[str, Any]:
        summary = self.safe_map_core_playlist(playlist)
        root_folder = self.playlist_root_folder(playlist)
        storage_folder = self.playlist_storage_folder(playlist)

        summary["sourceUrl"] = getattr(playlist, "url", None)
        summary["missingPath"] = str(root_folder) if root_folder is not None else str(getattr(playlist, "path", "") or "")
        summary["missingCachePath"] = str(storage_folder) if storage_folder is not None else str(getattr(playlist, "path", "") or "")
        return summary

    def list_missing_playlists(self, _payload: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                playlists = self.manager.list_playlists()

        return [
            self.map_broken_playlist(playlist)
            for playlist in playlists
            if self.is_playlist_path_missing(playlist)
        ]

    def update_playlist_folder(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(payload.get("playlist_id") or payload.get("playlistId") or "").strip()
        folder = str(payload.get("folder", "")).strip()

        if not playlist_id:
            return {
                "ok": False,
                "message": "A playlist id is required.",
                "updatedPlaylistIds": [],
                "playlists": [],
            }

        if not folder:
            return {
                "ok": False,
                "message": "A folder is required.",
                "updatedPlaylistIds": [],
                "playlists": [],
            }

        folder_path = Path(folder).expanduser()

        if folder_path.name == ".yousync":
            folder_path = folder_path.parent

        if not folder_path.exists():
            return {
                "ok": False,
                "message": "The selected folder does not exist.",
                "updatedPlaylistIds": [],
                "playlists": [],
            }

        if not folder_path.is_dir():
            return {
                "ok": False,
                "message": "The selected path is not a folder.",
                "updatedPlaylistIds": [],
                "playlists": [],
            }

        with self.sync_lock:
            state, should_refresh_manager = self.poll_sync_process_locked()
            should_refresh_manager = self.poll_playlist_tasks_locked() or should_refresh_manager

            if self.is_long_task_running_locked(state):
                return {
                    "ok": False,
                    "message": "Cannot recover a playlist while a sync or download is running.",
                    "updatedPlaylistIds": [],
                    "playlists": [],
                }

        self.refresh_after_completed_sync(should_refresh_manager)
        self.refresh_after_completed_playlist_tasks(should_refresh_manager)

        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                if not hasattr(self.manager, "update_path"):
                    return {
                        "ok": False,
                        "message": "Playlist folder recovery is not available in this build.",
                        "updatedPlaylistIds": [],
                        "playlists": [],
                    }

                playlists_before = self.manager.list_playlists()
                target_playlist = next(
                    (playlist for playlist in playlists_before if playlist.id == playlist_id),
                    None,
                )

                if target_playlist is None:
                    return {
                        "ok": False,
                        "message": "Playlist not found.",
                        "updatedPlaylistIds": [],
                        "playlists": [],
                    }

                old_root = self.playlist_root_folder(target_playlist)
                old_roots_by_id: Dict[str, Optional[Path]] = {}
                old_storage_folders_by_id: Dict[str, Optional[Path]] = {}
                target_ids: List[str] = []

                for playlist in playlists_before:
                    if playlist.id == playlist_id:
                        old_roots_by_id[playlist.id] = self.playlist_root_folder(playlist)
                        old_storage_folders_by_id[playlist.id] = self.playlist_storage_folder(playlist)
                        target_ids.append(playlist.id)
                        continue

                    if old_root is None:
                        continue

                    other_root = self.playlist_root_folder(playlist)

                    if other_root == old_root and self.is_playlist_path_missing(playlist):
                        old_roots_by_id[playlist.id] = other_root
                        old_storage_folders_by_id[playlist.id] = self.playlist_storage_folder(playlist)
                        target_ids.append(playlist.id)

                updated_ids: List[str] = []

                for target_id in target_ids:
                    try:
                        updated = self.manager.update_path(str(folder_path), target_id)
                    except Exception as exc:
                        log(f"failed to update path for {target_id}: {exc}")
                        updated = False

                    if bool(updated):
                        cache_path = folder_path / ".yousync" / f"{target_id}.json"
                        self.rewrite_playlist_cache_paths(
                            cache_path,
                            old_roots_by_id.get(target_id),
                            old_storage_folders_by_id.get(target_id),
                            folder_path,
                        )
                        updated_ids.append(target_id)

        if updated_ids:
            self.refresh_manager()
            with redirect_stdout(sys.stderr):
                with self.manager_lock:
                    playlists_after = self.manager.list_playlists()

            updated_playlists = [
                self.safe_map_core_playlist(playlist, cover_wait_seconds=1.0)
                for playlist in playlists_after
                if playlist.id in set(updated_ids)
            ]
            count = len(updated_ids)
            return {
                "ok": True,
                "message": "Recovered " + str(count) + " playlist" + ("s" if count > 1 else "") + ".",
                "updatedPlaylistIds": updated_ids,
                "playlists": updated_playlists,
            }

        return {
            "ok": False,
            "message": "No matching YouSync data was found in the selected folder.",
            "updatedPlaylistIds": [],
            "playlists": [],
        }

    def recover_existing_playlist(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        folder = str(payload.get("folder", "")).strip()

        if not folder:
            return {
                "ok": False,
                "message": "A folder is required.",
            }

        folder_path = Path(folder).expanduser()

        if folder_path.name == ".yousync":
            folder_path = folder_path.parent

        if not folder_path.exists():
            return {
                "ok": False,
                "message": "The selected folder does not exist.",
            }

        if not folder_path.is_dir():
            return {
                "ok": False,
                "message": "The selected path is not a folder.",
            }

        with self.sync_lock:
            state, should_refresh_manager = self.poll_sync_process_locked()
            should_refresh_manager = self.poll_playlist_tasks_locked() or should_refresh_manager

            if self.is_long_task_running_locked(state):
                return {
                    "ok": False,
                    "message": "Cannot recover a playlist while a sync or download is running.",
                }

        self.refresh_after_completed_sync(should_refresh_manager)
        self.refresh_after_completed_playlist_tasks(should_refresh_manager)

        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                if not hasattr(self.manager, "add_existing_playlists"):
                    return {
                        "ok": False,
                        "message": "Playlist recovery is not available in this build.",
                    }

                before_playlists = self.manager.list_playlists()
                before_ids = {playlist.id for playlist in before_playlists}

                result = self.manager.add_existing_playlists(str(folder_path))
                playlists = self.manager.list_playlists()

        self.managers_loaded = False

        recovered_playlists = [
            self.safe_map_core_playlist(playlist, cover_wait_seconds=1.0)
            for playlist in playlists
            if playlist.id not in before_ids
        ]

        if recovered_playlists:
            count = len(recovered_playlists)
            return {
                "ok": True,
                "message": "Recovered " + str(count) + " playlist" + ("s" if count > 1 else "") + ".",
                "playlists": recovered_playlists,
            }

        message = result if isinstance(result, str) and result.strip() else "No existing YouSync playlist was found in the selected folder."

        return {
            "ok": False,
            "message": message,
            "playlists": [],
        }

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

    def redownload_track(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()

        try:
            track_index = int(payload.get("track_index") or payload.get("trackIndex") or 0)
        except (TypeError, ValueError):
            track_index = 0

        if not playlist_id:
            raise ValueError("A playlist id is required.")

        if track_index < 1:
            raise ValueError("A valid track index is required.")

        with self.sync_lock:
            state, should_refresh_manager = self.poll_sync_process_locked()
            should_refresh_manager = self.poll_playlist_tasks_locked() or should_refresh_manager

            global_process_running = self.sync_process is not None and self.sync_process.poll() is None
            if global_process_running or self.is_playlist_task_running_locked(playlist_id):
                return {
                    "ok": False,
                    "started": False,
                    "playlistId": playlist_id,
                    "trackIndex": track_index,
                    "message": "Cannot redownload this track while this playlist is syncing or downloading.",
                }

        self.refresh_after_completed_sync(should_refresh_manager)
        self.refresh_after_completed_playlist_tasks(should_refresh_manager)

        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                playlist = self.manager.get_playlist(playlist_id)

                if playlist is None:
                    return {
                        "ok": False,
                        "started": False,
                        "playlistId": playlist_id,
                        "trackIndex": track_index,
                        "message": f"Playlist with ID {playlist_id} not found.",
                    }

                cache = bridge.read_playlist_cache(getattr(playlist, "path", ""))
                audios = cache.get("audios", []) if isinstance(cache, dict) else []

                if not isinstance(audios, list) or track_index > len(audios):
                    return {
                        "ok": False,
                        "started": False,
                        "playlistId": playlist_id,
                        "trackIndex": track_index,
                        "message": "Track not found.",
                    }

        with self.sync_lock:
            global_process_running = self.sync_process is not None and self.sync_process.poll() is None
            if global_process_running or self.is_playlist_task_running_locked(playlist_id):
                return {
                    "ok": False,
                    "started": False,
                    "playlistId": playlist_id,
                    "trackIndex": track_index,
                    "message": "This playlist is already syncing or downloading.",
                }

            progress_path = str(create_progress_path())
            playlist_title = self.playlist_title(playlist_id)
            process = self.start_sync_process([
                "--redownload-track-child",
                playlist_id,
                str(track_index),
                progress_path,
            ])
            task_state = {
                "jobType": "redownload_track",
                "playlistId": playlist_id,
                "playlistIds": [playlist_id],
                "playlistTitle": playlist_title,
                "status": "syncing",
                "phase": "downloading",
                "current": 0,
                "total": 1,
                "currentTrack": "",
                "failedCount": 0,
                "message": "Preparing track redownload...",
                "progressPath": progress_path,
                "playlists": {
                    playlist_id: playlist_progress(
                        "syncing",
                        "downloading",
                        current=0,
                        total=1,
                        message="Preparing track redownload...",
                    )
                },
            }
            self.sync_tasks[playlist_id] = {
                "process": process,
                "state": task_state,
                "refreshed": False,
            }

        return {
            "ok": True,
            "started": True,
            "playlistId": playlist_id,
            "trackIndex": track_index,
            "message": "Track redownload started.",
        }

    def normalize_file_path(self, raw_path: str, root_folder: Optional[Path]) -> Optional[Path]:
        text = str(raw_path or "").strip()

        if not text or text.startswith("http://") or text.startswith("https://"):
            return None

        path = Path(text).expanduser()

        if not path.is_absolute() and root_folder is not None:
            path = root_folder / path

        return path

    def playlist_metadata_files(self, playlist: Any) -> List[Path]:
        files: List[Path] = []
        seen: set[str] = set()
        storage_folder = self.playlist_storage_folder(playlist)
        playlist_id = str(getattr(playlist, "id", "") or "").strip()
        raw_playlist_path = str(getattr(playlist, "path", "") or "").strip()

        def add_file(path: Optional[Path]) -> None:
            if path is None:
                return

            try:
                key = str(path.expanduser().resolve(strict=False))
            except OSError:
                key = str(path.expanduser())

            if key in seen:
                return

            seen.add(key)
            files.append(path.expanduser())

        if raw_playlist_path:
            add_file(Path(raw_playlist_path))

        if storage_folder is not None and playlist_id:
            for suffix in (".json", ".jpg", ".jpeg", ".png", ".webp"):
                add_file(storage_folder / f"{playlist_id}{suffix}")

        return files

    def collect_playlist_audio_files(
        self,
        playlist: Any,
        cache: Optional[Dict[str, Any]] = None,
    ) -> List[Path]:
        if cache is None:
            cache = bridge.read_playlist_cache(getattr(playlist, "path", ""))

        root_folder = self.playlist_root_folder(playlist)
        audios = cache.get("audios", []) if isinstance(cache, dict) else []
        files: List[Path] = []
        seen: set[str] = set()
        path_keys = [
            "path_to_save_audio_with_title",
            "path_to_save_audio",
            "local_path",
            "localPath",
            "file_path",
            "filePath",
            "path",
        ]

        if not isinstance(audios, list):
            return files

        for audio in audios:
            if not isinstance(audio, dict):
                continue

            for key in path_keys:
                value = audio.get(key)

                if not isinstance(value, str):
                    continue

                file_path = self.normalize_file_path(value, root_folder)

                if file_path is None:
                    continue

                try:
                    normalized_key = str(file_path.resolve(strict=False))
                except OSError:
                    normalized_key = str(file_path)

                if normalized_key in seen:
                    continue

                seen.add(normalized_key)
                files.append(file_path)

        return files

    def playlist_audio_move_plan(
        self,
        playlist: Any,
        cache: Dict[str, Any],
        new_root: Path,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        root_folder = self.playlist_root_folder(playlist)
        audios = cache.get("audios", []) if isinstance(cache, dict) else []
        moves: List[Dict[str, Any]] = []
        seen_sources: set[str] = set()
        seen_destinations: set[str] = set()
        path_keys = [
            "path_to_save_audio_with_title",
            "path_to_save_audio_without_title",
            "local_path",
            "localPath",
            "file_path",
            "filePath",
            "path",
        ]

        if not isinstance(audios, list):
            return moves, None

        def reserve_destination(source: Path) -> Path:
            candidate = new_root / source.name
            index = 1

            while True:
                try:
                    destination_key = str(candidate.resolve(strict=False))
                except OSError:
                    destination_key = str(candidate)

                if destination_key not in seen_destinations and not candidate.exists():
                    seen_destinations.add(destination_key)
                    return candidate

                candidate = new_root / f"{source.stem} ({index}){source.suffix}"
                index += 1

        for audio_index, audio in enumerate(audios):
            if not isinstance(audio, dict):
                continue

            source: Optional[Path] = None

            for key in path_keys:
                value = audio.get(key)

                if not isinstance(value, str) or not value.strip():
                    continue

                candidate = self.normalize_file_path(value, root_folder)

                if candidate is None or not candidate.name or not candidate.suffix:
                    continue

                source = candidate
                break

            if source is None:
                continue

            try:
                source_key = str(source.resolve(strict=False))
            except OSError:
                source_key = str(source)

            if source_key in seen_sources:
                continue

            destination = reserve_destination(source)

            try:
                if source.resolve(strict=False) == destination.resolve(strict=False):
                    seen_sources.add(source_key)
                    continue
            except OSError:
                pass

            seen_sources.add(source_key)
            moves.append(
                {
                    "audioIndex": audio_index,
                    "source": source,
                    "destination": destination,
                }
            )

        return moves, None

    def move_playlist_audio_files(self, moves: List[Dict[str, Any]]) -> int:
        moved_count = 0

        for move in moves:
            source = move.get("source")
            destination = move.get("destination")

            if not isinstance(source, Path) or not isinstance(destination, Path):
                continue

            try:
                log(f"Moving audio: {source} -> {destination}")

                if not source.exists():
                    if destination.exists():
                        moved_count += 1
                        log("Audio moved successfully")
                    else:
                        log(f"Audio source missing: {source}")
                    continue

                if destination.exists():
                    destination = self.unique_destination_path(destination)
                    move["destination"] = destination
                    log(f"Audio destination exists, using: {destination}")

                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                moved_count += 1
                log("Audio moved successfully")
            except Exception as exc:
                raise RuntimeError(f'Could not move "{source.name}".') from exc

        return moved_count

    def unique_destination_path(self, destination: Path) -> Path:
        if not destination.exists():
            return destination

        index = 1
        while True:
            candidate = destination.parent / f"{destination.stem} ({index}){destination.suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def relative_destination_for_file(
        self,
        file_path: Path,
        old_root: Optional[Path],
        new_root: Path,
    ) -> Path:
        if old_root is None:
            return new_root / file_path.name

        try:
            relative_path = file_path.resolve(strict=False).relative_to(old_root.resolve(strict=False))
            return new_root / relative_path
        except ValueError:
            return new_root / file_path.name

    def copy_playlist_file(self, source: Path, destination: Path) -> bool:
        if not source.exists() or not source.is_file():
            return False

        try:
            if source.resolve(strict=False) == destination.resolve(strict=False):
                return False
        except OSError:
            pass

        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            if destination.is_file():
                destination.unlink()
            else:
                raise ValueError(f"Destination already exists and is not a file: {destination}")

        shutil.copy2(source, destination)
        return True

    def remove_file_if_exists(self, file_path: Path) -> bool:
        try:
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                return True
        except OSError as exc:
            log(f"failed to remove file {file_path}: {exc}")

        return False

    def replace_path_strings(self, value: Any, replacements: List[Tuple[str, str]]) -> Any:
        if isinstance(value, str):
            next_value = value

            for old_value, new_value in replacements:
                if old_value:
                    next_value = next_value.replace(old_value, new_value)

            return next_value

        if isinstance(value, list):
            return [self.replace_path_strings(item, replacements) for item in value]

        if isinstance(value, dict):
            return {
                key: self.replace_path_strings(item, replacements)
                for key, item in value.items()
            }

        return value

    def rewrite_playlist_cache_paths(
        self,
        cache_path: Path,
        old_root: Optional[Path],
        old_storage_folder: Optional[Path],
        new_root: Path,
        audio_moves: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        replacements: List[Tuple[str, str]] = []

        if old_root is not None:
            replacements.append((str(old_root), str(new_root)))
            replacements.append((old_root.as_posix(), new_root.as_posix()))

        if old_storage_folder is not None:
            new_storage_folder = new_root / ".yousync"
            replacements.append((str(old_storage_folder), str(new_storage_folder)))
            replacements.append((old_storage_folder.as_posix(), new_storage_folder.as_posix()))

        audio_path_keys = [
            "path_to_save_audio_with_title",
            "path_to_save_audio_without_title",
            "path_to_save_audio",
            "local_path",
            "localPath",
            "file_path",
            "filePath",
            "path",
        ]
        file_path_keys = {
            "path_to_save_audio_with_title",
            "path_to_save_audio_without_title",
            "local_path",
            "localPath",
            "file_path",
            "filePath",
            "path",
        }
        destination_by_audio_index: Dict[int, Path] = {}

        for move in audio_moves or []:
            audio_index = move.get("audioIndex")
            destination = move.get("destination")

            if isinstance(audio_index, int) and isinstance(destination, Path):
                destination_by_audio_index[audio_index] = destination

        def rewrite_audio_path(raw_value: Any, key: str, audio_index: int) -> Any:
            if not isinstance(raw_value, str):
                return raw_value

            value = raw_value.strip()
            if not value:
                return raw_value

            explicit_destination = destination_by_audio_index.get(audio_index)
            if explicit_destination is not None:
                if key in file_path_keys:
                    return str(explicit_destination)

                return str(new_root)

            replaced = self.replace_path_strings(value, replacements)
            if replaced != value:
                return replaced

            path = Path(value)
            if path.name and path.suffix:
                return str(new_root / path.name)

            return str(new_root)

        try:
            with open(cache_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return

            data = self.replace_path_strings(data, replacements)
            data["path_to_save_audio"] = str(new_root)

            audios = data.get("audios")
            if isinstance(audios, list):
                for audio_index, audio in enumerate(audios):
                    if not isinstance(audio, dict):
                        continue

                    for key in audio_path_keys:
                        if key in audio:
                            audio[key] = rewrite_audio_path(audio[key], key, audio_index)

            tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)

            os.replace(tmp_path, cache_path)
        except Exception as exc:
            log(f"failed to rewrite playlist cache paths {cache_path}: {exc}")

    def rewrite_moved_playlist_cache(
        self,
        target_storage_folder: Path,
        playlist_id: str,
        old_root: Optional[Path],
        old_storage_folder: Optional[Path],
        new_root: Path,
    ) -> None:
        replacements: List[Tuple[str, str]] = []

        if old_root is not None:
            replacements.append((str(old_root), str(new_root)))
            replacements.append((old_root.as_posix(), new_root.as_posix()))

        if old_storage_folder is not None:
            new_storage_folder = new_root / ".yousync"
            replacements.append((str(old_storage_folder), str(new_storage_folder)))
            replacements.append((old_storage_folder.as_posix(), new_storage_folder.as_posix()))

        if not replacements:
            return

        for json_path in target_storage_folder.glob(f"{playlist_id}*.json"):
            try:
                with open(json_path, "r", encoding="utf-8") as file:
                    data = json.load(file)

                data = self.replace_path_strings(data, replacements)

                with open(json_path, "w", encoding="utf-8") as file:
                    json.dump(data, file, ensure_ascii=False, indent=2)
            except Exception as exc:
                log(f"failed to rewrite moved cache {json_path}: {exc}")

    def move_playlist_folder(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()
        folder = str(payload.get("folder", "")).strip()

        if not playlist_id:
            return {"ok": False, "message": "A playlist id is required."}

        if not folder:
            return {"ok": False, "message": "A destination folder is required."}

        destination_root = Path(folder).expanduser()

        if destination_root.name == ".yousync":
            destination_root = destination_root.parent

        if destination_root.exists() and not destination_root.is_dir():
            return {"ok": False, "message": "The selected path is not a folder."}

        with self.sync_lock:
            state, should_refresh_manager = self.poll_sync_process_locked()
            should_refresh_manager = self.poll_playlist_tasks_locked() or should_refresh_manager

            global_process_running = self.sync_process is not None and self.sync_process.poll() is None
            if global_process_running or self.is_playlist_task_running_locked(playlist_id):
                return {
                    "ok": False,
                    "message": "Cannot change location while this playlist is syncing.",
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

                if not hasattr(self.manager, "update_path"):
                    return {
                        "ok": False,
                        "message": "Changing playlist folder is not available in this build.",
                    }

                old_root = self.playlist_root_folder(playlist)
                old_storage_folder = self.playlist_storage_folder(playlist)
                metadata_files = self.playlist_metadata_files(playlist)
                playlist_cache = bridge.read_playlist_cache(getattr(playlist, "path", ""))

        if old_root is not None:
            try:
                if old_root.resolve(strict=False) == destination_root.resolve(strict=False):
                    return {"ok": True, "message": "Playlist is already in this folder."}
            except OSError:
                pass

            try:
                destination_root.resolve(strict=False).relative_to(old_root.resolve(strict=False))
                return {
                    "ok": False,
                    "message": "Choose a destination outside the current playlist folder.",
                }
            except ValueError:
                pass

        target_storage_folder = destination_root / ".yousync"
        copied_sources: List[Path] = []

        try:
            destination_root.mkdir(parents=True, exist_ok=True)
            target_storage_folder.mkdir(parents=True, exist_ok=True)

            audio_moves, conflict_message = self.playlist_audio_move_plan(
                playlist,
                playlist_cache,
                destination_root,
            )

            if conflict_message:
                return {"ok": False, "message": conflict_message}

            for metadata_file in metadata_files:
                destination_file = target_storage_folder / metadata_file.name
                if self.copy_playlist_file(metadata_file, destination_file):
                    copied_sources.append(metadata_file)

            moved_audio_count = self.move_playlist_audio_files(audio_moves)

            with redirect_stdout(sys.stderr):
                with self.manager_lock:
                    updated = self.manager.update_path(str(destination_root), playlist_id)
                    playlists = self.manager.list_playlists()

            if not bool(updated):
                return {
                    "ok": False,
                    "message": "No matching YouSync data was found in the selected folder.",
                }

            self.rewrite_playlist_cache_paths(
                target_storage_folder / f"{playlist_id}.json",
                old_root,
                old_storage_folder,
                destination_root,
                audio_moves,
            )
            log("Playlist location changed")

            deleted_count = 0
            for source in copied_sources:
                deleted_count += 1 if self.remove_file_if_exists(source) else 0

            self.refresh_manager()
            with redirect_stdout(sys.stderr):
                with self.manager_lock:
                    playlists = self.manager.list_playlists()

            playlist_summary = next(
                (
                    self.safe_map_core_playlist(playlist, cover_wait_seconds=1.0)
                    for playlist in playlists
                    if playlist.id == playlist_id
                ),
                None,
            )

            return {
                "ok": True,
                "message": "Playlist destination folder updated.",
                "playlist": playlist_summary,
                "movedFiles": deleted_count,
                "movedAudioFiles": moved_audio_count,
            }
        except Exception as exc:
            log(f"failed to move playlist folder for {playlist_id}: {exc}")
            return {
                "ok": False,
                "message": "Playlist folder could not be changed.",
            }

    def delete_playlist(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = str(
            payload.get("playlist_id") or payload.get("playlistId") or ""
        ).strip()
        delete_local_files = bool(
            payload.get("delete_local_files") or payload.get("deleteLocalFiles")
        )

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

        files_to_delete: List[Path] = []

        with redirect_stdout(sys.stderr):
            with self.manager_lock:
                playlist = self.manager.get_playlist(playlist_id)

                if playlist is None:
                    return {
                        "ok": False,
                        "message": f"Playlist with ID {playlist_id} not found.",
                    }

                if delete_local_files:
                    cache = bridge.read_playlist_cache(getattr(playlist, "path", ""))
                    files_to_delete.extend(self.collect_playlist_audio_files(playlist, cache))
                    files_to_delete.extend(self.playlist_metadata_files(playlist))

                self.manager.remove_playlist(playlist_id)

        deleted_count = 0

        if delete_local_files:
            seen: set[str] = set()
            unique_files: List[Path] = []

            for file_path in files_to_delete:
                try:
                    key = str(file_path.resolve(strict=False))
                except OSError:
                    key = str(file_path)

                if key in seen:
                    continue

                seen.add(key)
                unique_files.append(file_path)

            for file_path in unique_files:
                deleted_count += 1 if self.remove_file_if_exists(file_path) else 0

        self.managers_loaded = False

        if delete_local_files:
            return {
                "ok": True,
                "message": "Playlist removed and local files deleted.",
                "deletedLocalFiles": deleted_count,
            }

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

        if command == "list_missing_playlists":
            return self.list_missing_playlists(payload)

        if command == "update_playlist_folder":
            return self.update_playlist_folder(payload)

        if command == "move_playlist_folder":
            return self.move_playlist_folder(payload)

        if command == "playlist_details":
            return self.playlist_details(payload)

        if command == "add":
            return self.add(payload)

        if command == "recover_existing_playlist":
            return self.recover_existing_playlist(payload)

        if command == "sync":
            return self.sync(payload)

        if command == "download_missing":
            return self.download_missing(payload)

        if command == "cancel_playlist_sync":
            return self.cancel_playlist_sync(payload)

        if command == "cancel_sync_all":
            return self.cancel_sync_all(payload)

        if command == "redownload_track":
            return self.redownload_track(payload)

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

    if len(sys.argv) >= 4 and sys.argv[1] == "--redownload-track-child":
        try:
            track_index = int(sys.argv[3])
        except (TypeError, ValueError):
            track_index = 0
        progress_path = sys.argv[4] if len(sys.argv) >= 5 else None
        return run_redownload_track_child(sys.argv[2], track_index, progress_path)

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
