
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from pytube import YouTube

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
