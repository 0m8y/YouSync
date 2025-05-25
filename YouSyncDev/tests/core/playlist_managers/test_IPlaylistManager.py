from core.playlist_managers.IPlaylistManager import IPlaylistManager
from core.audio_managers.IAudioManager import IAudioManager
from core.storage.AudioMetadata import AudioMetadata
from core.storage.AudioDataStore import AudioDataStore

import os
import json
import shutil
import pytest
from typing import List
from threading import Lock
from unittest.mock import patch

def cleanup_dirs(*dirs):
    for path in dirs:
        if os.path.isdir(path):
            try:
                shutil.rmtree(path)
            except Exception as e:
                print(f"Erreur lors de la suppression de {path} : {e}")

class DummyAudioManager(IAudioManager):
    def __init__(self, url, path_to_save_audio, data_filepath, lock, id, video_title):
        self.lock = lock
        self.url = url
        self.id = id
        self.video_title = video_title
        self.path_to_save_audio = path_to_save_audio
        self.data_store = AudioDataStore(data_filepath, lock)
        self.metadata = AudioMetadata(
            url=url,
            path_to_save_audio_with_title=os.path.join(self.path_to_save_audio, f"{self.video_title}.mp3"),
            video_title=video_title,
            title=video_title, artist="", album="", image_url=""
        )
        self.data_store.update_audio(self.metadata)

    def download_audio(self): pass
    def add_metadata(self): pass
    def update_path(self, new_path, old_path): self.path_to_save_audio = new_path
    def update_data(self): self.data_store.update_audio(self.metadata)
    def get_url(self): return self.url
    def delete(self): self.data_store.remove_audio(self.url)

class DummyPlaylistManager(IPlaylistManager):
    def new_audio_manager(self, url: str) -> IAudioManager:
        return DummyAudioManager(
            url=url,
            path_to_save_audio=self.path_to_save_audio,
            data_filepath=self.playlist_data_filepath,
            lock=self.lock,
            id="dummy_id",
            video_title="dummy_video"
        )

    def get_video_urls(self) -> List[str]:
        return ["https://video.test/1", "https://video.test/2"]

    def get_playlist_title(self) -> str:
        return "Dummy Playlist"

    def download(self) -> None:
        pass

    def extract_image(self) -> str:
        return "https://lh3.googleusercontent.com/I2JsbpdeR8kiZx_mud5sQFwrN7IwUZ9vF_Fm4vz2qV1rHy56w3aMrILQ-xpdXMNutqitLcoRv4tI0hPH"

    def extract_video_id(self, url: str) -> str:
        return url.split("/")[-1]

@pytest.fixture
def temp_path():
    path = os.path.join("tests", "temp_files")
    os.makedirs(path, exist_ok=True)
    return path

# Tests

def test_playlist_json_created(temp_path):
    try:
        manager = DummyPlaylistManager("https://playlist.test", temp_path, "dummy_playlist_id")
        assert os.path.exists(manager.playlist_data_filepath)
        with open(manager.playlist_data_filepath) as f:
            data = json.load(f)
            assert data["title"] == "Dummy Playlist"
    finally:
        cleanup_dirs(temp_path)

def test_update_path(temp_path):
    old_path = os.path.join(temp_path, "old")
    new_path = os.path.join(temp_path, "new")
    os.makedirs(os.path.join(old_path, ".yousync"), exist_ok=True)
    os.makedirs(os.path.join(new_path, ".yousync"), exist_ok=True)
    try:
        manager = DummyPlaylistManager("https://playlist.test", old_path, "dummy_id")
        manager.update_path(new_path)
        assert manager.path_to_save_audio == new_path
        assert new_path in manager.playlist_data_filepath
        assert os.path.exists(manager.playlist_data_filepath)
    finally:
        cleanup_dirs(old_path, new_path)

def test_save_playlist_data(temp_path):
    try:
        manager = DummyPlaylistManager("https://playlist.test", temp_path, "dummy_id")
        manager.save_playlist_data({
            "playlist_url": manager.playlist_url,
            "path_to_save_audio": manager.path_to_save_audio,
            "title": "Updated Title"
        })
        with open(manager.playlist_data_filepath) as f:
            data = json.load(f)
            assert data["title"] == "Updated Title"
    finally:
        cleanup_dirs(temp_path)

def test_get_audio_managers(temp_path):
    try:
        manager = DummyPlaylistManager("https://playlist.test", temp_path, "dummy_id")
        audio_managers = manager.get_audio_managers()
        assert all(isinstance(am, IAudioManager) for am in audio_managers)
    finally:
        cleanup_dirs(temp_path)

@patch("requests.get")
def test_download_cover_image(mock_get, temp_path):
    try:
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake image"
        manager = DummyPlaylistManager("https://playlist.test", temp_path, "dummy_id")
        manager.download_cover_image()
        assert os.path.exists(os.path.join(temp_path, ".yousync", "dummy_id.jpg"))
    finally:
        cleanup_dirs(temp_path)

@patch("requests.get")
def test_download_cover_image_invalid_url(mock_get, temp_path):
    try:
        mock_get.return_value.status_code = 404
        class ManagerWithBadImage(DummyPlaylistManager):
            def extract_image(self):
                return "https://invalid-url/image.jpg"
        manager = ManagerWithBadImage("https://playlist.test", temp_path, "dummy_id")
        manager.download_cover_image()  # Should fail silently
    finally:
        cleanup_dirs(temp_path)

def test_update_adds_and_removes_audio(temp_path):
    try:
        class UpdatingDummyPlaylist(DummyPlaylistManager):
            def get_video_urls(self): return ["https://video.test/2", "https://video.test/3"]
        manager = UpdatingDummyPlaylist("https://playlist.test", temp_path, "dummy_id")
        audio1 = manager.new_audio_manager("https://video.test/1")
        manager._IPlaylistManager__add_audio(audio1)
        manager.update()
        urls = [am.get_url() for am in manager.get_audio_managers()]
        assert "https://video.test/1" not in urls
        assert "https://video.test/3" in urls
    finally:
        cleanup_dirs(temp_path)

def test_add_and_remove_audio(temp_path):
    try:
        manager = DummyPlaylistManager("https://playlist.test", temp_path, "dummy_id")
        audio = manager.new_audio_manager("https://video.test/99")
        manager._IPlaylistManager__add_audio(audio)
        assert audio in manager.audio_managers
        manager._IPlaylistManager__remove_audio("https://video.test/99")
        assert audio not in manager.audio_managers
    finally:
        cleanup_dirs(temp_path)

def test_get_video_urls_from_json(temp_path):
    try:
        json_path = os.path.join(temp_path, ".yousync", "dummy_id.json")
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, "w") as f:
            json.dump({
                "playlist_url": "https://playlist.test",
                "path_to_save_audio": temp_path,
                "title": "Dummy Playlist",
                "audios": [
                    {"url": "https://video.test/1"},
                    {"url": "https://video.test/2"}
                ]
            }, f)
        manager = DummyPlaylistManager("https://playlist.test", temp_path, "dummy_id")
        urls = [am.get_url() for am in manager.get_audio_managers()]
        assert "https://video.test/1" in urls
        assert "https://video.test/2" in urls
    finally:
        cleanup_dirs(temp_path)
