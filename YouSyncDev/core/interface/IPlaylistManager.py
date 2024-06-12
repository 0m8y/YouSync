from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod
from threading import Lock
from core.utils import *
import logging
import json

class IPlaylistManager(ABC):
    
    def __init__(self, playlist_url, path_to_save_audio, playlist_id):
        logging.debug("Initializing IPlaylistManager")
        self.lock = Lock()
        self.playlist_url = playlist_url
        self.path_to_save_audio = path_to_save_audio
        self.id = playlist_id
        self.playlist_data_filepath = self.path_to_save_audio + "\\.yousync\\" + self.id + ".json"
        self.video_urls = []
        self.audio_managers = []

        self.__recover_or_create_json_data()

#-------------------------------------Get JSON Data--------------------------------------#

    def __recover_or_create_json_data(self):
        check_yousync_folder(os.path.join(self.path_to_save_audio, ".yousync"))

        if not os.path.exists(self.playlist_data_filepath):
            with open(self.playlist_data_filepath, 'w') as fichier:
                fichier.write("[]")
            self.__initialize_playlist_data()
        else:
            self.__get_video_urls_from_json()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.new_audio_manager, video_url) for video_url in self.video_urls]
            for future in futures:
                youtube_audio = future.result()
                self.audio_managers.append(youtube_audio)
        logging.debug(f"playlist {self.id} is loaded successfully")

    def __initialize_playlist_data(self):
        data = {
            "playlist_url": self.playlist_url,
            "path_to_save_audio": self.path_to_save_audio,
        }
        with self.lock:
            with open(self.playlist_data_filepath, 'w') as file:
                json.dump(data, file, indent=4)

    def __get_video_urls_from_json(self):
        data = self.__load_playlist_data()
        self.path_to_save_audio = data["path_to_save_audio"]
        audios = data["audios"]
        for audio in audios:
            self.video_urls.append(audio["url"])

#-------------------------------------Load & Save--------------------------------------#

    def __load_playlist_data(self):
        with self.lock:
            try:
                with open(self.playlist_data_filepath, 'r') as file:
                    return json.load(file)
            except FileNotFoundError:
                return {"playlist_url": self.playlist_url, "audios": []}

#-------------------------------------Public Function--------------------------------------#

    def update(self):
        print("Updating playlist " + self.id)
        #TODO: Not working, to update with new logic
        new_video_urls = self.get_video_urls()

        for new_video_url in new_video_urls:
            new_video_id = extract_video_id(new_video_url)
            existing_video_ids = [extract_video_id(video_url) for video_url in self.video_urls]
            if new_video_id not in existing_video_ids:
                self.__add_audio(self.new_audio_manager(new_video_url))

        for video_url in list(self.video_urls):
            video_id = extract_video_id(video_url)
            new_video_ids = [extract_video_id(new_video_url) for new_video_url in new_video_urls]
            if video_id not in new_video_ids:
                self.__remove_audio(video_url)

    def update_path(self, new_path):
        old_path = self.path_to_save_audio
        self.path_to_save_audio = new_path

        for audio_manager in self.audio_managers:
            audio_manager.update_path(new_path, old_path)

        self.playlist_data_filepath = os.path.join(new_path, '.yousync', f"{self.id}.json")

        data = self.__load_playlist_data()
        data['path_to_save_audio'] = new_path
        self.save_playlist_data(data)

    def save_playlist_data(self, data):
        with self.lock:
            with open(self.playlist_data_filepath, 'w') as file:
                json.dump(data, file, indent=4)

    def get_audio_managers(self):
        return self.audio_managers
    
    def __remove_audio(self, url):
        audio_manager_index = next((i for i, am in enumerate(self.audio_managers) if am.get_url() == url), None)

        if audio_manager_index is not None:
            self.audio_managers[audio_manager_index].delete()

            del self.audio_managers[audio_manager_index]

            self.video_urls = [video_url for video_url in self.video_urls if video_url != url]

            print(f"Audio supprimé : {url}")
        else:
            print(f"Audio non trouvé durant la supression : {url}")

    def __add_audio(self, audio_manager):
            audio_manager.update_data()
            self.audio_managers.append(audio_manager)
            self.video_urls.append(audio_manager.url)

    @abstractmethod
    def new_audio_manager(self, url):
        pass

    @abstractmethod
    def get_video_urls(self):
        pass

    @abstractmethod
    def get_playlist_name(self, driver):
        pass

#----------------------------------Download Process-------------------------------------#

    @abstractmethod
    def download(self):
        pass

