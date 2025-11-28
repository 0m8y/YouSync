from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from abc import ABC, abstractmethod
from threading import Lock
from typing import List

import logging
import requests
import os
from PIL import Image, UnidentifiedImageError

from core.utils import check_yousync_folder
from core.audio_managers.IAudioManager import IAudioManager
from core.storage.PlaylistData import PlaylistData
from core.storage.PlaylistDataStore import PlaylistDataStore


class IPlaylistManager(ABC):

    def __init__(self, playlist_url: str, path_to_save_audio: str, playlist_id: str) -> None:
        logging.debug("Initializing IPlaylistManager")

        self.lock = Lock()
        self.playlist_url = playlist_url
        self.path_to_save_audio = path_to_save_audio
        self.id = playlist_id

        # JSON playlist data file path
        self.playlist_data_filepath = os.path.join(
            self.path_to_save_audio, ".yousync", f"{self.id}.json"
        )

        check_yousync_folder(os.path.join(self.path_to_save_audio, ".yousync"))

        # DataStore & cached data object
        self.data_store = PlaylistDataStore(self.playlist_data_filepath, self.lock)
        self.playlist_data: PlaylistData = None

        # Loaded audio managers
        self.audio_managers: List[IAudioManager] = []

        # Initialize folder & load data
        self.__recover_or_create_json_data()

    # ==================================================================================
    #                              INITIALIZATION
    # ==================================================================================

    def __recover_or_create_json_data(self) -> None:

        # Ensure .yousync folder exists
        check_yousync_folder(os.path.join(self.path_to_save_audio, ".yousync"))

        # Load or create playlist data
        self.playlist_data = self.data_store.load()

        if self.playlist_data.playlist_url == "":
            self.playlist_data.playlist_url = self.playlist_url
            self.playlist_data.path_to_save_audio = self.path_to_save_audio
            self.playlist_data.title = self.get_playlist_title()
            self.data_store.save(self.playlist_data)

        # Load existing audios (as AudioManagers)
        self.__load_audio_managers()

        # Download playlist cover
        self.download_cover_image()

        logging.debug(f"Playlist {self.id} loaded successfully.")

    def __load_audio_managers(self) -> None:
        urls = [audio.url for audio in self.playlist_data.audios]

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures: List[Future] = [
                executor.submit(self.new_audio_manager, url) for url in urls
            ]

            for future in as_completed(futures):
                try:
                    am = future.result()
                    self.audio_managers.append(am)
                except Exception as e:
                    logging.error(f"Error while loading audio manager: {e}", exc_info=True)

    # ==================================================================================
    #                              COVER IMAGE
    # ==================================================================================

    def download_cover_image(self) -> None:
        image_path = os.path.join(
            self.path_to_save_audio, ".yousync", f"{self.id}.jpg"
        )

        if self.__is_image_valid(image_path):
            return

        cover_url = self.extract_image()
        response = requests.get(cover_url)

        if response.status_code == 200:
            with open(image_path, "wb") as img_file:
                img_file.write(response.content)
            print(f"Cover image saved at {image_path}")
        else:
            print(f"Failed to download cover: HTTP {response.status_code}")

    def __is_image_valid(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        try:
            with Image.open(path) as img:
                img.verify()
            return True
        except (UnidentifiedImageError, OSError):
            try:
                os.remove(path)
            except:
                pass
            return False

    # ==================================================================================
    #                              UPDATE PLAYLIST
    # ==================================================================================

    def update(self) -> None:
        print("Updating playlist " + self.id)

        new_urls = self.get_video_urls()
        old_urls = [audio.url for audio in self.playlist_data.audios]

        # Add new videos
        for url in new_urls:
            if url not in old_urls:
                print("New video: " + url)
                am = self.new_audio_manager(url)
                am.update_data()
                self.playlist_data.audios.append(am.metadata)
                self.audio_managers.append(am)

        # Remove deleted videos
        for old_url in list(old_urls):
            if old_url not in new_urls:
                self.__remove_audio(old_url)

        # Save playlist data
        self.data_store.save(self.playlist_data)

    # ==================================================================================
    #                              PATH UPDATE
    # ==================================================================================

    def update_path(self, new_path: str) -> None:
        old_path = self.path_to_save_audio
        self.path_to_save_audio = new_path

        for am in self.audio_managers:
            am.update_path(new_path, old_path)

        self.playlist_data.path_to_save_audio = new_path

        new_json_path = os.path.join(new_path, ".yousync", f"{self.id}.json")
        self.playlist_data_filepath = new_json_path
        self.data_store.filepath = new_json_path

        self.data_store.save(self.playlist_data)

    # ==================================================================================
    #                              AUDIO REMOVE / ADD
    # ==================================================================================

    def __remove_audio(self, url: str) -> None:
        # Remove file + metadata
        for am in list(self.audio_managers):
            if am.get_url() == url:
                am.delete()
                self.audio_managers.remove(am)
                break

        # Remove from playlist data
        self.playlist_data.audios = [
            a for a in self.playlist_data.audios if a.url != url
        ]

        print(f"Audio removed: {url}")

    # ==================================================================================
    #                              PUBLIC GETTERS
    # ==================================================================================

    def get_audio_managers(self) -> List[IAudioManager]:
        return self.audio_managers

    # ==================================================================================
    #                              ABSTRACT METHODS
    # ==================================================================================

    @abstractmethod
    def new_audio_manager(self, url: str) -> IAudioManager:
        pass

    @abstractmethod
    def get_video_urls(self) -> List[str]:
        pass

    @abstractmethod
    def get_playlist_title(self) -> str:
        pass

    @abstractmethod
    def download(self) -> None:
        pass

    @abstractmethod
    def extract_video_id(self, url: str) -> str:
        pass

    @abstractmethod
    def extract_image(self) -> str:
        pass
