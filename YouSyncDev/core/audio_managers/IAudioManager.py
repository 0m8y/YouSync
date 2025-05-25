import os
import requests
import eyed3.id3
from threading import Lock
from typing import Dict, Any
from abc import ABC, abstractmethod

from core.storage.AudioMetadata import AudioMetadata
from core.storage.AudioDataStore import AudioDataStore


class IAudioManager(ABC):

    def __init__(self, url: str, path_to_save_audio: str, data_filepath: str, id: str, video_title: str, lock: Lock) -> None:
        self.lock = lock
        self.url = url
        self.id = id
        self.video_title = video_title
        self.path_to_save_audio = path_to_save_audio

        self.data_store = AudioDataStore(data_filepath, lock)

        self.metadata = AudioMetadata(
            url=url,
            path_to_save_audio_with_title=os.path.join(self.path_to_save_audio, f"{self.video_title}.mp3"),
            video_title=video_title,
            title="", artist="", album="", image_url=""
        )

        data = self.data_store.load_all()
        existing = next((item for item in data if item.url == self.url), None)
        if existing:
            self.__from_dict(existing)
        else:
            self.data_store.update_audio(self.metadata)

    def download(self) -> None:
        if self.metadata.is_downloaded:
            if not self.metadata.metadata_updated:
                self.add_metadata()
                return
            return

        print("downloading " + self.url + "...")
        self.download_audio()

        print(self.url + " is downloaded!")
        self.metadata.is_downloaded = True
        self.__update_is_downloaded()
        self.add_metadata()

    @abstractmethod
    def download_audio(self) -> None:
        pass

    def register_metadata(self, video_title: str, title: str, artist: str, album: str, image_url: str) -> None:
        self.video_title = video_title
        self.metadata.title = title
        self.metadata.artist = artist
        self.metadata.album = album
        self.metadata.image_url = image_url

        audiofile = eyed3.load(self.metadata.path_to_save_audio_with_title)
        if audiofile.tag is None:
            audiofile.initTag()

        audiofile.tag.title = self.metadata.title
        audiofile.tag.album = self.metadata.album
        audiofile.tag.artist = self.metadata.artist
        if self.metadata.image_url:
            response = requests.get(self.metadata.image_url)
            if response.status_code == 200:
                audiofile.tag.images.set(3, response.content, 'image/jpeg')
            else:
                self.metadata.image_url = None
        audiofile.tag.save(version=eyed3.id3.ID3_V2_3)
        print("Metadata is added in " + self.url)
        self.metadata.metadata_updated = True
        self.update_data()

    @abstractmethod
    def add_metadata(self) -> None:
        pass

#----------------------------------------UPDATE-----------------------------------------#

    def update_data(self) -> None:
        self.data_store.update_audio(self.metadata)

    def __update_is_downloaded(self) -> None:
        self.metadata.is_downloaded = True
        self.data_store.update_audio(self.metadata)

    def delete(self) -> None:
        try:
            if os.path.exists(self.metadata.path_to_save_audio_with_title):
                os.remove(self.metadata.path_to_save_audio_with_title)
                print(f"Fichier audio supprimé : {self.metadata.path_to_save_audio_with_title}")
            self.data_store.remove_audio(self.url)
        except Exception as e:
            print(f"Erreur lors de la suppression de l'audio : {e}")

    def update_path(self, new_path: str, old_path: str) -> None:
        current_path = os.path.dirname(self.metadata.path_to_save_audio_with_title)
        if current_path == old_path:
            self.path_to_save_audio = new_path
            self.metadata.path_to_save_audio_with_title = os.path.join(new_path, f"{self.video_title}.mp3")
            self.data_store.update_audio(self.metadata)

#-----------------------------------------DICT------------------------------------------#

    def __from_dict(self, metadata: AudioMetadata) -> None:
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return self.metadata.to_dict()

    def get_url(self) -> str:
        return self.url
