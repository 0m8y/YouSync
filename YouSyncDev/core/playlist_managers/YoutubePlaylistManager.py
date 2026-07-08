from core.playlist_managers.IPlaylistManager import IPlaylistManager
from concurrent.futures import ThreadPoolExecutor
from core.audio_managers.YoutubeAudioManager import YoutubeAudioManager
from core.utils import get_youtube_playlist_id
import logging
from typing import Any, List, Optional
from urllib.parse import urlparse, parse_qs

class YoutubePlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url: str, path_to_save_audio: str) -> None:
        self.playlist_url = playlist_url
        self.soup = None
        logging.debug("Initializing YoutubePlaylistManager")
        super().__init__(playlist_url, path_to_save_audio, get_youtube_playlist_id(playlist_url))

#----------------------------------------GETTER----------------------------------------#

    def __ensure_soup_loaded(self):
        if self.soup is not None:
            return
        import requests
        from bs4 import BeautifulSoup

        response = requests.get(self.playlist_url)
        response.encoding = 'utf-8'
        self.soup = BeautifulSoup(response.text, 'lxml')

    # Override Method
    def new_audio_manager(self, url: str) -> Optional[YoutubeAudioManager]:
        try:
            audio_manager = YoutubeAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            return audio_manager
        except Exception as e:
            logging.error(f"Error initializing YoutubeAudioManager for {url}: {e}", exc_info=True)
            return None

    # Override Method
    def get_playlist_title(self) -> str:
        self.__ensure_soup_loaded()
        title = self.soup.find('meta', property='og:title')['content']
        print(f"title found: {title}")
        return title

    # Override Method
    def get_video_urls(self) -> List[str]:
        from yt_dlp import YoutubeDL

        print("🔗 Fast fetching playlist with yt_dlp (flat)...")
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'skip_download': True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(self.playlist_url, download=False)
                entries = result.get("entries", [])
                urls = [entry['url'] for entry in entries if 'url' in entry]

            print(f"🎥 {len(urls)} videos found (flat mode).")
            return urls
        except Exception as e:
            print(f"❌ yt_dlp extract_flat error: {e}")
            return []

    def __get_video_urls_from_driver(self, driver: Any) -> List[str]:
        from selenium.webdriver.common.by import By

        video_links = driver.find_elements(By.CSS_SELECTOR, 'a.yt-simple-endpoint.style-scope.ytd-playlist-video-renderer')
        urls = [video.get_attribute('href') for video in video_links if video.get_attribute('href') and 'watch?v=' in video.get_attribute('href')]
        recommended_videos_present = len(driver.find_elements(By.XPATH, "//div[@id='title' and contains(text(),'Vidéos recommandées')]")) > 0
        if recommended_videos_present:
            urls = urls[:-5]
        return urls

    def __get_author_name(self, driver: Any) -> Optional[str]:
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

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
        from pytubefix.exceptions import VideoUnavailable

        def download_audio(audio_manager: YoutubeAudioManager) -> None:
            if audio_manager is None:
                return

            try:
                audio_manager.download()
            except VideoUnavailable as e:
                logging.warning(f"YouTube video unavailable: {e}")
            except Exception as e:
                logging.error(f"Error while downloading YouTube audio: {e}", exc_info=True)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(download_audio, audio_manager)
                for audio_manager in self.audio_managers
                if audio_manager is not None
            ]
            for future in futures:
                future.result()

    # Override Function
    def extract_video_id(self, url: str) -> Optional[str]:
        query = urlparse(url).query
        params = parse_qs(query)
        return params.get('v', [None])[0]

    # Override Function
    def extract_image(self) -> str:
        self.__ensure_soup_loaded()
        title = self.soup.find('meta', property='og:image')['content']
        print(f"Extracting image: {title}")
        return title
