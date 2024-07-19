from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from pytubefix import YouTube
from selenium.webdriver.remote.webdriver import WebDriver
from typing import Optional


def find_title_yt(yt: YouTube) -> str:
    return yt.title.replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")


def find_title_url(url: str) -> str:
    yt = YouTube(url)
    return yt.title.replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")


def find_title(driver: WebDriver) -> Optional[str]:
    try:
        titre = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CLASS_NAME, "yt-video-attribute-view-model__title"))
        ).get_attribute('textContent').replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
    except TimeoutException:
        titre = None
    print(f"Titre: {titre}")
    return titre


def find_artist(driver: WebDriver) -> Optional[str]:
    try:
        artiste = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CLASS_NAME, "yt-video-attribute-view-model__subtitle"))
        ).get_attribute('textContent').replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
    except TimeoutException:
        artiste = None
    print(f"Artiste: {artiste}")
    return artiste


def find_album(driver: WebDriver) -> Optional[str]:
    try:
        album = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CLASS_NAME, "yt-video-attribute-view-model__secondary-subtitle"))
        ).get_attribute('textContent').replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
    except TimeoutException:
        album = None
    print(f"Album: {album}")
    return album


def find_image(driver: WebDriver) -> Optional[str]:
    try:
        image = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "link[itemprop='thumbnailUrl']"))
        ).get_attribute('href')
        print(f"Image: {image}")
        return image
    except TimeoutException:
        image = None
        print(f"Image: {image}")
    return image
