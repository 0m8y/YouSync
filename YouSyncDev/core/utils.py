import json
import re
import os
import time
import requests
import platform
from bs4 import BeautifulSoup
from selenium import webdriver
from typing import Optional, List
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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
    pattern = r"(track|playlist)/([a-zA-Z0-9]+)"
    match = re.search(pattern, playlist_url)
    if match:
        return match.group(2)
    return None

def accept_spotify_cookies(driver: webdriver.Chrome) -> bool:
    try:
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))).click()
        print("accepted cookies")
        return True
    except Exception as e:
        print(f'no cookie button: {e}')
        return False


def get_selenium_driver_for_spotify(url: str) -> webdriver.Chrome:
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


def get_selenium_driver_for_apple(url: str) -> webdriver.Chrome:
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

    match = re.search(r"open\.spotify\.com/track/([a-zA-Z0-9]+)", raw_url)
    if match:
        return f"https://open.spotify.com/track/{match.group(1)}"

    match = re.search(r"(?:^|/)track/([a-zA-Z0-9]+)", raw_url)
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


def collect_spotify_track_row_urls_from_driver(driver: webdriver.Chrome) -> List[str]:
    urls: List[Optional[str]] = []

    try:
        rows = driver.find_elements(By.XPATH, "//div[@data-testid='tracklist-row']")
        for row in rows:
            urls.append(get_soundloud_song_link(row.get_attribute('innerHTML')))
    except Exception as e:
        print(f"⚠️ Unable to collect Spotify track rows: {e}")

    try:
        hrefs = driver.execute_script(
            "return Array.from(document.querySelectorAll('[data-testid=\\\"tracklist-row\\\"] a[href*=\\\"/track/\\\"]')).map((a) => a.href);"
        )
        if isinstance(hrefs, list):
            urls.extend(str(href) for href in hrefs)
    except Exception as e:
        print(f"⚠️ Unable to collect Spotify row links with JavaScript: {e}")

    return dedupe_spotify_track_urls(urls)


def get_spotify_url_list(driver: webdriver.Chrome, total_songs: int, iterator: int = 0) -> List[str]:
    print("searching songs...")

    # First, use only official playlist metadata from the currently rendered page.
    metadata_urls = get_spotify_urls_from_html(driver.page_source)
    if metadata_urls:
        if total_songs > 0:
            return metadata_urls[:total_songs]
        return metadata_urls

    urls = collect_spotify_track_row_urls_from_driver(driver)

    if total_songs > 0 and len(urls) >= total_songs:
        return urls[:total_songs]

    stable_rounds = 0
    max_rounds = 30

    for _ in range(max_rounds):
        previous_count = len(urls)

        try:
            driver.execute_script(
                "const scroller = document.querySelector('[data-testid=\\\"playlist-tracklist\\\"]') || document.querySelector('[data-testid=\\\"virtuoso-scroller\\\"]') || document.scrollingElement || document.body; scroller.scrollTop = scroller.scrollHeight; window.scrollTo(0, document.body.scrollHeight);"
            )
        except Exception:
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                pass

        time.sleep(0.8)

        metadata_urls = get_spotify_urls_from_html(driver.page_source)
        if metadata_urls:
            if total_songs > 0:
                return metadata_urls[:total_songs]
            return metadata_urls

        urls = collect_spotify_track_row_urls_from_driver(driver)

        if total_songs > 0 and len(urls) >= total_songs:
            return urls[:total_songs]

        if len(urls) == previous_count:
            stable_rounds += 1
            if stable_rounds >= 3:
                break
        else:
            stable_rounds = 0

    return urls[:total_songs] if total_songs > 0 else urls


def get_spotify_total_songs(driver: webdriver.Chrome) -> int:
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

def scroll_down_apple_page(driver: webdriver.Chrome) -> None:
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
