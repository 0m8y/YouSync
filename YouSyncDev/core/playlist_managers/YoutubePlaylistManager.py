from selenium.webdriver.support import expected_conditions as EC
from core.playlist_managers.IPlaylistManager import IPlaylistManager
from selenium.webdriver.support.ui import WebDriverWait
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.common.by import By
from selenium import webdriver
from core.audio_managers.YoutubeAudioManager import YoutubeAudioManager
from core.utils import get_youtube_playlist_id, get_selenium_driver, scroll_down_page
from bs4 import BeautifulSoup
import logging
import requests
from typing import List, Optional
from urllib.parse import urlparse, parse_qs


class YoutubePlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url: str, path_to_save_audio: str) -> None:
        self.html_page = requests.get(playlist_url).text
        self.soup = BeautifulSoup(self.html_page, 'html.parser')
        logging.debug("Initializing YoutubePlaylistManager")
        super().__init__(playlist_url, path_to_save_audio, get_youtube_playlist_id(playlist_url))

#----------------------------------------GETTER----------------------------------------#

    # Override Method
    def new_audio_manager(self, url: str) -> Optional[YoutubeAudioManager]:
        try:
            audio_manager = YoutubeAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            return audio_manager
        except Exception as e:
            logging.error(f"Error initializing YoutubeAudioManager: {e}")
            print(f"Error initializing YoutubeAudioManager: {e}")
            return None

    # Override Method
    def get_playlist_title(self) -> str:
        title = self.soup.find('meta', property='og:title')['content']
        print(f"title found: {title}")
        return title

    # Override Method
    def get_video_urls(self) -> List[str]:
        driver = get_selenium_driver(self.playlist_url)
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
        )
        scroll_down_page(driver)
        urls = self.__get_video_urls_from_driver(driver)
        driver.quit()
        return urls

    def __get_video_urls_from_driver(self, driver: webdriver.Chrome) -> List[str]:
        video_links = driver.find_elements(By.CSS_SELECTOR, 'a.yt-simple-endpoint.style-scope.ytd-playlist-video-renderer')
        urls = [video.get_attribute('href') for video in video_links if video.get_attribute('href') and 'watch?v=' in video.get_attribute('href')]
        recommended_videos_present = len(driver.find_elements(By.XPATH, "//div[@id='title' and contains(text(),'Vidéos recommandées')]")) > 0
        if recommended_videos_present:
            urls = urls[:-5]
        return urls

    def __get_author_name(self, driver: webdriver.Chrome) -> Optional[str]:
        try:
            author_name_selector = "yt-formatted-string#owner-text > a"
            author_name = WebDriverWait(driver, 1).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, author_name_selector))
            )
            return author_name.get_attribute('textContent')
        except Exception as e:
            logging.error(f"An error occurred while fetching the playlist name: {e}")
            return None

#----------------------------------Download Process-------------------------------------#

    # Override Method
    def download(self) -> None:
        def download_audio(audio_manager: YoutubeAudioManager) -> None:
            audio_manager.download()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(download_audio, audio_manager) for audio_manager in self.audio_managers]
            for future in futures:
                future.result()
        logging.debug("Downloading videos ...")

    # Override Function
    def extract_video_id(self, url: str) -> Optional[str]:
        query = urlparse(url).query
        params = parse_qs(query)
        return params.get('v', [None])[0]

    # Override Function
    def extract_image(self) -> str:
        title = self.soup.find('meta', property='og:image')['content']
        print(f"Extracting image: {title}")
        return title
