import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "desktop" / "python" / "yousync_bridge.py"

spec = importlib.util.spec_from_file_location("yousync_bridge", BRIDGE_PATH)
bridge = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(bridge)

from core.utils import get_deezer_playlist_id, get_deezer_playlist_tracks


URL_DEEZER_PLAYLIST = "https://www.deezer.com/fr/playlist/2506597284"


def test_deezer_playlist_url_parsing():
    assert get_deezer_playlist_id("https://www.deezer.com/fr/playlist/2506597284") == "2506597284"
    assert get_deezer_playlist_id("https://www.deezer.com/playlist/2506597284") == "2506597284"
    assert get_deezer_playlist_id("https://www.deezer.com/fr/playlist/2506597284?utm_source=test") == "2506597284"


def test_deezer_preview_uses_api_metadata():
    result = bridge.preview_playlist({"url": URL_DEEZER_PLAYLIST})

    assert result.get("supported") is True
    assert result.get("platform") == "deezer"
    assert result.get("tracks") == 237
    assert result.get("title")
    assert result.get("coverUrl")


def test_deezer_api_pagination_returns_target_playlist_tracks():
    tracks = get_deezer_playlist_tracks("2506597284")
    ids = [track["id"] for track in tracks]

    assert len(tracks) == 237
    assert len(set(ids)) == 237

    for track in tracks:
        assert track["url"].startswith("https://www.deezer.com/track/")
        assert track["title"]
        assert track["artists"]
        assert track["album"] is not None
        assert track["cover"]
        assert isinstance(track["duration"], int)


def test_deezer_preview_does_not_import_selenium():
    before_modules = set(sys.modules.keys())

    result = bridge.preview_playlist({"url": URL_DEEZER_PLAYLIST})

    imported_modules = set(sys.modules.keys()) - before_modules

    assert result.get("supported") is True
    assert result.get("platform") == "deezer"
    assert not any(name == "selenium" or name.startswith("selenium.") for name in imported_modules)
    assert not any(name.startswith("core.playlist_managers") for name in imported_modules)
