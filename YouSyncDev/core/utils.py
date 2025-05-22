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
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--mute-audio")

    driver = webdriver.Chrome(options=chrome_options)
    print(f"url: {url}")
    driver.get(url)

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    return driver

def get_soundloud_song_link(html_content: str) -> Optional[str]:
    soup = BeautifulSoup(html_content, 'html.parser')
    track_link_tag = soup.select_one('a[data-testid="internal-track-link"]')

    if track_link_tag:
        track_link = track_link_tag.get('href')
        full_link = re.sub(r'^.*(/track)', r'https://open.spotify.com\1', track_link)
        return full_link
    return None


def get_soundcloud_url_list(driver: webdriver.Chrome, total_songs: int, iterator: int = 0) -> List[Optional[str]]:
    print("searching songs...")
    song_list = []
    if iterator == 30:
        raise Exception("Impossible to get all playlist sound url")
    songs = WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.XPATH, "//div[@data-testid='tracklist-row']")))
    song_count = 0
    for song in songs:
        song_count += 1
        song_list.append(get_soundloud_song_link(song.get_attribute('innerHTML')))
        if song_count >= total_songs:
            return song_list
    return get_soundcloud_url_list(driver, total_songs, iterator + 1)


def get_soundcloud_total_songs(driver: webdriver.Chrome) -> int:
    time.sleep(0.5)

    try:
        elements = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.GI8QLntnaSCh2ONX_y2c > span[data-encore-id="text"]'))
        )

        print(elements.text)  # Devrait afficher "143 titres"
        return int(elements.text.split()[0])

    except (TimeoutException, NoSuchElementException, ValueError) as e:
        print(f"❌ Erreur lors de la récupération du nombre de morceaux : {e}")
        return 0  # Retourne 0 en cas d'erreur


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
    start_index = text.find(key)
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
