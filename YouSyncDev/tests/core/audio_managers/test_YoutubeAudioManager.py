import os
import json
import pytest
from threading import Lock
from core.audio_managers.YoutubeAudioManager import YoutubeAudioManager
from pathlib import Path
import eyed3

URL_WITH_MUSICINFO = "https://www.youtube.com/watch?v=lxd1b-abNJw&ab_channel=Omay-Topic"
URL_WITHOUT_MUSICINFO_WITH_TIMECODE = "https://www.youtube.com/watch?v=nQjsfbGq_ng&ab_channel=Omay"
URL_INVALID = "https://www.youtube.com/watch?v=doesnotexist123"
URL_SPECIAL_CHAR_TITLE = "https://www.youtube.com/watch?v=zFr-5SV4jzk&ab_channel=PLK-Topic"
URL_SPECIAL_CHAR_ALBUM = "https://www.youtube.com/watch?v=4XbgdNarD8Y&ab_channel=menaceSantana-Topic"
URL_SPECIAL_CHAR_ARTIST = "https://www.youtube.com/watch?v=T3CJKo4cNQA&ab_channel=SaturnCitizen"
@pytest.fixture
def temp_path():
    path = os.path.join("tests", "temp_files")
    os.makedirs(path, exist_ok=True)
    return path

def test_download_with_music_info(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_YoutubeAudioManager.json")

        manager = YoutubeAudioManager(
            url=URL_WITH_MUSICINFO,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.path_to_save_audio_with_title)
        audio = eyed3.load(manager.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None
        assert "googleusercontent.com" in manager.image_url.lower()

        assert audio.tag.title.strip().lower() == "run"
        assert audio.tag.artist.strip().lower() == "omay"
        assert audio.tag.album.strip().lower() == "space island"

        print("🎧 MP3 title:", audio.tag.title)
    finally:
        if manager:
            manager.delete()


def test_download_without_music_info(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_YoutubeAudioManager.json")

        manager = YoutubeAudioManager(
            url=URL_WITHOUT_MUSICINFO_WITH_TIMECODE,
            path_to_save_audio=temp_path,
            data_filepath=json_file,
            lock=Lock()
        )

        manager.download()

        assert os.path.exists(manager.path_to_save_audio_with_title)
        audio = eyed3.load(manager.path_to_save_audio_with_title)
        assert audio is not None
        assert audio.tag is not None

        assert "i.ytimg.com" in manager.image_url.lower()
        assert not audio.tag.title
        assert not audio.tag.artist
        assert not audio.tag.album
    finally:
        if manager:
            manager.delete()


def test_download_invalid_video(temp_path):
    with pytest.raises(Exception):  # ou pytube.exceptions.VideoUnavailable
        YoutubeAudioManager(
            url=URL_INVALID,
            path_to_save_audio=temp_path,
            data_filepath=os.path.join(temp_path, "yt.json"),
            lock=Lock()
        ).download()


def test_download_title_special_chars(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_YoutubeAudioManager.json")

        manager = YoutubeAudioManager(
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
        assert manager.video_title == "track_zFr-5SV4jzk"
        assert audio.tag.title == "* * * * *"
    finally:
        if manager:
            manager.delete()

def test_download_album_special_chars(temp_path):
    manager = None
    try:
        json_file = os.path.join(temp_path, "test_YoutubeAudioManager.json")

        manager = YoutubeAudioManager(
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
        json_file = os.path.join(temp_path, "test_YoutubeAudioManager.json")

        manager = YoutubeAudioManager(
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

        assert audio.tag.artist == "Bu$hi"

        manager.delete()
    finally:
        if manager:
            manager.delete()