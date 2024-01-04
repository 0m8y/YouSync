
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
from pytube import YouTube

def get_selenium_driver(url):
    chrome_profile_path = r'C:\Users\msoub\AppData\Local\Google\Chrome\User Data'
    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
    chrome_options.add_argument("--profile-directory=Default")
    chrome_options.add_argument("--headless")

    driver = webdriver.Chrome(options=chrome_options)

    print("url is: " + url)
    
    driver.get(url)

    show_description = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//tp-yt-paper-button[@id='expand']"))
        )
    
    show_description.click()

    return driver

def find_title_yt(yt):
    return yt.title.replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")

def find_title_url(url):
    yt = YouTube(url)
    return yt.title.replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
    
def find_title(driver):
    try:
        titre = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CLASS_NAME, "yt-video-attribute-view-model__title"))
        ).get_attribute('textContent').replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
    except TimeoutException:
        titre = None
    print(f"Titre: {titre}")
    return titre

def find_artist(driver):
    try:
        artiste = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CLASS_NAME, "yt-video-attribute-view-model__subtitle"))
        ).get_attribute('textContent').replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
    except TimeoutException:
        artiste = None
    print(f"Artiste: {artiste}")
    return artiste

def find_album(driver):
    try:
        album = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CLASS_NAME, "yt-video-attribute-view-model__secondary-subtitle"))
        ).get_attribute('textContent').replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
    except TimeoutException:
        album = None
    print(f"Album: {album}")
    return album

def find_image(driver):
    try:
        image = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "link[itemprop='thumbnailUrl']"))
        ).get_attribute('href')
        print(f"Image: {image}")
        return image
    except TimeoutException:
        image = None
