import os
import json
import pytest
from threading import Lock
from core.audio_managers.YoutubeAudioManager import YoutubeAudioManager
from pathlib import Path
import eyed3

URL_WITH_MUSICINFO = "https://www.youtube.com/watch?v=lxd1b-abNJw&ab_channel=Omay-Topic"
URL_WITHOUT_MUSICINFO = "https://www.youtube.com/watch?v=nQjsfbGq_ng&ab_channel=Omay"
URL_INVALID = "https://www.youtube.com/watch?v=doesnotexist123"


@pytest.fixture
def temp_path():
    path = os.path.join("tests", "temp_files")
    os.makedirs(path, exist_ok=True)
    return path

def test_download_audio_with_music_info(temp_path):
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

    # Clean
    manager.delete()


def test_download_audio_without_music_info(temp_path):
    json_file = os.path.join(temp_path, "test_YoutubeAudioManager.json")

    manager = YoutubeAudioManager(
        url=URL_WITHOUT_MUSICINFO,
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

    # Clean
    manager.delete()


def test_download_invalid_video(temp_path):
    with pytest.raises(Exception):  # ou plus précisément `pytube.exceptions.VideoUnavailable`
        YoutubeAudioManager(
            url=URL_INVALID,
            path_to_save_audio=temp_path,
            data_filepath=os.path.join(temp_path, "yt.json"),
            lock=Lock()
        ).download()
