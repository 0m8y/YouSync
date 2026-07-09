import json
import re
import os
import time
import hashlib
import requests
import platform
import unicodedata
from bs4 import BeautifulSoup
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse

WINDOWS_FORBIDDEN_PATH_CHARS = '<>:"/\\|?*'
WINDOWS_RESERVED_PATH_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_path_component(value: str, fallback: str = "untitled", max_length: int = 120) -> str:
    text = "" if value is None else str(value)
    text = text.encode("utf-8", "ignore").decode("utf-8", "ignore")
    text = unicodedata.normalize("NFC", text)

    cleaned_chars = []
    for char in text:
        category = unicodedata.category(char)
        if category[0] == "C":
            continue
        if ord(char) > 0xFFFF:
            continue
        if char in WINDOWS_FORBIDDEN_PATH_CHARS:
            cleaned_chars.append("_")
            continue
        cleaned_chars.append(char)

    cleaned = "".join(cleaned_chars)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(" .")
    cleaned = re.sub(r"_+", "_", cleaned).strip("_").strip().rstrip(" .")

    if not cleaned:
        cleaned = str(fallback or "untitled")
        cleaned = cleaned.encode("utf-8", "ignore").decode("utf-8", "ignore")
        cleaned = unicodedata.normalize("NFC", cleaned)
        cleaned = re.sub(rf"[{re.escape(WINDOWS_FORBIDDEN_PATH_CHARS)}]", "_", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(" .")
        cleaned = re.sub(r"_+", "_", cleaned).strip("_").strip().rstrip(" .")

    if not cleaned:
        cleaned = "untitled"

    name_for_reserved_check = cleaned.split(".", 1)[0].upper()
    if name_for_reserved_check in WINDOWS_RESERVED_PATH_NAMES:
        cleaned = f"_{cleaned}"

    max_length = max(16, int(max_length or 120))
    if len(cleaned) > max_length:
        digest = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:8]
        suffix = f"-{digest}"
        cleaned = cleaned[:max_length - len(suffix)].rstrip(" .") + suffix

    return cleaned or "untitled"


def check_yousync_folder(yousync_folder_path: str) -> None:
    parent_folder = os.path.dirname(yousync_folder_path)

    # Check if parent folder exists
    if not os.path.exists(parent_folder):
        raise FileNotFoundError(f"The parent folder {parent_folder} does not exist.")

    if not os.path.exists(yousync_folder_path):
        os.makedirs(yousync_folder_path)

    if platform.system() == 'Windows':
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x02

        ret = ctypes.windll.kernel32.SetFileAttributesW(yousync_folder_path, FILE_ATTRIBUTE_HIDDEN)
        if not ret:
            raise ctypes.WinError()


def check_playlist_data_filepath(playlist_filepath: str) -> None:
    if not os.path.exists(playlist_filepath):
        with open(playlist_filepath, 'w') as fichier:
            fichier.write("[]")


def get_youtube_playlist_id(playlist_url: str) -> Optional[str]:
    pattern = r"list=([a-zA-Z0-9_-]+)"
    match = re.search(pattern, playlist_url)
    if match:
        return match.group(1)
    return None


def get_spotify_playlist_id(playlist_url: str) -> Optional[str]:
    pattern = r"(?:^|/)(?:intl-[a-z]{2}/)?(?:track|playlist)/([a-zA-Z0-9]+)"
    match = re.search(pattern, playlist_url)
    if match:
        return match.group(1)
    return None


DEEZER_API_BASE = "https://api.deezer.com"
DEEZER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def get_deezer_playlist_id(playlist_url: str) -> Optional[str]:
    raw_url = str(playlist_url or "").strip()

    if re.fullmatch(r"\d+", raw_url):
        return raw_url

    parsed = urlparse(raw_url)
    match = re.search(r"/(?:[a-z]{2}/)?playlist/(\d+)", parsed.path, re.IGNORECASE)

    if match:
        return match.group(1)

    return None


