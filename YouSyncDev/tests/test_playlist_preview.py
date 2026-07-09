import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "desktop" / "python" / "yousync_bridge.py"

spec = importlib.util.spec_from_file_location("yousync_bridge", BRIDGE_PATH)
bridge = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(bridge)


URL_YOUTUBE_PLAYLIST = "https://www.youtube.com/playlist?list=PLsOoDQgfBdd17erA74nVTQE4g7O1tjW6k"
URL_YOUTUBE_REGRESSION = "https://www.youtube.com/playlist?list=PLsOoDQgfBdd2LWKtXBXZvyFjMQQktogAz"
URL_SPOTIFY_PLAYLIST = "https://open.spotify.com/playlist/5UkD1s2ZTwRvzCFz84t3aF"
URL_SPOTIFY_RADIO_PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1E4lSd84kB4j3i"
URL_SPOTIFY_NORMAL_PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1DWYRdd9noPgqB"
URL_APPLE_PLAYLIST = "https://music.apple.com/fr/playlist/yousync-test/pl.u-38oWjr3tqpA3GX?l=en-GB"


EXPECTED_PREVIEWS = {
    URL_YOUTUBE_PLAYLIST: {
        "platform": "youtube",
        "tracks": 5,
        "title": "YouSync ! é è @ $ € % £ # - /",
    },
    URL_SPOTIFY_PLAYLIST: {
        "platform": "spotify",
        "tracks": 4,
        "title": "YouSync Test",
    },
    URL_APPLE_PLAYLIST: {
        "platform": "apple",
        "tracks": 4,
        "title": "YouSync Test",
    },
}


INVALID_URLS = [
    {
        "url": "",
        "platform": "unknown",
    },
    {
        "url": "not a playlist url",
        "platform": "unknown",
    },
    {
        "url": "https://example.com/playlist",
        "platform": "unknown",
    },
    {
        "url": "https://www.youtube.com/watch?v=lxd1b-abNJw",
        "platform": "youtube",
    },
    {
        "url": "https://open.spotify.com/track/4hpnImImsCtXv6N3o5aC5x",
        "platform": "spotify",
    },
    {
        "url": "https://music.apple.com/us/library/playlist/private-playlist",
        "platform": "apple",
    },
    {
        "url": "https://soundcloud.com/omay/sets/private-playlist",
        "platform": "soundcloud",
    },
]


def assert_valid_preview(result: dict[str, Any], expected: dict[str, Any]) -> None:
    assert isinstance(result, dict)

    assert result.get("supported") is True
    assert result.get("platform") == expected["platform"]
    assert result.get("title") == expected["title"]
    assert result.get("tracks") == expected["tracks"]

    cover_url = result.get("coverUrl")
    cover_path = result.get("coverPath")
    assert cover_url or cover_path

    if cover_url is not None:
        assert isinstance(cover_url, str)
        assert cover_url.startswith(("http://", "https://"))
        assert len(cover_url) > 15

    if cover_path is not None:
        assert isinstance(cover_path, str)
        assert cover_path.strip() != ""


@pytest.mark.parametrize("url", EXPECTED_PREVIEWS.keys())
def test_preview_supported_playlist_urls_return_exact_expected_metadata(url: str):
    result = bridge.preview_playlist({"url": url})
    assert_valid_preview(result, EXPECTED_PREVIEWS[url])


@pytest.mark.parametrize("case", INVALID_URLS)
def test_preview_invalid_or_unsupported_urls_return_clean_error(case: dict[str, str]):
    result = bridge.preview_playlist({"url": case["url"]})

    assert isinstance(result, dict)
    assert result.get("supported") is False
    assert result.get("platform") == case["platform"]
    assert result.get("message") or result.get("reason")

    assert not result.get("title")
    assert not result.get("coverUrl")
    assert not result.get("coverPath")
    assert result.get("tracks") in (None, 0)


def test_preview_non_existing_youtube_playlist_returns_clean_error():
    result = bridge.preview_playlist(
        {"url": "https://www.youtube.com/playlist?list=PLsOoDQgfBdd2LWKtXBXZvyFjMQQktogAzx"}
    )

    assert isinstance(result, dict)
    assert result.get("supported") is False
    assert result.get("platform") == "youtube"
    assert result.get("message") or result.get("reason")

    assert not result.get("title")
    assert not result.get("coverUrl")
    assert not result.get("coverPath")
    assert result.get("tracks") in (None, 0)


@pytest.mark.parametrize("url", EXPECTED_PREVIEWS.keys())
def test_preview_cli_stdout_is_valid_json_with_exact_expected_metadata(url: str):
    completed = subprocess.run(
        [sys.executable, str(BRIDGE_PATH), "preview"],
        input=json.dumps({"url": url}),
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )

    assert completed.returncode == 0
    assert "Traceback" not in completed.stdout
    assert "Traceback" not in completed.stderr

    result = json.loads(completed.stdout)
    assert_valid_preview(result, EXPECTED_PREVIEWS[url])


def test_preview_cli_soundcloud_is_clean_unsupported_response():
    completed = subprocess.run(
        [sys.executable, str(BRIDGE_PATH), "preview"],
        input=json.dumps({"url": "https://soundcloud.com/omay/sets/private-playlist"}),
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )

    assert completed.returncode == 0
    assert "Traceback" not in completed.stdout
    assert "Traceback" not in completed.stderr

    result = json.loads(completed.stdout)
    assert result.get("supported") is False
    assert result.get("platform") == "soundcloud"
    assert result.get("message") or result.get("reason")


def test_preview_does_not_import_selenium_or_playlist_managers():
    before_modules = set(sys.modules.keys())

    result = bridge.preview_playlist({"url": URL_YOUTUBE_PLAYLIST})

    after_modules = set(sys.modules.keys())
    imported_modules = after_modules - before_modules

    assert_valid_preview(result, EXPECTED_PREVIEWS[URL_YOUTUBE_PLAYLIST])
    assert "selenium" not in sys.modules
    assert not any(name.startswith("core.playlist_managers") for name in imported_modules)


@pytest.mark.parametrize(
    ("url", "expected_title", "minimum_tracks"),
    [
        (URL_SPOTIFY_RADIO_PLAYLIST, "Franglish Radio", 50),
        (URL_SPOTIFY_NORMAL_PLAYLIST, "Feel Good", 60),
    ],
)
def test_spotify_preview_uses_embed_track_list_for_radio_and_normal_playlists(
    url: str,
    expected_title: str,
    minimum_tracks: int,
):
    result = bridge.preview_playlist({"url": url})

    assert isinstance(result, dict)
    assert result.get("supported") is True
    assert result.get("platform") == "spotify"
    assert result.get("title") == expected_title
    assert isinstance(result.get("tracks"), int)
    assert result["tracks"] >= minimum_tracks
    assert result.get("coverUrl")
    assert "selenium" not in sys.modules


def test_spotify_embed_track_list_has_no_duplicates_or_playlist_id_false_positive():
    from core.utils import get_spotify_playlist_data_from_embed, get_spotify_playlist_id

    data = get_spotify_playlist_data_from_embed(URL_SPOTIFY_RADIO_PLAYLIST)
    playlist_id = get_spotify_playlist_id(URL_SPOTIFY_RADIO_PLAYLIST)
    urls = data.get("track_urls")

    assert isinstance(urls, list)
    assert len(urls) == 50
    assert len(urls) == len(set(urls))
    assert all("/track/" in url for url in urls)
    assert all(playlist_id not in url for url in urls)
