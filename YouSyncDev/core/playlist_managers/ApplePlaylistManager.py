import logging
import requests
from core.playlist_managers.IPlaylistManager import IPlaylistManager
from concurrent.futures import ThreadPoolExecutor
from core.audio_managers.AppleAudioManager import AppleAudioManager
from core.utils import get_selenium_driver_for_apple, scroll_down_apple_page
from typing import List, Optional
from bs4 import BeautifulSoup
import re


class ApplePlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url: str, path_to_save_audio: str) -> None:
        self.html_page = requests.get(playlist_url).text
        self.soup = BeautifulSoup(self.html_page, 'html.parser')
        logging.debug("Initializing ApplePlaylistManager")
        super().__init__(playlist_url, path_to_save_audio, self.get_apple_playlist_id())

#----------------------------------------GETTER----------------------------------------#

    def get_apple_playlist_id(self):
        return self.soup.find('meta', attrs={'name': 'apple:content_id'})['content'].replace('-', '').replace('.', '')

    # Override Method
    def new_audio_manager(self, url: str) -> Optional[AppleAudioManager]:
        try:
            logging.debug("Creating AppleAudioManager")
            if url is None:
                return None
            audio_manager = AppleAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            return audio_manager
        except Exception as e:
            logging.error(f"Error initializing AppleAudioManager: {e}")
            print(f"Error initializing AppleAudioManager: {e}")
            return None

    # Override Method
    def get_playlist_title(self) -> str:
        return self.soup.find('meta', attrs={'name': 'apple:title'})['content']

    # Override Function
    def extract_image(self) -> str:
        return self.soup.find('meta', property='og:image')['content']

    # Override Method
    def get_video_urls(self) -> List[str]:
        driver = get_selenium_driver_for_apple(self.playlist_url)

        scroll_down_apple_page(driver)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        song_links = soup.select('a[data-testid="track-seo-link"]')
        urls = {link['href'] for link in song_links}

        driver.quit()
        return urls

#----------------------------------Download Process-------------------------------------#

    # Override Method
    def download(self) -> None:
        def download_audio(audio_manager: AppleAudioManager) -> None:
            audio_manager.download()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(download_audio, audio_manager) for audio_manager in self.audio_managers]
            for future in futures:
                future.result()
        logging.debug("Downloading videos ...")

    # Override Function
    def extract_video_id(self, url: str) -> Optional[str]:
        pattern = r"/song/[^/]+/([0-9]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
