from core.playlist_managers.IPlaylistManager import IPlaylistManager
from concurrent.futures import ThreadPoolExecutor
from core.audio_managers.SpotifyAudioManager import SpotifyAudioManager
from core.utils import get_spotify_playlist_id, get_selenium_driver_for_spotify, get_soundcloud_total_songs, get_soundcloud_url_list
import logging
import requests
from typing import List, Optional
from bs4 import BeautifulSoup
import re


class SpotifyPlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url: str, path_to_save_audio: str) -> None:
        response = requests.get(playlist_url)
        response.encoding = "utf-8"
        self.html_page = response.text
        self.soup = BeautifulSoup(self.html_page, 'html.parser')
        logging.debug("Initializing SpotifyPlaylistManager")
        super().__init__(playlist_url, path_to_save_audio, get_spotify_playlist_id(playlist_url))

#----------------------------------------GETTER----------------------------------------#

    # Override Method
    def new_audio_manager(self, url: str) -> Optional[SpotifyAudioManager]:
        try:
            logging.debug("Creating SpotifyAudioManager")
            if url is None:
                return None
            audio_manager = SpotifyAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            return audio_manager
        except Exception as e:
            logging.error(f"Error initializing SpotifyAudioManager: {e}")
            print(f"Error initializing SpotifyAudioManager: {e}")
            return None

    # Override Method
    def get_playlist_title(self) -> str:
        return self.soup.find('meta', property='og:title')['content']

    def extract_image(self) -> str:
        return self.soup.find('meta', property='og:image')['content']

    # Override Method
    def get_video_urls(self) -> List[str]:
        driver = get_selenium_driver_for_spotify(self.playlist_url)
        driver.execute_script("document.body.style.zoom = '0.001'")
        total_songs = get_soundcloud_total_songs(driver)
        urls = get_soundcloud_url_list(driver, total_songs)
        print(f"{len(urls)} songs found.")
        driver.quit()
        return urls

#----------------------------------Download Process-------------------------------------#

    # Override Method
    def download(self) -> None:
        def download_audio(audio_manager: SpotifyAudioManager) -> None:
            audio_manager.download()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(download_audio, audio_manager) for audio_manager in self.audio_managers]
            for future in futures:
                future.result()
        logging.debug("Downloading videos ...")

    # Override Function
    def extract_video_id(self, url: str) -> Optional[str]:
        pattern = r"track/([a-zA-Z0-9]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
