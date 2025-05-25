import json
import os
from typing import Dict, List, Any
from threading import Lock

class AudioDataStore:
    def __init__(self, filepath: str, lock: Lock):
        self.filepath = filepath
        self.lock = lock
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump({"audios": []}, f)

    def load_all(self) -> List[Dict[str, Any]]:
        with self.lock:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("audios", [])
            except Exception:
                return []

    def save_all(self, audios: List[Dict[str, Any]]) -> None:
        with self.lock:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"audios": audios}, f, indent=4)

    def get_audio(self, url: str) -> Dict[str, Any] | None:
        return next((audio for audio in self.load_all() if audio["url"] == url), None)

    def update_audio(self, updated: Dict[str, Any]) -> None:
        data = self.load_all()
        for i, audio in enumerate(data):
            if audio["url"] == updated["url"]:
                data[i] = updated
                self.save_all(data)
                return
        data.append(updated)
        self.save_all(data)

    def remove_audio(self, url: str) -> None:
        data = self.load_all()
        data = [a for a in data if a["url"] != url]
        self.save_all(data)
