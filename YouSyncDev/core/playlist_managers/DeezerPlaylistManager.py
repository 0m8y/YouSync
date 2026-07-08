from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import logging
import re

from core.audio_managers.DeezerAudioManager import DeezerAudioManager
from core.playlist_managers.IPlaylistManager import IPlaylistManager
from core.utils import (
    get_deezer_playlist_data,
    get_deezer_playlist_id,
    get_deezer_playlist_tracks,
    get_deezer_track_id,
)


class DeezerPlaylistManager(IPlaylistManager):
    def __init__(self, playlist_url: str, path_to_save_audio: str) -> None:
        self.playlist_url = playlist_url
        self.playlist_id = get_deezer_playlist_id(playlist_url)
        self._playlist_data: Optional[Dict] = None
        self._tracks: Optional[List[Dict]] = None
        self._tracks_by_url: Dict[str, Dict] = {}

        if not self.playlist_id:
            raise ValueError("Invalid Deezer playlist URL.")

        logging.debug("Initializing DeezerPlaylistManager")
        super().__init__(playlist_url, path_to_save_audio, self.playlist_id)

#----------------------------------------GETTER----------------------------------------#

    def __load_playlist_data(self) -> Dict:
        if self._playlist_data is None:
            self._playlist_data = get_deezer_playlist_data(self.playlist_id)

        return self._playlist_data

    def __load_tracks(self, force_reload: bool = False) -> List[Dict]:
        if self._tracks is not None and not force_reload:
            return self._tracks

        self._tracks = get_deezer_playlist_tracks(self.playlist_id)
        self._tracks_by_url = {
            str(track.get("url")): track
            for track in self._tracks
            if track.get("url")
        }
        return self._tracks

    def new_audio_manager(self, url: str) -> Optional[DeezerAudioManager]:
        try:
            if url is None:
                return None

            track_data = self._tracks_by_url.get(url)
            return DeezerAudioManager(
                url,
                self.path_to_save_audio,
                self.playlist_data_filepath,
                self.lock,
                track_data,
            )
        except Exception as e:
            logging.error(f"Error initializing DeezerAudioManager: {e}")
            print(f"Error initializing DeezerAudioManager: {e}")
            return None

    def get_playlist_title(self) -> str:
        data = self.__load_playlist_data()
        return str(data.get("title") or "Deezer playlist").strip()

    def extract_image(self) -> str:
        data = self.__load_playlist_data()
        image_url = (
            data.get("picture_xl")
            or data.get("picture_big")
            or data.get("picture_medium")
            or data.get("picture")
        )

        if not image_url:
            raise ValueError("Unable to find Deezer playlist cover image.")

        return str(image_url)

    def get_video_urls(self) -> List[str]:
        tracks = self.__load_tracks(force_reload=True)
        urls = [str(track.get("url")) for track in tracks if track.get("url")]
        print(f"{len(urls)} songs found from Deezer API.")
        return urls

#----------------------------------Download Process-------------------------------------#

    def download(self) -> None:
        def download_audio(audio_manager: DeezerAudioManager) -> None:
            audio_manager.download()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(download_audio, audio_manager)
                for audio_manager in self.audio_managers
                if audio_manager is not None
            ]
            for future in futures:
                future.result()

        logging.debug("Downloading Deezer videos ...")

    def extract_video_id(self, url: str) -> Optional[str]:
        track_id = get_deezer_track_id(url)

        if track_id:
            return track_id

        pattern = r"/track/(\d+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)

        return None
