from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
import platform, re, os, time
from bs4 import BeautifulSoup
import datetime

def check_yousync_folder(yousync_folder_path):
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

def check_playlist_data_filepath(playlist_filepath):
    if not os.path.exists(playlist_filepath):
        with open(playlist_filepath, 'w') as fichier:
            fichier.write("[]")

def get_youtube_playlist_id(playlist_url):
    pattern = r"list=([a-zA-Z0-9_-]+)"
    match = re.search(pattern, playlist_url)
    if match:
        return match.group(1)
    else:
        return None
    
def get_spotify_playlist_id(playlist_url):
    pattern = r"(track|playlist)/([a-zA-Z0-9]+)"
    match = re.search(pattern, playlist_url)
    if match:
        return match.group(2)
    return None


def accept_youtube_cookies(driver):
    wait = WebDriverWait(driver, 10)
    if 'consent.youtube.com' in driver.current_url:
        try:
            accept_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Tout accepter')]")))
            accept_button.click()
            print("Cookies accepted")
        except Exception as e:
            print(f"Erreur lors de la tentative de clic sur le bouton 'Tout accepter': {e}")
    else:
        try:
            accept_button_xpath = '//button[@aria-label="Accepter l\'utilisation de cookies et d\'autres données aux fins décrites"]'
            accept_button = wait.until(EC.presence_of_element_located((By.XPATH, accept_button_xpath)))
            if accept_button:
                accept_button.click()
        except Exception as e:
            print(f"Erreur lors de la tentative de clic sur le bouton 'Tout accepter': {e}")
    
def get_selenium_driver(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--mute-audio")

    driver = webdriver.Chrome(options=chrome_options)

    driver.get(url)
    accept_youtube_cookies(driver)
    return driver

def accept_spotify_cookies(driver):
    try:
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        print("accepted cookies")
        return True
    except Exception as e:
        print('no cookie button')
        return False

def get_selenium_driver_for_spotify(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--mute-audio")

    driver = webdriver.Chrome(options=chrome_options)

    driver.get(url)
    i = 0
    while accept_spotify_cookies(driver) is False:
        i += 1
        if i > 4:
            break
    
    return driver

def scroll_down_page(driver):
    last_height = driver.execute_script("return document.documentElement.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")

        time.sleep(1)

        new_height = driver.execute_script("return document.documentElement.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def get_soundloud_song_link(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    track_link_tag = soup.select_one('a[data-testid="internal-track-link"]')
    
    if track_link_tag:
        track_link = track_link_tag.get('href')
        full_link = re.sub(r'^.*(/track)', r'https://open.spotify.com\1', track_link)
        return full_link
    else:
        return None

def get_soundcloud_url_list(driver, total_songs, iterator = 0):
    print("searching songs...")
    song_list = []
    if iterator == 5:
        raise Exception("Impossible to get all playlist sound url")
    songs = WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.XPATH, "//div[@data-testid='tracklist-row']")))
    song_count = 0
    for song in songs:
        song_count += 1
        song_list.append(get_soundloud_song_link(song.get_attribute('innerHTML')))
        if song_count >= total_songs:
            return song_list
    return get_soundcloud_url_list(driver, total_songs, iterator + 1)

def get_soundcloud_total_songs(driver):
    time.sleep(0.5)
    elements = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'span.encore-text.encore-text-body-small.RANLXG3qKB61Bh33I0r2'))
    )

    if len(elements) > 1:
        total_songs_element = elements[1]
    else:
        total_songs_element = elements[0]

    return int(total_songs_element.text.split()[0])
