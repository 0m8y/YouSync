import json
import os
from typing import List, Optional
from threading import Lock

from core.storage.AudioMetadata import AudioMetadata

class AudioDataStore:
    def __init__(self, filepath: str, lock: Lock):
        self.filepath = filepath
        self.lock = lock
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump({"audios": []}, f)

    def load_all(self) -> List[AudioMetadata]:
        with self.lock:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [AudioMetadata.from_dict(d) for d in data.get("audios", [])]
            except Exception:
                return []

    def save_all(self, audios: List[AudioMetadata]) -> None:
        with self.lock:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"audios": [a.to_dict() for a in audios]}, f, indent=4)

    def get_audio(self, url: str) -> Optional[AudioMetadata]:
        return next((a for a in self.load_all() if a.url == url), None)

    def update_audio(self, updated: AudioMetadata) -> None:
        data = self.load_all()
        for i, audio in enumerate(data):
            if audio.url == updated.url:
                data[i] = updated
                self.save_all(data)
                return
        data.append(updated)
        self.save_all(data)

    def remove_audio(self, url: str) -> None:
        data = self.load_all()
        data = [a for a in data if a.url != url]
        self.save_all(data)
