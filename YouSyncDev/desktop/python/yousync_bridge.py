#!/usr/bin/env python3
import json
import os
import re
import signal
import sys
import time
import types
from contextlib import redirect_stdout
from html import unescape
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urljoin, urlparse
from urllib.request import Request, urlopen


MOCK_PLAYLISTS = [
    {
        "id": "todays-top-hits",
        "title": "Today's Top Hits",
        "path": "/Users/alex/Music/YouSync/Spotify",
        "platform": "spotify",
        "tracks": 50,
        "status": {"type": "synced", "label": "Synced"},
        "lastSynced": "2 min ago",
    },
    {
        "id": "lofi-beats",
        "title": "Lo-fi Beats to Study To",
        "path": "/Users/alex/Music/YouSync/YouTube",
        "platform": "youtube",
        "tracks": 128,
        "status": {"type": "syncing", "label": "62%", "progress": 62},
        "lastSynced": "Syncing...",
    },
    {
        "id": "workout-mix",
        "title": "Workout Mix 2024",
        "path": "/Users/alex/Music/YouSync/Apple",
        "platform": "apple",
        "tracks": 34,
        "status": {"type": "error", "label": "3 failed"},
        "lastSynced": "1 hr ago",
    },
    {
        "id": "chill-vibes",
        "title": "Chill Vibes",
        "path": "/Users/alex/Music/YouSync/Spotify",
        "platform": "spotify",
        "tracks": 82,
        "status": {"type": "synced", "label": "Synced"},
        "lastSynced": "Yesterday",
    },
    {
        "id": "jazz-essentials",
        "title": "Jazz Essentials",
        "path": "/Users/alex/Music/YouSync/YouTube",
        "platform": "youtube",
        "tracks": 200,
        "status": {"type": "stale", "label": "Out of date"},
        "lastSynced": "7 days ago",
    },
    {
        "id": "deep-focus",
        "title": "Deep Focus",
        "path": "/Users/alex/Music/YouSync/Spotify",
        "platform": "spotify",
        "tracks": 61,
        "status": {"type": "synced", "label": "Synced"},
        "lastSynced": "3 days ago",
    },
]


def install_core_import_stubs() -> None:
    stub_specs = {
        "core.audio_managers.IAudioManager": "IAudioManager",
        "core.playlist_managers.YoutubePlaylistManager": "YoutubePlaylistManager",
        "core.playlist_managers.SpotifyPlaylistManager": "SpotifyPlaylistManager",
        "core.playlist_managers.ApplePlaylistManager": "ApplePlaylistManager",
    }

    for module_name, class_name in stub_specs.items():
        if module_name in sys.modules:
            continue

        module = types.ModuleType(module_name)
        setattr(module, class_name, type(class_name, (), {}))
        sys.modules[module_name] = module


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_project_root_on_path() -> None:
    root = str(project_root())

    if root not in sys.path:
        sys.path.insert(0, root)


def detect_platform_id(url: str) -> str:
    detection = detect_platform(url)
    return detection["platform"] if detection["platform"] != "unknown" else "soundcloud"


def playlist_local_path(path: str) -> str:
    parent = os.path.dirname(path)

    if os.path.basename(parent) == ".yousync":
        return os.path.dirname(parent)

    return path


T = TypeVar("T")


class FileReadTimeout(Exception):
    pass


def with_file_timeout(operation: Callable[[], T], fallback: T) -> T:
    if not hasattr(signal, "SIGALRM"):
        try:
            return operation()
        except Exception:
            return fallback

    def handle_timeout(_signum: int, _frame: Any) -> None:
        raise FileReadTimeout()

    previous_handler = signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, 1.0)
    try:
        return operation()
    except Exception:
        return fallback
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def read_playlist_cache(path: str) -> Dict[str, Any]:
    def read() -> Dict[str, Any]:
        if not path or not os.path.isfile(path):
            return {}

        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    return with_file_timeout(read, {})


def cover_path_for_playlist(
    path: str,
    playlist_id: str,
    wait_seconds: float = 0.0,
) -> Optional[str]:
    def find_cover_once() -> Optional[str]:
        if not path or not playlist_id:
            return None

        cover_path = os.path.join(os.path.dirname(path), f"{playlist_id}.jpg")
        return cover_path if os.path.isfile(cover_path) else None

    if wait_seconds <= 0:
        return with_file_timeout(find_cover_once, None)

    deadline = time.monotonic() + wait_seconds

    while True:
        cover_path = with_file_timeout(find_cover_once, None)

        if cover_path or time.monotonic() >= deadline:
            return cover_path

        time.sleep(0.05)


