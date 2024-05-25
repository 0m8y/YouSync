from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
import platform, re, os, time

def check_yousync_folder(yousync_folder_path):
    if not os.path.exists(yousync_folder_path):
        os.makedirs(yousync_folder_path)

    if platform.system() == 'Windows':
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x02

        ret = ctypes.windll.kernel32.SetFileAttributesW(yousync_folder_path, FILE_ATTRIBUTE_HIDDEN)
        if not ret:  # Si l'opération échoue, ret est 0
            raise ctypes.WinError()

def check_playlist_data_filepath(playlist_filepath):
    if not os.path.exists(playlist_filepath):
        with open(playlist_filepath, 'w') as fichier:
            fichier.write("[]")

def get_playlist_id(playlist_url):
    pattern = r"list=([a-zA-Z0-9_-]+)"
    match = re.search(pattern, playlist_url)
    if match:
        return match.group(1)
    else:
        return None

def extract_video_id(url):
    query = urlparse(url).query
    params = parse_qs(query)
    return params.get('v', [None])[0]


def accept_cookies(driver):
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
    accept_cookies(driver)
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