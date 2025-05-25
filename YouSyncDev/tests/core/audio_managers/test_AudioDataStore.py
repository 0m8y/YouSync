import os
import json
import pytest
from threading import Lock

from core.storage.AudioDataStore import AudioDataStore
from core.storage.AudioMetadata import AudioMetadata

@pytest.fixture
def temp_store(tmp_path):
    filepath = tmp_path / "audio_data.json"
    store = AudioDataStore(str(filepath), Lock())
    return store, str(filepath)

def test_file_creation(temp_store):
    store, filepath = temp_store
    assert os.path.exists(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data == {"audios": []}

def test_update_audio_adds_new_entry(temp_store):
    store, _ = temp_store
    audio = AudioMetadata(url="abc", title="Test", video_title="Test", path_to_save_audio_with_title="dummy.mp3")
    store.update_audio(audio)
    result = store.get_audio("abc")
    assert result is not None
    assert result.title == "Test"

def test_update_audio_overwrites_existing(temp_store):
    store, _ = temp_store
    audio_old = AudioMetadata(url="abc", title="Old", video_title="Old", path_to_save_audio_with_title="Old.mp3")
    audio_new = AudioMetadata(url="abc", title="New", video_title="New", path_to_save_audio_with_title="New.mp3")
    store.update_audio(audio_old)
    store.update_audio(audio_new)
    result = store.get_audio("abc")
    assert result is not None
    assert result.title == "New"

def test_get_audio_returns_none_for_missing(temp_store):
    store, _ = temp_store
    assert store.get_audio("notfound") is None

def test_remove_audio_deletes_entry(temp_store):
    store, _ = temp_store
    audio = AudioMetadata(url="abc", title="Test", video_title="Test", path_to_save_audio_with_title="Test.mp3")
    store.update_audio(audio)
    assert store.get_audio("abc") is not None
    store.remove_audio("abc")
    assert store.get_audio("abc") is None

def test_save_all_and_load_all(temp_store):
    store, _ = temp_store
    audios = [
        AudioMetadata(url="a1", title="A", video_title="A", path_to_save_audio_with_title="Test.mp3"),
        AudioMetadata(url="a2", title="B", video_title="B", path_to_save_audio_with_title="Test.mp3"),
    ]
    store.save_all(audios)
    result = store.load_all()
    assert len(result) == 2
    assert result[0].url == "a1"
    assert result[1].title == "B"
