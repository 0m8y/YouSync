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
