from core.audio_managers.IAudioManager import IAudioManager
from core.metadata_finder import find_title_yt
from core.utils import extract_json_object

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
        self.yt = YouTube(url)
        super().__init__(url, path_to_save_audio, data_filepath, self.yt.video_id, find_title_yt(self.yt), lock)

#----------------------------------Download Process-------------------------------------#

    #Override Function
    def download_audio(self) -> None:
        audio_stream = self.yt.streams.filter(only_audio=True).first()

        temp_dir = tempfile.gettempdir()
        downloaded_file = audio_stream.download(output_path=temp_dir)

        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(self.path_to_save_audio_with_title)
        audio_clip.close()
        os.remove(downloaded_file)

    #Override Function
    def add_metadata(self) -> None:
        print("Adding Metada...")
        if not self.is_downloaded or self.metadata_updated:
            print("Audio is not downloaded")
            return

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(self.url, headers=headers)
        if response.status_code != 200:
            print("❌ Erreur lors de la récupération de la page.")
            return

        soup = BeautifulSoup(response.text, "html.parser")

        # Chercher le script contenant "horizontalCardListRenderer"
        script_tags = soup.find_all("script")
        for script in script_tags:
            if script.string and "horizontalCardListRenderer" in script.string and "videoAttributeViewModel" in script.string:
                json_data = extract_json_object(script.string, "horizontalCardListRenderer")
                if json_data:
                    break
        else:
            self.register_metadata(self.video_title, "", "", "", self.yt.thumbnail_url)
            return

        # Essayer de parser le JSON extrait
        try:
            data = json.loads(json_data)
            music_data = data["horizontalCardListRenderer"]["cards"][0]["videoAttributeViewModel"]

            title = music_data["title"]
            artist = music_data["subtitle"]
            album = music_data["secondarySubtitle"]["content"]
            image_url = music_data["image"]["sources"][0]["url"]

            print(f"**Titre**   : {title}")
            print(f"**Artiste** : {artist}")
            print(f"**Album**   : {album}")
            print(f"**Image**   : {image_url}")

            self.register_metadata(self.video_title, title, artist, album, image_url)

        except (KeyError, json.JSONDecodeError) as e:
            print(f"⚠️ Erreur lors de l'extraction des métadonnées : {e}")
            return None
