from core.playlist_managers.IPlaylistManager import IPlaylistManager
from concurrent.futures import ThreadPoolExecutor
from core.audio_managers.SpotifyAudioManager import SpotifyAudioManager
from core.utils import (
    get_spotify_meta_content_from_html,
    get_spotify_playlist_id,
    get_spotify_playlist_data_from_embed,
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

    def __load_embed_data(self) -> Dict[str, object]:
        try:
            data = get_spotify_playlist_data_from_embed(self.playlist_url)
            logging.debug(
                "Spotify embed source found %s tracks for %s",
                data.get("track_count", 0),
                self.playlist_url,
            )
            return data
        except Exception as e:
            logging.debug(f"Unable to retrieve Spotify embed data: {e}")
            return {"track_urls": [], "track_count": 0}

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

        embed_title = self.__load_embed_data().get("title")
        if embed_title:
            return str(embed_title).strip()

        oembed_title = self.__load_oembed_data().get("title")
        if oembed_title:
            return str(oembed_title).strip()

        return "Spotify playlist"

    def extract_image(self) -> str:
        image_url = self.__get_meta_content(property_="og:image")

        if image_url:
            return image_url

        embed_image = self.__load_embed_data().get("image")
        if embed_image:
            return str(embed_image).strip()

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
        embed_data = self.__load_embed_data()
        embed_urls = embed_data.get("track_urls")
        if not isinstance(embed_urls, list):
            embed_urls = []

        if metadata_urls and (metadata_total <= 0 or len(metadata_urls) >= metadata_total):
            urls = metadata_urls[:metadata_total] if metadata_total > 0 else metadata_urls
            if len(urls) >= len(embed_urls):
                print(f"{len(urls)} songs found from Spotify metadata.")
                logging.debug(
                    "Spotify source counts: metadata=%s embed=%s selenium=not_used total=%s",
                    len(metadata_urls),
                    len(embed_urls),
                    metadata_total,
                )
                return urls

        if metadata_urls and metadata_total > 0:
            print(
                f"Spotify metadata is incomplete: {len(metadata_urls)}/{metadata_total} songs. "
                "Falling back to playlist-scoped Selenium collection."
            )

        # Fallback: use Selenium but scope extraction to playlist rows only.
        # Spotify can append a "Recommandés" / "Recommended" section after
        # the playlist; those track links must not be downloaded.
        driver = get_selenium_driver_for_spotify(self.playlist_url)
        try:
            total_songs = get_spotify_total_songs(driver) or metadata_total
            selenium_urls = get_spotify_url_list(driver, total_songs)
            effective_total = max(total_songs, metadata_total, len(embed_urls))
            candidates = [
                ("metadata", metadata_urls),
                ("embed", [str(url) for url in embed_urls]),
                ("selenium", selenium_urls),
            ]
            usable_candidates = [
                (source, urls)
                for source, urls in candidates
                if urls
            ]

            if effective_total > 0:
                complete_candidates = [
                    (source, urls)
                    for source, urls in usable_candidates
                    if len(urls) >= effective_total
                ]
                if complete_candidates:
                    source, urls = complete_candidates[0]
                    selected_urls = urls[:effective_total]
                else:
                    source, selected_urls = max(
                        usable_candidates or [("selenium", selenium_urls)],
                        key=lambda item: len(item[1]),
                    )
            else:
                source, selected_urls = max(
                    usable_candidates or [("selenium", selenium_urls)],
                    key=lambda item: len(item[1]),
                )

            logging.debug(
                "Spotify source counts: metadata=%s embed=%s selenium=%s total=%s selected=%s selected_count=%s",
                len(metadata_urls),
                len(embed_urls),
                len(selenium_urls),
                effective_total,
                source,
                len(selected_urls),
            )
            print(f"{len(selected_urls)} songs found from Spotify {source}.")
            return selected_urls
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