def status_from_audios(
    audios: List[Dict[str, Any]],
    has_cover: bool,
    playlist_exists: bool,
) -> Dict[str, Any]:
    if not audios:
        if playlist_exists and has_cover:
            return {"type": "stale", "label": "Not synced yet"}

        return {"type": "empty", "label": "Empty"}

    completed = [
        audio
        for audio in audios
        if audio.get("is_downloaded") is True and audio.get("metadata_updated") is True
    ]

    if len(completed) == len(audios):
        return {"type": "synced", "label": "Synced"}

    return {
        "type": "error",
        "label": f"{len(audios) - len(completed)} missing",
    }


def playlist_summary(
    playlist_id: str,
    url: str,
    path: str,
    title: str,
    last_synced: str,
    cover_wait_seconds: float = 0.0,
) -> Dict[str, Any]:
    cache = read_playlist_cache(path)
    audios = cache.get("audios", [])

    if not isinstance(audios, list):
        audios = []

    cover_path = cover_path_for_playlist(path, playlist_id, cover_wait_seconds)

    return {
        "id": playlist_id,
        "title": cache.get("title") or title,
        "path": cache.get("path_to_save_audio") or playlist_local_path(path),
        "platform": detect_platform_id(cache.get("playlist_url") or url),
        "tracks": len(audios),
        "coverPath": cover_path,
        "status": status_from_audios(
            audios,
            has_cover=cover_path is not None,
            playlist_exists=bool(playlist_id and path),
        ),
        "lastSynced": last_synced,
    }


def map_core_playlist(playlist: Any, cover_wait_seconds: float = 0.0) -> Dict[str, Any]:
    return playlist_summary(
        playlist_id=playlist.id,
        url=playlist.url,
        path=playlist.path,
        title=playlist.title,
        last_synced=playlist.last_update,
        cover_wait_seconds=cover_wait_seconds,
    )


def map_raw_playlist(data: Dict[str, Any]) -> Dict[str, Any]:
    return playlist_summary(
        playlist_id=data.get("id", ""),
        url=data.get("url", ""),
        path=data.get("path", ""),
        title=data.get("title", ""),
        last_synced=data.get("last_update", ""),
    )


def list_core_playlists() -> Tuple[List[Dict[str, Any]], str]:
    root = project_root()
    ensure_project_root_on_path()
    install_core_import_stubs()

    try:
        from core.CentralManager import CentralManager

        with redirect_stdout(StringIO()):
            manager = CentralManager("playlists.json")
            playlists = manager.list_playlists()

        return [map_core_playlist(playlist) for playlist in playlists], "core"
    except Exception:
        playlists_file = root / "core" / "playlists.json"
        with playlists_file.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return [map_raw_playlist(playlist) for playlist in data.get("playlists", [])], "fallback"


def read_input() -> Dict[str, Any]:
    raw_input = sys.stdin.read().strip()
    if not raw_input:
        return {}
    return json.loads(raw_input)


def write_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":")))
    sys.stdout.flush()


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: Dict[str, str] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "title":
            self._in_title = True
            return

        if tag.lower() != "meta":
            return

        attributes = {
            key.lower(): value
            for key, value in attrs
            if key and value is not None
        }
        key = attributes.get("property") or attributes.get("name")
        content = attributes.get("content")

        if key and content:
            self.meta[key.lower()] = unescape(content.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        import requests

        response = requests.get(url, headers=headers, timeout=6)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return response.text
    except ImportError:
        request = Request(url, headers=headers)

        with urlopen(request, timeout=6) as response:
            return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        import requests

        response = requests.get(url, headers=headers, timeout=6)
        response.raise_for_status()
        return response.json()
    except ImportError:
        request = Request(url, headers=headers)

        with urlopen(request, timeout=6) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))


DEFAULT_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
}


