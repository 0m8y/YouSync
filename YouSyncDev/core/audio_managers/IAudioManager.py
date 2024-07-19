from abc import ABC, abstractmethod
import eyed3.id3, requests, json, os
from threading import Lock
from typing import Dict, List, Any

class IAudioManager(ABC):

    def __init__(self, url: str, path_to_save_audio: str, data_filepath: str, id: str, video_title: str, lock: Lock) -> None:
        self.lock = lock
        self.url = url
        self.path_to_save_audio = path_to_save_audio
        self.data_filepath = data_filepath
        self.id = id
        self.video_title = video_title
        self.path_to_save_audio_with_title = f"{self.path_to_save_audio}\\{self.video_title}.mp3"

        self.is_downloaded = False
        self.metadata_updated = False
        self.title: str = ""
        self.artist: str = ""
        self.album: str = ""
        self.image_url: str = ""

        data = self.load_data()
        if not any(item['url'] == self.url for item in data):
            data.append(self.to_dict())
            self.save_data_to_file(data)
        else:
            for item in data:
                if item['url'] == self.url:
                    self.__from_dict(item)

    def load_data(self) -> List[Dict[str, Any]]:
        try:
            with open(self.data_filepath, 'r') as file:
                data = json.load(file)
            return data.get("audios", [])
        except FileNotFoundError:
            return []

    def download(self) -> None:
        if self.is_downloaded:
            if not self.metadata_updated:
                self.add_metadata()
                return
            return

        print("downloading " + self.url + "...")
        self.download_audio()

        print(self.url + " is downloaded!")
        self.is_downloaded = True
        self.__update_is_downloaded()
        self.add_metadata()

    @abstractmethod
    def download_audio(self) -> None:
        pass

    def register_metadata(self, video_title: str, title: str, artist: str, album: str, image_url: str) -> None:
        self.video_title = video_title
        self.title = title
        self.artist = artist
        self.album = album
        self.image_url = image_url

        audiofile = eyed3.load(self.path_to_save_audio_with_title)
        if audiofile.tag is None:
            audiofile.initTag()

        audiofile.tag.title = self.title
        audiofile.tag.album = self.album
        audiofile.tag.artist = self.artist
        if self.image_url:
            response = requests.get(self.image_url)
            if response.status_code == 200:
                audiofile.tag.images.set(3, response.content, 'image/jpeg')
            else:
                self.image_url = None
        audiofile.tag.save(version=eyed3.id3.ID3_V2_3)
        print("Metadata is added in " + self.url)
        self.metadata_updated = True
        self.update_data()

    @abstractmethod
    def add_metadata(self) -> None:
        pass

#----------------------------------------UPDATE-----------------------------------------#

    def update_data(self) -> None:
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['is_downloaded'] = self.is_downloaded
                item['metadata_updated'] = self.metadata_updated
                item['video_title'] = self.video_title
                item['title'] = self.title
                item['artist'] = self.artist
                item['album'] = self.album
                item['image_url'] = self.image_url
                break
        self.save_data_to_file(data)

    def __update_is_downloaded(self) -> None:
        data = self.load_data()
        updated = False
        for item in data:
            if item['url'] == self.url and not item['is_downloaded']:
                item['is_downloaded'] = self.is_downloaded
                updated = True
                break
        if updated:
            self.save_data_to_file(data)

    def __update_metadata_updated(self) -> None:
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['metadata_updated'] = self.metadata_updated

    def __update_video_title(self) -> None:
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['video_title'] = self.video_title

    def __update_title(self) -> None:
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['title'] = self.title

    def __update_artist(self) -> None:
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['artist'] = self.artist

    def __update_album(self) -> None:
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['album'] = self.album

    def __update_image_url(self) -> None:
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['image_url'] = self.image_url

    def __delete_audio_file(self) -> None:
        if os.path.exists(self.path_to_save_audio_with_title):
            os.remove(self.path_to_save_audio_with_title)
            print(f"Fichier audio supprimé : {self.path_to_save_audio_with_title}")

    def __delete_audio_info(self) -> None:
        audios_data = self.load_data()
        audios_data = [audio for audio in audios_data if audio['url'] != self.url]
        self.save_data_to_file(audios_data)
        print("Informations audio supprimées du fichier JSON.")

    def delete(self) -> None:
        try:
            self.__delete_audio_file()
            self.__delete_audio_info()
        except Exception as e:
            print(f"Erreur lors de la suppression de l'audio : {e}")

    def update_path(self, new_path: str, old_path: str) -> None:
        current_path = os.path.dirname(self.path_to_save_audio_with_title)
        if current_path == old_path:
            new_path_to_save_audio_with_title = os.path.join(new_path, f"{self.video_title}.mp3")
            self.path_to_save_audio = new_path
            self.path_to_save_audio_with_title = new_path_to_save_audio_with_title

            data = self.load_data()
            for item in data:
                if item['url'] == self.url:
                    item['path_to_save_audio_with_title'] = self.path_to_save_audio_with_title
                    break
            self.save_data_to_file(data)

#-------------------------------------Load & Save--------------------------------------#

    def save_data_to_file(self, audios_data: List[Dict[str, Any]]) -> None:
        with self.lock:
            try:
                with open(self.data_filepath, 'r') as file:
                    data = json.load(file)
            except FileNotFoundError:
                data = {}

            data["audios"] = audios_data

            with open(self.data_filepath, 'w') as file:
                json.dump(data, file, indent=4)

#-----------------------------------------DICT------------------------------------------#

    def __from_dict(self, data: Dict[str, Any]) -> None:
        self.path_to_save_audio_with_title = data["path_to_save_audio_with_title"]
        self.is_downloaded = data["is_downloaded"]
        self.metadata_updated = data["metadata_updated"]
        self.video_title = data["video_title"]
        self.title = data["title"]
        self.artist = data["artist"]
        self.album = data["album"]
        self.image_url = data["image_url"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "path_to_save_audio_with_title": self.path_to_save_audio_with_title,
            "is_downloaded": self.is_downloaded,
            "metadata_updated": self.metadata_updated,
            "video_title": self.video_title,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "image_url": self.image_url
        }

    def get_url(self) -> str:
        return self.url
