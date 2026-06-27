from core.playlist_managers.IPlaylistManager import IPlaylistManager
from concurrent.futures import ThreadPoolExecutor
from core.audio_managers.SpotifyAudioManager import SpotifyAudioManager
from core.utils import (
    get_spotify_meta_content_from_html,
    get_spotify_playlist_id,
    get_spotify_total_songs,
    get_spotify_total_songs_from_html,
    get_spotify_url_list,
    get_spotify_urls_from_html,
    get_selenium_driver_for_spotify,
)
import logging
import re
import time
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


class SpotifyPlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url: str, path_to_save_audio: str) -> None:
        self.playlist_url = playlist_url
        self.soup: Optional[BeautifulSoup] = None
        self._oembed_data: Optional[Dict[str, str]] = None
        logging.debug("Initializing SpotifyPlaylistManager")
        super().__init__(playlist_url, path_to_save_audio, get_spotify_playlist_id(playlist_url))

#----------------------------------------GETTER----------------------------------------#

    def __load_spotify_selenium_soup(self) -> None:
        driver = get_selenium_driver_for_spotify(self.playlist_url)
        html = ""

        try:
            # Spotify first returns a generic shell, then hydrates playlist metadata.
            # Wait until the stable playlist meta tags are present.
            for _ in range(24):
                html = driver.page_source

                has_title = get_spotify_meta_content_from_html(html, property_="og:title") is not None
                has_tracks = len(get_spotify_urls_from_html(html)) > 0

                if has_title or has_tracks:
                    break

                time.sleep(0.5)

            self.soup = BeautifulSoup(html, "lxml")
        finally:
            driver.quit()

    def __ensure_soup_loaded(self, force_reload: bool = False) -> None:
        if self.soup is not None and not force_reload:
            return

        self.__load_spotify_selenium_soup()

    def __get_meta_content(self, *, name: str | None = None, property_: str | None = None) -> Optional[str]:
        self.__ensure_soup_loaded()

        if self.soup is None:
            return None

        if name is not None:
            tag = self.soup.find("meta", attrs={"name": name})
        else:
            tag = self.soup.find("meta", attrs={"property": property_})

        if tag is None:
            return None

        content = tag.get("content")
        if not content:
            return None

        return str(content).strip()

    def __load_oembed_data(self) -> Dict[str, str]:
        if self._oembed_data is not None:
            return self._oembed_data

        self._oembed_data = {}

        try:
            oembed_url = f"https://open.spotify.com/oembed?url={quote(self.playlist_url, safe='')}"
            response = requests.get(oembed_url, timeout=15)
            response.raise_for_status()
            payload = response.json()

            if isinstance(payload, dict):
                self._oembed_data = payload
        except Exception as e:
            logging.warning(f"Unable to retrieve Spotify oEmbed metadata: {e}")

        return self._oembed_data

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
        title = self.__get_meta_content(property_="og:title")

        if title:
            return title

        oembed_title = self.__load_oembed_data().get("title")
        if oembed_title:
            return str(oembed_title).strip()

        return "Spotify playlist"

    def extract_image(self) -> str:
        image_url = self.__get_meta_content(property_="og:image")

        if image_url:
            return image_url

        oembed_thumbnail = self.__load_oembed_data().get("thumbnail_url")
        if oembed_thumbnail:
            return str(oembed_thumbnail).strip()

        raise ValueError("Unable to find Spotify playlist cover image.")

    # Override Method
    def get_video_urls(self) -> List[str]:
        # Force a fresh Selenium render for update, otherwise an old cached soup may
        # miss tracks added after the manager was initialized.
        self.__ensure_soup_loaded(force_reload=True)

        html = str(self.soup) if self.soup is not None else ""
        metadata_urls = get_spotify_urls_from_html(html)
        metadata_total = get_spotify_total_songs_from_html(html)

        if metadata_urls:
            urls = metadata_urls[:metadata_total] if metadata_total > 0 else metadata_urls
            print(f"{len(urls)} songs found from Spotify metadata.")
            return urls

        # Last fallback: use Selenium track rows only. Do not scan the whole page
        # with a global /track/ regex because Spotify also injects recommendations
        # and player state links that are not part of the playlist.
        driver = get_selenium_driver_for_spotify(self.playlist_url)
        try:
            total_songs = get_spotify_total_songs(driver) or metadata_total
            urls = get_spotify_url_list(driver, total_songs)
            print(f"{len(urls)} songs found.")
            return urls
        finally:
            driver.quit()

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