def get_deezer_track_id(track_url: str) -> Optional[str]:
    raw_url = str(track_url or "").strip()

    if re.fullmatch(r"\d+", raw_url):
        return raw_url

    parsed = urlparse(raw_url)
    match = re.search(r"/(?:[a-z]{2}/)?track/(\d+)", parsed.path, re.IGNORECASE)

    if match:
        return match.group(1)

    return None


def normalize_deezer_track_url(raw_url: str | None) -> Optional[str]:
    track_id = get_deezer_track_id(str(raw_url or ""))
    return f"https://www.deezer.com/track/{track_id}" if track_id else None


def fetch_deezer_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = requests.get(url, params=params, headers=DEEZER_HEADERS, timeout=20)
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, dict):
        raise ValueError("Invalid Deezer API response.")

    if payload.get("error"):
        raise ValueError(f"Deezer API error: {payload['error']}")

    return payload


def normalize_deezer_track(raw_track: Dict[str, Any]) -> Dict[str, Any]:
    track_id = raw_track.get("id")
    track_id_str = str(track_id) if track_id not in (None, "") else ""

    artists: List[str] = []
    contributors = raw_track.get("contributors")

    if isinstance(contributors, list):
        artists.extend(
            str(artist.get("name")).strip()
            for artist in contributors
            if isinstance(artist, dict) and artist.get("name")
        )

    artist = raw_track.get("artist")
    if isinstance(artist, dict) and artist.get("name"):
        artists.append(str(artist["name"]).strip())

    deduped_artists: List[str] = []
    seen_artists: set[str] = set()
    for artist_name in artists:
        if artist_name and artist_name not in seen_artists:
            seen_artists.add(artist_name)
            deduped_artists.append(artist_name)

    album = raw_track.get("album")
    album_title = None
    cover_url = None

    if isinstance(album, dict):
        album_title = album.get("title")
        cover_url = (
            album.get("cover_xl")
            or album.get("cover_big")
            or album.get("cover_medium")
            or album.get("cover")
        )

    track_url = normalize_deezer_track_url(raw_track.get("link")) if raw_track.get("link") else None
    if not track_url and track_id_str:
        track_url = f"https://www.deezer.com/track/{track_id_str}"

    return {
        "id": track_id_str,
        "url": track_url,
        "title": raw_track.get("title") or raw_track.get("title_short") or "",
        "artists": deduped_artists,
        "album": album_title or "",
        "cover": cover_url or "",
        "duration": raw_track.get("duration"),
    }


def get_deezer_playlist_data(playlist_id: str) -> Dict[str, Any]:
    return fetch_deezer_json(f"{DEEZER_API_BASE}/playlist/{playlist_id}")


def get_deezer_track_data(track_id: str) -> Dict[str, Any]:
    return fetch_deezer_json(f"{DEEZER_API_BASE}/track/{track_id}")


def get_deezer_playlist_tracks(playlist_id: str) -> List[Dict[str, Any]]:
    endpoint = f"{DEEZER_API_BASE}/playlist/{playlist_id}/tracks"
    tracks: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    next_url: Optional[str] = endpoint
    params: Optional[Dict[str, Any]] = {"index": 0, "limit": 100}
    raw_index = 0

    for _ in range(100):
        if next_url is None:
            break

        payload = fetch_deezer_json(next_url, params=params)
        data = payload.get("data")

        if not isinstance(data, list) or not data:
            break

        raw_index += len(data)

        for raw_track in data:
            if not isinstance(raw_track, dict):
                continue

            track = normalize_deezer_track(raw_track)
            track_id = track.get("id") or track.get("url")

            if not track_id or track_id in seen_ids:
                continue

            seen_ids.add(str(track_id))
            tracks.append(track)

        next_value = payload.get("next")
        if next_value:
            next_url = str(next_value)
            params = None
            continue

        total = payload.get("total")
        if isinstance(total, int) and raw_index < total:
            next_url = endpoint
            params = {"index": raw_index, "limit": 100}
            continue

        break

    return tracks

def accept_spotify_cookies(driver: Any) -> bool:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    try:
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))).click()
        print("accepted cookies")
        return True
    except Exception as e:
        print(f'no cookie button: {e}')
        return False


