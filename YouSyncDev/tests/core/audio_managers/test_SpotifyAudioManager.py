import os
import pytest
from threading import Lock
from core.audio_managers.SpotifyAudioManager import SpotifyAudioManager
import eyed3

NORMAL_SONG_URL         = "https://open.spotify.com/intl-fr/track/4hpnImImsCtXv6N3o5aC5x"
URL_SPECIAL_CHAR_TITLE  = "https://open.spotify.com/intl-fr/track/0Lm01zD4ApfOubhJhd8nOo"
URL_SPECIAL_CHAR_ALBUM  = "https://open.spotify.com/intl-fr/track/3ABj19BelXElJ4x4UGbjJc"
URL_SPECIAL_CHAR_ARTIST = "https://open.spotify.com/intl-fr/track/6jHWCqsNu6VzspiMP38kvt"


@pytest.fixture
def temp_path():
    path = os.path.join("tests", "temp_files")
    os.makedirs(path, exist_ok=True)
    return path

def test_download_normal(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_SpotifyAudioManager.json")

        manager = SpotifyAudioManager(
            url=NORMAL_SONG_URL,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.path_to_save_audio_with_title)
        audio = eyed3.load(manager.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None

        assert audio.tag.title == "Run"
        assert audio.tag.artist == "Omay"
        assert audio.tag.album == "Space Island"
    finally:
        if manager:
            manager.delete()

def test_download_title_special_chars(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_SpotifyAudioManager.json")

        manager = SpotifyAudioManager(
            url=URL_SPECIAL_CHAR_TITLE,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.path_to_save_audio_with_title)
        audio = eyed3.load(manager.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None

        assert manager.title == "* * * * *"
        assert manager.video_title == "track_0Lm01zD4ApfOubhJhd8nOo"
        assert audio.tag.title == "* * * * *"
    finally:
        if manager:
            manager.delete()

def test_download_album_special_chars(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_SpotifyAudioManager.json")

        manager = SpotifyAudioManager(
            url=URL_SPECIAL_CHAR_ALBUM,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.path_to_save_audio_with_title)
        audio = eyed3.load(manager.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None

        assert manager.title == "L'apprentie sorcière !"
        assert manager.video_title == "L'apprentie sorcière !"
        assert audio.tag.title == "L'apprentie sorcière !"
        assert audio.tag.album == "!"

        manager.delete()
    finally:
        if manager:
            manager.delete()


def test_download_artist_special_chars(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_SpotifyAudioManager.json")

        manager = SpotifyAudioManager(
            url=URL_SPECIAL_CHAR_ARTIST,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.path_to_save_audio_with_title)
        audio = eyed3.load(manager.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None

        assert audio.tag.artist == "BU$HI"

        manager.delete()
    finally:
        if manager:
            manager.delete()