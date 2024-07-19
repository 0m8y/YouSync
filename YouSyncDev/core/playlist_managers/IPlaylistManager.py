from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from abc import ABC, abstractmethod
from threading import Lock
from core.utils import check_yousync_folder
import logging
import requests
import json
import os
from typing import List, Optional, Dict, Any
from core.audio_managers.IAudioManager import IAudioManager

class IPlaylistManager(ABC):

    def __init__(self, playlist_url: str, path_to_save_audio: str, playlist_id: str) -> None:
        logging.debug("Initializing IPlaylistManager")
        self.lock = Lock()
        self.playlist_url = playlist_url
        self.path_to_save_audio = path_to_save_audio
        self.id = playlist_id
        self.playlist_data_filepath = os.path.join(self.path_to_save_audio, ".yousync", f"{self.id}.json")
        self.video_urls: List[str] = []
        self.audio_managers: List[IAudioManager] = []

        self.__recover_or_create_json_data()

#-------------------------------------Get JSON Data--------------------------------------#

    def __recover_or_create_json_data(self) -> None:
        check_yousync_folder(os.path.join(self.path_to_save_audio, ".yousync"))

        if not os.path.exists(self.playlist_data_filepath):
            with open(self.playlist_data_filepath, 'w') as fichier:
                fichier.write("[]")
            self.__initialize_playlist_data()
        else:
            self.__get_video_urls_from_json()

        try:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures: List[Future] = [executor.submit(self.new_audio_manager, video_url) for video_url in self.video_urls]

                for future in as_completed(futures):
                    try:
                        youtube_audio = future.result()
                        self.audio_managers.append(youtube_audio)
                    except Exception as e:
                        logging.error(f"Error processing future: {e}", exc_info=True)

            if self.title is None:
                self.title = self.get_playlist_title()
            self.download_cover_image()

            logging.debug(f"playlist {self.id} is loaded successfully")
        except Exception as e:
            logging.error(f"Error in load_audio_managers: {e}", exc_info=True)

    def __initialize_playlist_data(self) -> None:
        self.title = self.get_playlist_title()
        data = {
            "playlist_url": self.playlist_url,
            "path_to_save_audio": self.path_to_save_audio,
            "title": self.title,
        }
        with self.lock:
            with open(self.playlist_data_filepath, 'w') as file:
                json.dump(data, file, indent=4)

    def __get_video_urls_from_json(self) -> None:
        data = self.__load_playlist_data()
        self.path_to_save_audio = data.get("path_to_save_audio", self.path_to_save_audio)
        self.title = data.get("title", None)

        if self.title is None:
            self.title = self.get_playlist_title()
            data['title'] = self.title
            self.save_playlist_data(data)

        audios = data.get("audios", [])
        for audio in audios:
            self.video_urls.append(audio["url"])

    def download_cover_image(self) -> None:
        logging.debug("Downloading cover image...")
        yousync_path = os.path.join(self.path_to_save_audio, '.yousync')
        image_path = os.path.join(yousync_path, f"{self.id}.jpg")
        if os.path.exists(image_path):
            logging.debug("Cover image is already downloaded")
            return
        cover_image_url = self.extract_image()
        logging.debug(f"Cover image url: {cover_image_url}, playlist: {self.playlist_url}")
        response = requests.get(cover_image_url)
        if response.status_code == 200:
            with open(image_path, 'wb') as img_file:
                img_file.write(response.content)
            print(f"Image enregistrée à: {image_path}")
        else:
            print(f"Erreur lors du téléchargement de l'image: {response.status_code}")

#-------------------------------------Load & Save--------------------------------------#

    def __load_playlist_data(self) -> Dict[str, Any]:
        with self.lock:
            try:
                with open(self.playlist_data_filepath, 'r') as file:
                    return json.load(file)
            except FileNotFoundError:
                return {"playlist_url": self.playlist_url, "audios": []}

#-------------------------------------Public Function--------------------------------------#

    def update(self) -> None:
        print("Updating playlist " + self.id)
        try:
            new_video_urls = self.get_video_urls()

            for new_video_url in new_video_urls:
                new_video_id = self.extract_video_id(new_video_url)
                existing_video_ids = [self.extract_video_id(video_url) for video_url in self.video_urls]
                if new_video_id not in existing_video_ids:
                    print("new video url: " + new_video_url)
                    self.__add_audio(self.new_audio_manager(new_video_url))

            for video_url in list(self.video_urls):
                video_id = self.extract_video_id(video_url)
                new_video_ids = [self.extract_video_id(new_video_url) for new_video_url in new_video_urls]
                if video_id not in new_video_ids:
                    self.__remove_audio(video_url)
        except Exception as e:
            raise Exception(f"Update Error: {e}")

    def update_path(self, new_path: str) -> None:
        old_path = self.path_to_save_audio
        self.path_to_save_audio = new_path

        for audio_manager in self.audio_managers:
            audio_manager.update_path(new_path, old_path)

        self.playlist_data_filepath = os.path.join(new_path, '.yousync', f"{self.id}.json")

        data = self.__load_playlist_data()
        data['path_to_save_audio'] = new_path
        self.save_playlist_data(data)

    def save_playlist_data(self, data: Dict[str, Any]) -> None:
        with self.lock:
            with open(self.playlist_data_filepath, 'w') as file:
                json.dump(data, file, indent=4)

    def get_audio_managers(self) -> List[IAudioManager]:
        return self.audio_managers
    
    def __remove_audio(self, url: str) -> None:
        audio_manager_index = next((i for i, am in enumerate(self.audio_managers) if am.get_url() == url), None)

        if audio_manager_index is not None:
            self.audio_managers[audio_manager_index].delete()

            del self.audio_managers[audio_manager_index]

            self.video_urls = [video_url for video_url in self.video_urls if video_url != url]

            print(f"Audio supprimé : {url}")
        else:
            print(f"Audio non trouvé durant la supression : {url}")

    def __add_audio(self, audio_manager: IAudioManager) -> None:
        audio_manager.update_data()
        self.audio_managers.append(audio_manager)
        self.video_urls.append(audio_manager.get_url())

    @abstractmethod
    def new_audio_manager(self, url: str) -> IAudioManager:
        pass

    @abstractmethod
    def get_video_urls(self) -> List[str]:
        pass

    @abstractmethod
    def get_playlist_title(self) -> str:
        pass

#----------------------------------Download Process-------------------------------------#

    @abstractmethod
    def download(self) -> None:
        pass

    @abstractmethod
    def extract_video_id(self, url: str) -> str:
        pass

    @abstractmethod
    def extract_image(self) -> str:
        pass