def fetch_json_with_headers(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    request_headers = dict(DEFAULT_HTTP_HEADERS)
    if headers:
        request_headers.update(headers)

    try:
        import requests

        response = requests.get(url, headers=request_headers, timeout=8)
        response.raise_for_status()
        return response.json()
    except ImportError:
        request = Request(url, headers=request_headers)
        with urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_html_with_headers(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    request_headers = dict(DEFAULT_HTTP_HEADERS)
    if headers:
        request_headers.update(headers)

    try:
        import requests

        response = requests.get(url, headers=request_headers, timeout=8)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return response.text
    except ImportError:
        request = Request(url, headers=request_headers)
        with urlopen(request, timeout=8) as response:
            return response.read().decode("utf-8", errors="replace")


def extract_first_int(patterns: List[str], text: str) -> Optional[int]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                return int(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def spotify_playlist_id(url: str) -> Optional[str]:
    parsed = parsed_url(url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) >= 2 and segments[0] == "playlist":
        return segments[1]
    return None


def youtube_playlist_id(url: str) -> Optional[str]:
    return parse_qs(parsed_url(url).query).get("list", [None])[0]


def apple_tracks_from_html(html: str, metadata: Dict[str, str]) -> Optional[int]:
    count = extract_track_count(metadata)
    if count is not None:
        return count

    return extract_first_int(
        [
            r'"trackCount"\s*:\s*(\d{1,5})',
            r'"songCount"\s*:\s*(\d{1,5})',
            r'Playlist\s*[·•]\s*(\d{1,5})\s*Songs?',
        ],
        html,
    )


def spotify_tracks_from_html(html: str, metadata: Dict[str, str]) -> Optional[int]:
    count = extract_track_count(metadata)
    if count is not None:
        return count

    return extract_first_int(
        [
            r'"trackCount"\s*:\s*(\d{1,5})',
            r'"totalCount"\s*:\s*(\d{1,5})',
            r'"total"\s*:\s*(\d{1,5})\s*,\s*"items"',
            r'(\d{1,5})\s+(?:songs?|tracks?|titres?)',
        ],
        html,
    )


def spotify_preview_from_web_api(url: str) -> Optional[Dict[str, Any]]:
    playlist_id = spotify_playlist_id(url)
    if not playlist_id:
        return None

    token_data = fetch_json_with_headers(
        "https://open.spotify.com/get_access_token?reason=transport&productType=web-player"
    )
    token = token_data.get("accessToken") or token_data.get("access_token")
    if not token:
        return None

    data = fetch_json_with_headers(
        (
            f"https://api.spotify.com/v1/playlists/{playlist_id}"
            "?fields=name,images(url),tracks(total)&additional_types=track&market=from_token"
        ),
        headers={"Authorization": f"Bearer {token}"},
    )

    images = data.get("images") if isinstance(data.get("images"), list) else []
    cover_url = None
    for image in images:
        if isinstance(image, dict) and image.get("url"):
            cover_url = image["url"]
            break

    tracks = data.get("tracks", {}).get("total") if isinstance(data.get("tracks"), dict) else None

    return preview_response(
        platform="spotify",
        title=data.get("name"),
        tracks=tracks if isinstance(tracks, int) else None,
        cover_url=cover_url,
    )


def youtube_tracks_from_feed(url: str) -> Optional[int]:
    playlist_id = youtube_playlist_id(url)
    if not playlist_id:
        return None

    feed_url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
    xml = fetch_html_with_headers(feed_url)
    entries = re.findall(r"<entry[\s>]", xml, re.IGNORECASE)
    return len(entries) if entries else None


def youtube_preview_from_ytdlp(url: str) -> Optional[Dict[str, Any]]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return None

    options = {
        "extract_flat": True,
        "ignoreerrors": True,
        "quiet": True,
        "skip_download": True,
        "socket_timeout": 10,
        "noplaylist": False,
    }

    with YoutubeDL(options) as ydl:
        data = ydl.extract_info(url, download=False)

    if not isinstance(data, dict):
        return None

    title = data.get("title")
    cover_url = data.get("thumbnail")
    thumbnails = data.get("thumbnails")

    if not cover_url and isinstance(thumbnails, list):
        for thumbnail in reversed(thumbnails):
            if isinstance(thumbnail, dict) and thumbnail.get("url"):
                cover_url = thumbnail["url"]
                break

    tracks: Optional[int] = None
    entries = data.get("entries")

    if isinstance(entries, list):
        tracks = len([entry for entry in entries if entry])

    if tracks is None:
        for key in ["playlist_count", "n_entries"]:
            value = data.get(key)

            if isinstance(value, int):
                tracks = value
                break

    if not has_valid_youtube_preview(title, cover_url, tracks):
        return None

    return preview_response(
        platform="youtube",
        title=title,
        tracks=tracks,
        cover_url=cover_url,
    )


def youtube_tracks_from_html(html: str, metadata: Dict[str, str]) -> Optional[int]:
    count = extract_track_count(metadata)
    if count is not None:
        return count

    count = extract_first_int(
        [
            r'"numVideosText"\s*:\s*\{.*?"simpleText"\s*:\s*"(\d{1,5})\s+videos?"',
            r'"videoCount"\s*:\s*"?(\d{1,5})"?',
            r'"stats"\s*:\s*\[\s*\{\s*"runs"\s*:\s*\[\s*\{\s*"text"\s*:\s*"(\d{1,5})"',
            r'(\d{1,5})\s+videos?',
        ],
        html,
    )
    return count


def youtube_html_for_playlist(url: str) -> str:
    return fetch_html_with_headers(
        url,
        headers={
            "Cookie": "CONSENT=YES+cb.20210328-17-p0.en+FX+410; SOCS=CAISEwgDEgk0MzY3NzYwODQaAmVuIAEaBgiA_LyaBg",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

def extract_metadata(html: str) -> Dict[str, str]:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        metadata: Dict[str, str] = {}

        for tag in soup.find_all("meta"):
            key = tag.get("property") or tag.get("name")
            content = tag.get("content")

            if key and content:
                metadata[str(key).lower()] = str(content).strip()

        if soup.title and soup.title.string:
            metadata["title"] = soup.title.string.strip()

        return metadata
    except ImportError:
        parser = MetadataParser()
        parser.feed(html)

        if parser.title.strip():
            parser.meta["title"] = unescape(parser.title.strip())

        return parser.meta


def first_metadata_value(metadata: Dict[str, str], keys: List[str]) -> Optional[str]:
    for key in keys:
        value = metadata.get(key)

        if value:
            return value.strip()

    return None


def clean_preview_title(title: Optional[str], platform: str) -> str:
    if not title:
        return "Playlist"

    cleaned = unescape(title).strip()
    suffixes = {
        "youtube": [" - YouTube", " - youtube"],
        "spotify": [" | Spotify", " - playlist by Spotify"],
        "apple": [" - Apple Music", " on Apple Music"],
    }

    for suffix in suffixes.get(platform, []):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()

    return cleaned or "Playlist"


def extract_track_count(metadata: Dict[str, str]) -> Optional[int]:
    for key in ["music:song_count", "music:album:track_count", "numtracks"]:
        value = metadata.get(key)

        if value and value.isdigit():
            return int(value)

    description = first_metadata_value(
        metadata,
        ["og:description", "description", "twitter:description"],
    )

    if not description:
        return None

    match = re.search(
        r"(\d{1,5})\s+(?:songs?|tracks?|videos?)",
        description,
        re.IGNORECASE,
    )

    return int(match.group(1)) if match else None


def preview_response(
    platform: str,
    title: Optional[str],
    tracks: Optional[int],
    cover_url: Optional[str],
    supported: bool = True,
    message: Optional[str] = None,
) -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "title": clean_preview_title(title, platform),
        "platform": platform,
        "tracks": tracks,
        "supported": supported,
    }

    if cover_url:
        response["coverUrl"] = cover_url

    if message:
        response["message"] = message

    return response


def unsupported_preview(platform: str, message: str) -> Dict[str, Any]:
    return {
        "platform": platform,
        "tracks": None,
        "supported": False,
        "message": message,
    }


def has_valid_youtube_preview(
    title: Optional[str],
    cover_url: Optional[str],
    tracks: Optional[int],
) -> bool:
    normalized_title = unescape(title or "").strip().lower()

    if normalized_title in {"", "undefined", "null", "none", "youtube", "playlist"}:
        return False

    return bool(cover_url) or (isinstance(tracks, int) and tracks > 0)


def http_status(error: Exception) -> Optional[int]:
    code = getattr(error, "code", None)

    if isinstance(code, int):
        return code

    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)

    return status_code if isinstance(status_code, int) else None


def parsed_url(url: str) -> Any:
    try:
        return urlparse(url)
    except Exception:
        return urlparse("")


def is_youtube_playlist_url(url: str) -> bool:
    parsed = parsed_url(url)
    host = parsed.netloc.lower()

    if not (
        host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtu.be"
    ):
        return False

    list_id = parse_qs(parsed.query).get("list", [""])[0]
    return bool(list_id.strip())


def is_spotify_playlist_url(url: str) -> bool:
    parsed = parsed_url(url)
    host = parsed.netloc.lower()

    if host != "open.spotify.com":
        return False

    return "playlist" in [segment for segment in parsed.path.split("/") if segment]


def is_apple_music_playlist_url(url: str) -> bool:
    parsed = parsed_url(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if host != "music.apple.com" or "/library/" in path:
        return False

    return re.search(r"/[a-z]{2}/(playlist|album)/", path) is not None


def preview_from_metadata(url: str, platform: str) -> Dict[str, Any]:
    html = fetch_html(url)
    metadata = extract_metadata(html)
    title_keys = ["og:title", "twitter:title", "apple:title", "title"]

    if platform == "apple":
        title_keys = ["apple:title", "og:title", "twitter:title", "title"]

    title = first_metadata_value(metadata, title_keys)
    cover_url = first_metadata_value(
        metadata,
        ["og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"],
    )

    if cover_url:
        cover_url = urljoin(url, cover_url)

    tracks = extract_track_count(metadata)
    if platform == "apple":
        tracks = apple_tracks_from_html(html, metadata)
    elif platform == "spotify":
        tracks = spotify_tracks_from_html(html, metadata)
    elif platform == "youtube":
        tracks = youtube_tracks_from_html(html, metadata)

    return preview_response(
        platform=platform,
        title=title,
        tracks=tracks,
        cover_url=cover_url,
    )


def preview_youtube(url: str) -> Dict[str, Any]:
    if not is_youtube_playlist_url(url):
        return unsupported_preview("youtube", "Use a valid public YouTube playlist URL.")

    try:
        ytdlp_preview = youtube_preview_from_ytdlp(url)

        if ytdlp_preview is not None:
            return ytdlp_preview
    except Exception:
        pass

    title = None
    cover_url = None
    tracks = None
    oembed_error: Optional[Exception] = None

    try:
        data = fetch_json(
            f"https://www.youtube.com/oembed?url={quote(url, safe='')}&format=json"
        )
        title = data.get("title")
        cover_url = data.get("thumbnail_url")
    except Exception as exc:
        oembed_error = exc

    try:
        html = youtube_html_for_playlist(url)
        metadata = extract_metadata(html)
        title = title or first_metadata_value(metadata, ["og:title", "twitter:title", "title"])
        cover_url = cover_url or first_metadata_value(metadata, ["og:image", "twitter:image", "twitter:image:src"])
        tracks = youtube_tracks_from_html(html, metadata)
    except Exception:
        pass

    if tracks is None:
        try:
            tracks = youtube_tracks_from_feed(url)
        except Exception:
            pass

    if cover_url:
        cover_url = urljoin(url, cover_url)

    if has_valid_youtube_preview(title, cover_url, tracks):
        return preview_response(
            platform="youtube",
            title=title,
            tracks=tracks,
            cover_url=cover_url,
        )

    if oembed_error and http_status(oembed_error) in {400, 404}:
        return unsupported_preview("youtube", "YouTube playlist could not be found.")

    return unsupported_preview("youtube", "YouTube playlist could not be found or is not public.")


def preview_spotify(url: str) -> Dict[str, Any]:
    if not is_spotify_playlist_url(url):
        return unsupported_preview("spotify", "Use a public Spotify playlist URL.")

    try:
        data = fetch_json(
            f"https://open.spotify.com/oembed?url={quote(url, safe='')}"
        )

        return preview_response(
            platform="spotify",
            title=data.get("title"),
            tracks=None,
            cover_url=data.get("thumbnail_url"),
        )
    except Exception:
        return unsupported_preview(
            "spotify",
            "Spotify playlist could not be found or is not public.",
        )

def preview_apple(url: str) -> Dict[str, Any]:
    if not is_apple_music_playlist_url(url):
        return unsupported_preview("apple", "Use a public Apple Music share link.")

    return preview_from_metadata(url, "apple")


def detect_platform(url: str) -> Dict[str, Any]:
    normalized = url.strip().lower()

    if not normalized:
        return {"platform": "unknown", "supported": False, "reason": "empty"}

    if "soundcloud.com" in normalized:
        return {"platform": "soundcloud", "supported": False, "reason": "unsupported"}

    if "spotify.com" in normalized:
        supported = is_spotify_playlist_url(url)
        response = {"platform": "spotify", "supported": supported}
        if not supported:
            response["reason"] = "unknown"
        return response

    if "music.apple.com" in normalized:
        supported = is_apple_music_playlist_url(url)
        response = {"platform": "apple", "supported": supported}
        if not supported:
            response["reason"] = "unknown"
        return response

    if "youtube.com" in normalized or "youtu.be" in normalized:
        supported = is_youtube_playlist_url(url)
        response = {"platform": "youtube", "supported": supported}
        if not supported:
            response["reason"] = "unknown"
        return response

    return {"platform": "unknown", "supported": False, "reason": "unknown"}


def preview_playlist(payload: Dict[str, Any]) -> Any:
    url = str(payload.get("url", "")).strip()
    detection = detect_platform(url)
    platform = detection.get("platform", "unknown")

    if not detection.get("supported"):
        if platform == "soundcloud":
            return unsupported_preview("soundcloud", "SoundCloud support coming soon.")

        if platform == "youtube":
            return unsupported_preview("youtube", "Use a valid public YouTube playlist URL.")

        if platform == "spotify":
            return unsupported_preview("spotify", "Use a public Spotify playlist URL.")

        if platform == "apple":
            return unsupported_preview("apple", "Use a public Apple Music share link.")

        return {
            "platform": "unknown",
            "tracks": None,
            "supported": False,
            "message": "Use a supported playlist URL.",
        }

    preview_functions = {
        "youtube": preview_youtube,
        "spotify": preview_spotify,
        "apple": preview_apple,
    }
    preview_function = preview_functions.get(platform)

    if preview_function is None:
        return {
            "platform": platform,
            "tracks": None,
            "supported": False,
            "message": "This platform is not supported yet.",
        }

    try:
        return preview_function(url)
    except Exception:
        return {
            "title": "Playlist preview unavailable",
            "platform": platform,
            "tracks": None,
            "supported": True,
            "message": "Playlist info could not be fetched yet. You can still add it.",
        }


def add_playlist(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = str(payload.get("url", "")).strip()
    folder = str(payload.get("folder", "")).strip()
    detection = detect_platform(url)

    if not detection.get("supported"):
        return {
            "ok": False,
            "message": "A supported playlist URL is required.",
        }

    if not folder:
        return {
            "ok": False,
            "message": "A destination folder is required.",
        }

    folder_path = Path(folder).expanduser()

    if not folder_path.exists():
        return {
            "ok": False,
            "message": "The selected destination folder does not exist.",
        }

    if not folder_path.is_dir():
        return {
            "ok": False,
            "message": "The selected destination is not a folder.",
        }

    try:
        ensure_project_root_on_path()
        from core.CentralManager import CentralManager, Platform

        platform_map = {
            "youtube": Platform.YOUTUBE,
            "spotify": Platform.SPOTIFY,
            "apple": Platform.APPLE,
        }
        platform = platform_map.get(detection["platform"])

        if platform is None:
            return {
                "ok": False,
                "message": "This platform is not supported yet.",
            }

        with redirect_stdout(StringIO()):
            manager = CentralManager("playlists.json")
            message = manager.add_playlist(url, str(folder_path), platform)
            playlists = manager.list_playlists()

        playlist = next(
            (
                map_core_playlist(playlist, cover_wait_seconds=1.0)
                for playlist in playlists
                if playlist.url == url
            ),
            None,
        )
        ok = message == "Playlist added successfully."
        response: Dict[str, Any] = {
            "ok": ok,
            "message": message,
        }

        if playlist is not None:
            response["playlist"] = playlist

        print("[YouSync bridge] add response:", json.dumps(response, ensure_ascii=False), file=sys.stderr)
        return response
    except Exception as exc:
        return {
            "ok": False,
            "message": str(exc),
        }


def handle(command: str, payload: Dict[str, Any]) -> Any:
    if command == "detect":
        return detect_platform(str(payload.get("url", "")))

    if command == "preview":
        return preview_playlist(payload)

    if command == "add":
        return add_playlist(payload)

    if command == "list":
        playlists, _source = list_core_playlists()
        print("[YouSync bridge] list response:", json.dumps(playlists, ensure_ascii=False), file=sys.stderr)
        return playlists

    return {
        "ok": False,
        "error": f"Unknown command: {command}",
    }


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""

    try:
        payload = read_input()
        response = handle(command, payload)
        write_json(response)
        return 0
    except Exception as exc:
        write_json({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
