import os
import requests
import eyed3.id3
from threading import Lock
from typing import Dict, Any
from abc import ABC, abstractmethod

from core.storage.AudioDataStore import AudioDataStore


class IAudioManager(ABC):

    def __init__(self, url: str, path_to_save_audio: str, data_filepath: str, id: str, video_title: str, lock: Lock) -> None:
        self.lock = lock
        self.url = url
        self.id = id
        self.video_title = video_title
        self.path_to_save_audio = path_to_save_audio
        self.path_to_save_audio_with_title = os.path.join(self.path_to_save_audio, f"{self.video_title}.mp3")

        self.data_store = AudioDataStore(data_filepath, lock)

        self.is_downloaded = False
        self.metadata_updated = False
        self.title: str = ""
        self.artist: str = ""
        self.album: str = ""
        self.image_url: str = ""

        data = self.data_store.load_all()
        audio_data = next((item for item in data if item['url'] == self.url), None)
        if audio_data:
            self.__from_dict(audio_data)
        else:
            self.data_store.update_audio(self.to_dict())

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
        self.data_store.update_audio(self.to_dict())

    def __update_is_downloaded(self) -> None:
        self.is_downloaded = True
        self.data_store.update_audio(self.to_dict())

    def delete(self) -> None:
        try:
            if os.path.exists(self.path_to_save_audio_with_title):
                os.remove(self.path_to_save_audio_with_title)
                print(f"Fichier audio supprimé : {self.path_to_save_audio_with_title}")
            self.data_store.remove_audio(self.url)
        except Exception as e:
            print(f"Erreur lors de la suppression de l'audio : {e}")

    def update_path(self, new_path: str, old_path: str) -> None:
        current_path = os.path.dirname(self.path_to_save_audio_with_title)
        if current_path == old_path:
            new_path_to_save_audio_with_title = os.path.join(new_path, f"{self.video_title}.mp3")
            self.path_to_save_audio = new_path
            self.path_to_save_audio_with_title = new_path_to_save_audio_with_title
            updated_dict = self.to_dict()
            updated_dict["path_to_save_audio_with_title"] = self.path_to_save_audio_with_title
            self.data_store.update_audio(updated_dict)

#-----------------------------------------DICT------------------------------------------#


    def __from_dict(self, data: Dict[str, Any]) -> None:
        self.path_to_save_audio_with_title = data.get("path_to_save_audio_with_title", self.path_to_save_audio_with_title)
        self.is_downloaded = data.get("is_downloaded", False)
        self.metadata_updated = data.get("metadata_updated", False)
        self.video_title = data.get("video_title", self.video_title)
        self.title = data.get("title", "")
        self.artist = data.get("artist", "")
        self.album = data.get("album", "")
        self.image_url = data.get("image_url", "")

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
