import os
import json
import pytest
from threading import Lock
from core.storage.AudioDataStore import AudioDataStore

@pytest.fixture
def temp_store(tmp_path):
    filepath = tmp_path / "audio_data.json"
    return AudioDataStore(str(filepath), Lock()), str(filepath)

def test_file_creation(temp_store):
    store, filepath = temp_store
    assert os.path.exists(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data == {"audios": []}

def test_update_audio_adds_new_entry(temp_store):
    store, _ = temp_store
    audio = {"url": "abc", "title": "Test"}
    store.update_audio(audio)
    result = store.get_audio("abc")
    assert result["title"] == "Test"

def test_update_audio_overwrites_existing(temp_store):
    store, _ = temp_store
    store.update_audio({"url": "abc", "title": "Old"})
    store.update_audio({"url": "abc", "title": "New"})
    result = store.get_audio("abc")
    assert result["title"] == "New"

def test_get_audio_returns_none_for_missing(temp_store):
    store, _ = temp_store
    assert store.get_audio("notfound") is None

def test_remove_audio_deletes_entry(temp_store):
    store, _ = temp_store
    store.update_audio({"url": "abc", "title": "Test"})
    assert store.get_audio("abc") is not None
    store.remove_audio("abc")
    assert store.get_audio("abc") is None

def test_save_all_and_load_all(temp_store):
    store, _ = temp_store
    audios = [
        {"url": "a1", "title": "A"},
        {"url": "a2", "title": "B"},
    ]
    store.save_all(audios)
    result = store.load_all()
    assert len(result) == 2
    assert result[0]["url"] == "a1"