def get_selenium_driver_for_spotify(url: str) -> Any:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--mute-audio")

    driver = webdriver.Chrome(options=chrome_options)

    driver.get(url)
    i = 0
    while not accept_spotify_cookies(driver):
        i += 1
        if i > 4:
            break
    return driver


def get_selenium_driver_for_apple(url: str) -> Any:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--mute-audio")

    driver = webdriver.Chrome(options=chrome_options)
    print(f"url: {url}")
    driver.get(url)

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    return driver

def normalize_spotify_track_url(raw_url: str | None) -> Optional[str]:
    if raw_url is None:
        return None

    raw_url = str(raw_url)

    patterns = (
        r"spotify:track:([a-zA-Z0-9]+)",
        r"open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([a-zA-Z0-9]+)",
        r"/(?:intl-[a-z]{2}/)?track/([a-zA-Z0-9]+)",
        r"(?:^|/)track/([a-zA-Z0-9]+)",
    )

    for pattern in patterns:
        match = re.search(pattern, raw_url)
        if match:
            return f"https://open.spotify.com/track/{match.group(1)}"

    return None

def dedupe_spotify_track_urls(urls: List[Optional[str]]) -> List[str]:
    unique_urls: List[str] = []
    seen: set[str] = set()

    for url in urls:
        normalized_url = normalize_spotify_track_url(url)

        if normalized_url is None or normalized_url in seen:
            continue

        seen.add(normalized_url)
        unique_urls.append(normalized_url)

    return unique_urls


