from core.audio_managers.IAudioManager import IAudioManager
from core.utils import extract_json_object, get_cached_video_title, get_cached_video_id

from moviepy import AudioFileClip
from bs4 import BeautifulSoup
from pytubefix import YouTube
from threading import Lock
import requests
import tempfile
import json
import os


class YoutubeAudioManager(IAudioManager):

    def __init__(self, url: str, path_to_save_audio: str, data_filepath: str, lock: Lock) -> None:
        self.url = url
        self.yt = None
        cached_title = get_cached_video_title(url, data_filepath) or self.__extract_title(True)
        video_id = get_cached_video_id(url, data_filepath) or self.__get_video_id()
        super().__init__(url, path_to_save_audio, data_filepath, video_id, cached_title, lock)

#----------------------------------Download Process-------------------------------------#

    def __ensure_youtube_loaded(self):
        if self.yt:
            return
        self.yt = YouTube(self.url)

    def __get_video_id(self):
        self.__ensure_youtube_loaded()
        return self.yt.video_id

    #Override Function
    def download_audio(self) -> None:
        self.__ensure_youtube_loaded()
        audio_stream = self.yt.streams.filter(only_audio=True).first()

        temp_dir = tempfile.gettempdir()
        downloaded_file = audio_stream.download(output_path=temp_dir)

        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(self.metadata.path_to_save_audio_with_title)
        audio_clip.close()
        os.remove(downloaded_file)

    #Override Function
    def add_metadata(self) -> None:
        self.__ensure_youtube_loaded()

        print("Adding Metada...")

        if not self.metadata.is_downloaded or self.metadata.metadata_updated:
            print("Audio is not downloaded or already updated")
            return

        json_data = None

        for attempt in range(10):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.get(self.url, headers=headers)
            if response.status_code != 200:
                print("❌ Erreur lors de la récupération de la page.")
                continue

            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, "html.parser")

            # Chercher le script contenant "horizontalCardListRenderer"
            script_tags = soup.find_all("script")
            for script in script_tags:
                if script.string and "horizontalCardListRenderer" in script.string and "videoAttributeViewModel" in script.string:
                    json_data = extract_json_object(script.string, "horizontalCardListRenderer")
                    if json_data:
                        break

            if not json_data:
                break
            data = json.loads(json_data)
            cards = data.get("horizontalCardListRenderer", {}).get("cards", [])
            if cards:
                break

            print("⚠️ No JSON found, retrying...")

        if not json_data:
            self.register_metadata("", "", "", self.yt.thumbnail_url)
            return

        try:
            data = json.loads(json_data)
            cards = data.get("horizontalCardListRenderer", {}).get("cards", [])
            if not cards:
                raise KeyError("cards")

            music_data = cards[0].get("videoAttributeViewModel", {})
            title = music_data.get("title", "")
            artist = music_data.get("subtitle", "")
            album = music_data.get("secondarySubtitle", {}).get("content", "")
            image_sources = music_data.get("image", {}).get("sources", [])
            image_url = image_sources[0].get("url", "") if image_sources else self.yt.thumbnail_url

            print(f"**Titre**   : {title}")
            print(f"**Artiste** : {artist}")
            print(f"**Album**   : {album}")
            print(f"**Image**   : {image_url}")

            self.register_metadata(title, artist, album, image_url)
            print(f"[{self.metadata.video_title}] Metadata updated? {self.metadata.metadata_updated}")

        except (KeyError, json.JSONDecodeError) as e:
            print(f"⚠️ Erreur lors de l'extraction des métadonnées pour {self.url}: {e}")
            self.register_metadata("", "", "", self.yt.thumbnail_url)

    def __extract_title(self, file_mode: bool = False):
        self.__ensure_youtube_loaded()

        raw_title = self.yt.title

        if file_mode:
            # Supprime les caractères interdits dans les noms de fichiers
            cleaned_title = raw_title.translate(str.maketrans('', '', '|:"/\\?*<>')).strip()
        else:
            cleaned_title = raw_title.strip()

        if not cleaned_title:
            return f"track_{self.yt.video_id}"

        return cleaned_title