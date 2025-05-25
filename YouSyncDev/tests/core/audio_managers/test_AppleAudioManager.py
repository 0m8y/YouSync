import os
import pytest
from threading import Lock
from core.audio_managers.AppleAudioManager import AppleAudioManager
import eyed3

NORMAL_SONG_URL         = "https://music.apple.com/us/song/run/1766991039"
URL_SPECIAL_CHAR_TITLE  = "https://music.apple.com/us/song/1726637267"
URL_SPECIAL_CHAR_ALBUM  = "https://music.apple.com/fr/song/lapprentie-sorci%C3%A8re/1596501827"
URL_SPECIAL_CHAR_ARTIST = "https://music.apple.com/fr/song/obito/1604595119"


@pytest.fixture
def temp_path():
    path = os.path.join("tests", "temp_files")
    os.makedirs(path, exist_ok=True)
    return path

def test_download_normal(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_AppleAudioManager.json")

        manager = AppleAudioManager(
            url=NORMAL_SONG_URL,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.metadata.path_to_save_audio_with_title)
        audio = eyed3.load(manager.metadata.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None

        assert audio.tag.title == "Run"
        assert audio.tag.artist == "Omay"
        assert audio.tag.album == "Space Island - EP"
    finally:
        if manager:
            manager.delete()

def test_download_title_special_chars(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_AppleAudioManager.json")

        manager = AppleAudioManager(
            url=URL_SPECIAL_CHAR_TITLE,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.metadata.path_to_save_audio_with_title)
        audio = eyed3.load(manager.metadata.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None

        assert manager.metadata.title == "* * * * *"
        assert manager.metadata.video_title == "track_1726637267"
        assert audio.tag.title == "* * * * *"
    finally:
        if manager:
            manager.delete()

def test_download_album_special_chars(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_AppleAudioManager.json")

        manager = AppleAudioManager(
            url=URL_SPECIAL_CHAR_ALBUM,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.metadata.path_to_save_audio_with_title)
        audio = eyed3.load(manager.metadata.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None

        assert manager.metadata.title == "L'apprentie sorcière !"
        assert manager.metadata.video_title == "L'apprentie sorcière !"
        assert audio.tag.title == "L'apprentie sorcière !"
        assert audio.tag.album == "!"

        manager.delete()
    finally:
        if manager:
            manager.delete()


def test_download_artist_special_chars(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_AppleAudioManager.json")

        manager = AppleAudioManager(
            url=URL_SPECIAL_CHAR_ARTIST,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.metadata.path_to_save_audio_with_title)
        audio = eyed3.load(manager.metadata.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None

        assert audio.tag.artist == "BU$HI"

        manager.delete()
    finally:
        if manager:
            manager.delete()