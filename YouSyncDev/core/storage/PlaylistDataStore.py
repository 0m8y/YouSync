import json
import os
from threading import Lock
from typing import List

from core.storage.AudioMetadata import AudioMetadata
from core.storage.PlaylistData import PlaylistData

class PlaylistDataStore:
    def __init__(self, filepath: str, lock: Lock):
        self.filepath = filepath
        self.lock = lock
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "playlist_url": "",
                    "path_to_save_audio": "",
                    "title": "",
                    "audios": []
                }, f, indent=4)

    def load(self) -> PlaylistData:
        with self.lock:
            with open(self.filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)

            audios = [
                AudioMetadata.from_dict(a)
                for a in raw.get("audios", [])
            ]

            return PlaylistData(
                playlist_url=raw.get("playlist_url", ""),
                path_to_save_audio=raw.get("path_to_save_audio", ""),
                title=raw.get("title", ""),
                audios=audios
            )

    def save(self, playlist: PlaylistData):
        with self.lock:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except:
                raw = {}

            raw["playlist_url"] = playlist.playlist_url
            raw["path_to_save_audio"] = playlist.path_to_save_audio
            raw["title"] = playlist.title

            raw["audios"] = [a.to_dict() for a in playlist.audios]

            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(raw, f, indent=4)

    def add_audio(self, metadata: AudioMetadata):
        playlist = self.load()

        if not any(a.url == metadata.url for a in playlist.audios):
            playlist.audios.append(metadata)
            self.save(playlist)

    def remove_audio(self, url: str):
        playlist = self.load()
        playlist.audios = [a for a in playlist.audios if a.url != url]
        self.save(playlist)