def get_spotify_urls_from_html(html_content: str) -> List[str]:
    """Return only the official playlist tracks exposed by Spotify metadata.

    Spotify pages also contain many other /track/ links in the rendered DOM
    (recommendations, player state, scripts, etc.). Those links must not be
    considered playlist items. The stable source for a public playlist is:

        <meta name="music:song" content="https://open.spotify.com/track/...">
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    urls: List[Optional[str]] = []

    for meta in soup.find_all('meta', attrs={'name': 'music:song'}):
        urls.append(meta.get('content'))

    return dedupe_spotify_track_urls(urls)


def get_spotify_total_songs_from_html(html_content: str) -> int:
    soup = BeautifulSoup(html_content, 'html.parser')
    song_count_meta = soup.find('meta', attrs={'name': 'music:song_count'})

    if song_count_meta is not None:
        try:
            return int(str(song_count_meta.get('content', '')).strip())
        except ValueError:
            pass

    descriptions = []

    for attrs in (
        {'property': 'og:description'},
        {'name': 'description'},
        {'name': 'twitter:description'},
    ):
        tag = soup.find('meta', attrs=attrs)
        if tag is not None:
            descriptions.append(str(tag.get('content', '')))

    for description in descriptions:
        match = re.search(r'(\d+)\s*(?:items?|titres?|songs?|tracks?)', description, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return 0


def get_spotify_meta_content_from_html(
    html_content: str,
    *,
    name: str | None = None,
    property_: str | None = None,
) -> Optional[str]:
    soup = BeautifulSoup(html_content, 'html.parser')

    if name is not None:
        tag = soup.find('meta', attrs={'name': name})
    else:
        tag = soup.find('meta', attrs={'property': property_})

    if tag is None:
        return None

    content = tag.get('content')
    if not content:
        return None

    return str(content).strip()


SPOTIFY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def get_spotify_embed_url(playlist_url: str) -> Optional[str]:
    playlist_id = get_spotify_playlist_id(playlist_url)
    if not playlist_id:
        return None

    return f"https://open.spotify.com/embed/playlist/{playlist_id}"


def get_spotify_embed_next_data(html_content: str) -> Optional[Dict[str, Any]]:
    soup = BeautifulSoup(html_content, "html.parser")
    script = soup.find("script", attrs={"id": "__NEXT_DATA__"})

    if script is None or script.string is None:
        return None

    try:
        payload = json.loads(script.string)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def get_spotify_embed_entity(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    entity = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("state", {})
        .get("data", {})
        .get("entity", {})
    )

    return entity if isinstance(entity, dict) else {}


def get_spotify_embed_track_list(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entity = get_spotify_embed_entity(payload)
    track_list = entity.get("trackList")

    if not isinstance(track_list, list):
        return []

    return [track for track in track_list if isinstance(track, dict)]


def get_spotify_track_url_from_embed_item(track: Dict[str, Any]) -> Optional[str]:
    candidates = [
        track.get("uri"),
        track.get("trackUri"),
        track.get("url"),
        track.get("href"),
        track.get("shareUrl"),
        track.get("externalUrl"),
    ]

    external_urls = track.get("external_urls")
    if isinstance(external_urls, dict):
        candidates.append(external_urls.get("spotify"))

    track_id = track.get("id")
    if isinstance(track_id, str) and re.fullmatch(r"[a-zA-Z0-9]{16,32}", track_id):
        candidates.append(f"https://open.spotify.com/track/{track_id}")

    for candidate in candidates:
        normalized_url = normalize_spotify_track_url(candidate)
        if normalized_url:
            return normalized_url

    return None


def get_spotify_playlist_data_from_embed(playlist_url: str) -> Dict[str, Any]:
    embed_url = get_spotify_embed_url(playlist_url)
    if not embed_url:
        return {
            "track_urls": [],
            "track_count": 0,
            "title": None,
            "image": None,
            "source": "spotify_embed",
        }

    response = requests.get(embed_url, headers=SPOTIFY_HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    html = response.text
    payload = get_spotify_embed_next_data(html)
    entity = get_spotify_embed_entity(payload)
    track_list = get_spotify_embed_track_list(payload)
    track_urls = dedupe_spotify_track_urls([
        get_spotify_track_url_from_embed_item(track)
        for track in track_list
    ])

    images = entity.get("images")
    image = None
    if isinstance(images, list):
        for candidate in images:
            if isinstance(candidate, dict) and candidate.get("url"):
                image = str(candidate["url"]).strip()
                break

    return {
        "track_urls": track_urls,
        "track_count": len(track_urls),
        "declared_count": len(track_list) if track_list else None,
        "title": entity.get("name") or entity.get("title"),
        "image": image,
        "source": "spotify_embed",
    }


def get_soundloud_song_link(html_content: str) -> Optional[str]:
    """Legacy helper used with a single Spotify track row innerHTML."""
    soup = BeautifulSoup(html_content, 'html.parser')

    for link in soup.find_all('a', href=True):
        normalized_url = normalize_spotify_track_url(link.get('href'))
        if normalized_url is not None:
            return normalized_url

    match = re.search(r'(?:https://open\.spotify\.com)?/track/[a-zA-Z0-9]+', html_content)
    if match:
        return normalize_spotify_track_url(match.group(0))

    return None


def collect_spotify_track_row_urls_from_driver(driver: Any) -> List[str]:
    from selenium.webdriver.common.by import By

    urls: List[Optional[str]] = []

    try:
        rows = driver.find_elements(By.XPATH, "//div[@data-testid='tracklist-row']")
        for row in rows:
            urls.append(get_soundloud_song_link(row.get_attribute('innerHTML')))
    except Exception as e:
        print(f"⚠️ Unable to collect Spotify track rows: {e}")

    try:
        hrefs = driver.execute_script(
            "return Array.from(document.querySelectorAll('[data-testid=\"tracklist-row\"] a[href*=\"track\"]')).map((a) => a.href || a.getAttribute('href'));"
        )
        if isinstance(hrefs, list):
            urls.extend(str(href) for href in hrefs)
    except Exception as e:
        print(f"⚠️ Unable to collect Spotify row links with JavaScript: {e}")

    return dedupe_spotify_track_urls(urls)


def prepare_spotify_playlist_view(driver: Any) -> None:
    # Make Spotify render as many playlist rows as possible in headless mode.
    try:
        driver.set_window_size(1920, 10000)
    except Exception:
        pass

    try:
        driver.execute_script('''
            document.documentElement.style.zoom = "0.05";
            document.body.style.zoom = "0.05";
            window.dispatchEvent(new Event("resize"));
        ''')
        time.sleep(2)
    except Exception as e:
        print(f"⚠️ Unable to prepare Spotify playlist viewport: {e}")


def collect_spotify_playlist_scoped_urls_from_driver(driver: Any) -> List[str]:
    # Collect Spotify track URLs from the playlist only. Spotify appends a
    # recommendations block after the playlist, so global track-link scans
    # can include tracks that should not be synchronized.
    try:
        hrefs = driver.execute_script(r'''
            function textOf(node) {
              return (node?.innerText || node?.textContent || '').trim();
            }

            function findRecommendedHeading() {
              const candidates = Array.from(document.querySelectorAll('h1,h2,h3,section,div,span'));

              return candidates.find((node) => {
                const text = textOf(node).toLowerCase();
                if (!text || text.length > 120) return false;

                return (
                  text === 'recommandés' ||
                  text === 'recommended' ||
                  text.includes('recommandés') ||
                  text.includes('recommended') ||
                  text.includes('recommandations') ||
                  text.includes('recommendations')
                );
              }) || null;
            }

            function isAfter(reference, node) {
              if (!reference) return false;
              return Boolean(reference.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING);
            }

            const recommendedHeading = findRecommendedHeading();
            const anchors = Array.from(document.querySelectorAll('a[href*="track"]'));
            const playlistAnchors = anchors.filter((anchor) => !isAfter(recommendedHeading, anchor));

            return playlistAnchors
              .map((anchor) => anchor.href || anchor.getAttribute('href'))
              .filter(Boolean);
        ''')

        if isinstance(hrefs, list):
            return dedupe_spotify_track_urls([str(href) for href in hrefs])
    except Exception as e:
        print(f"⚠️ Unable to collect Spotify playlist-scoped links with JavaScript: {e}")

    return collect_spotify_track_row_urls_from_driver(driver)


def scroll_spotify_playlist(driver: Any) -> None:
    try:
        driver.execute_script(r'''
            const candidates = Array.from(document.querySelectorAll('*'))
              .filter((el) => el.scrollHeight > el.clientHeight + 100)
              .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));

            const scroller = candidates[0] || document.scrollingElement || document.documentElement || document.body;
            scroller.scrollTop = scroller.scrollHeight;
            window.scrollTo(0, document.body.scrollHeight);
        ''')
    except Exception:
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            pass


def get_spotify_url_list(driver: Any, total_songs: int, iterator: int = 0) -> List[str]:
    print("searching songs...")

    # Spotify metadata is reliable only when it contains the whole playlist.
    # For long playlists Spotify usually exposes only the first 30
    # <meta name="music:song"> entries, so we must fall back to scoped DOM
    # collection instead of returning a truncated list.
    metadata_urls = get_spotify_urls_from_html(driver.page_source)
    if metadata_urls and (total_songs <= 0 or len(metadata_urls) >= total_songs):
        return metadata_urls[:total_songs] if total_songs > 0 else metadata_urls

    if metadata_urls and total_songs > 0:
        print(f"Spotify metadata is incomplete: {len(metadata_urls)}/{total_songs} songs. Falling back to scoped DOM collection.")

    prepare_spotify_playlist_view(driver)

    urls = collect_spotify_playlist_scoped_urls_from_driver(driver)

    if total_songs > 0 and len(urls) >= total_songs:
        return urls[:total_songs]

    stable_rounds = 0
    max_rounds = 20

    for _ in range(max_rounds):
        previous_count = len(urls)
        scroll_spotify_playlist(driver)
        time.sleep(0.8)

        scoped_urls = collect_spotify_playlist_scoped_urls_from_driver(driver)
        if len(scoped_urls) > len(urls):
            urls = scoped_urls

        if total_songs > 0 and len(urls) >= total_songs:
            return urls[:total_songs]

        if len(urls) == previous_count:
            stable_rounds += 1
            if stable_rounds >= 3:
                break
        else:
            stable_rounds = 0

    return urls[:total_songs] if total_songs > 0 and len(urls) > total_songs else urls

def get_spotify_total_songs(driver: Any) -> int:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    time.sleep(0.5)

    total_from_metadata = get_spotify_total_songs_from_html(driver.page_source)
    if total_from_metadata > 0:
        print(f"{total_from_metadata} songs found in Spotify metadata")
        return total_from_metadata

    try:
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'span[data-encore-id="text"]'))
        )

        match = re.search(r'(\d+)\s*(?:titres?|songs?|tracks?|items?)', element.text, re.IGNORECASE)
        if match:
            print(element.text)
            return int(match.group(1))

    except (TimeoutException, NoSuchElementException, ValueError) as e:
        print(f"❌ Erreur lors de la récupération du nombre de morceaux : {e}")

    return 0

def scroll_down_apple_page(driver: Any) -> None:
    last_height = driver.execute_script("return document.getElementById('scrollable-page').scrollHeight")

    while True:
        driver.execute_script("document.getElementById('scrollable-page').scrollTo(0, document.getElementById('scrollable-page').scrollHeight);")

        # Wait for the page to load new content
        time.sleep(2)

        new_height = driver.execute_script("return document.getElementById('scrollable-page').scrollHeight")

        # If the new height is the same as the last height, wait for some time to ensure content has finished loading
        if new_height == last_height:
            time.sleep(2)
            new_height = driver.execute_script("return document.getElementById('scrollable-page').scrollHeight")
            if new_height == last_height:
                break

        last_height = new_height

def is_valid_apple_music_url(url: str) -> bool:
    # Refuser les liens de bibliothèque privée
    if "/library/" in url:
        return False

    # Vérifier qu'il s'agit bien d'une playlist ou d'un album
    if not re.search(r'/playlist/|/album/', url):
        return False

    try:
        response = requests.get(url, timeout=5, headers={
            "User-Agent": "Mozilla/5.0"
        })
        if response.status_code != 200:
            return False

        soup = BeautifulSoup(response.text, 'html.parser')

        # Vérifie la présence de métadonnées spécifiques à Apple Music
        if soup.find('meta', attrs={'name': 'apple:content_id'}) or soup.find('meta', property='og:title'):
            return True

    except Exception as e:
        print(f"Erreur lors de la validation du lien Apple Music : {e}")

    return False

def extract_json_object(text, key):
    """
    Extrait un JSON complet contenant une clé donnée.
    """
    start_index = text.rfind(key)
    if start_index == -1:
        return None

    # Trouver le début du JSON
    brace_count = 0
    json_start = text.rfind("{", 0, start_index)

    if json_start == -1:
        return None

    # Trouver la fin du JSON
    for i in range(json_start, len(text)):
        if text[i] == "{":
            brace_count += 1
        elif text[i] == "}":
            brace_count -= 1
        if brace_count == 0:
            json_end = i + 1
            break
    else:
        return None  # Pas de fin de JSON trouvée

    json_text = text[json_start:json_end]
    return json_text

def get_cached_video_title(url, data_filepath):
    if os.path.exists(data_filepath):
        try:
            with open(data_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for audio in data.get("audios", []):
                    if audio.get("url") == url:
                        return audio.get("video_title", "")
        except Exception as e:
            print(f"⚠️ Erreur lecture JSON pour vidéo title : {e}")
    return None

def get_cached_video_id(url: str, data_filepath: str) -> Optional[str]:
    if os.path.exists(data_filepath):
        try:
            with open(data_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for audio in data.get("audios", []):
                    if audio.get("url") == url:
                        return audio.get("id", None)
        except Exception as e:
            print(f"⚠️ Erreur lecture JSON pour video_id : {e}")
    return None

def get_cached_playlist_title(playlist_url: str, data_filepath: str) -> Optional[str]:
    if not os.path.exists(data_filepath):
        return None
    try:
        with open(data_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("title", None)
    except Exception as e:
        print(f"⚠️ Erreur lecture JSON pour playlist title : {e}")
        return None

def get_cached_playlist_id(playlist_url: str, data_filepath: str) -> Optional[str]:
    if not os.path.exists(data_filepath):
        return None
    try:
        with open(data_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("id", None)
    except Exception as e:
        print(f"⚠️ Erreur lecture JSON pour playlist id : {e}")
        return None
