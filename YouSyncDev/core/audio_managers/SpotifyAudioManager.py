from core.utils import get_cached_video_title
from core.audio_managers.IAudioManager import IAudioManager

from youtube_search import YoutubeSearch
from pytubefix import YouTube
import os
import re

from moviepy import AudioFileClip
import requests
from bs4 import BeautifulSoup
from typing import Optional
from threading import Lock
import tempfile
import logging


class SpotifyAudioManager(IAudioManager):

    def __init__(self, url: str, path_to_save_audio: str, data_filepath: str, lock: Lock) -> None:
        self.url = url
        self.soup = None

        cached_title = get_cached_video_title(url, data_filepath) or self.__extract_title(url, True)

        logging.debug(f"New SpotifyAudioManager\nURL: {url}\npath_to_save_audio: {path_to_save_audio}\ndata_filepath: {data_filepath}\n")
        super().__init__(url, path_to_save_audio, data_filepath, self.__extract_spotify_id(url), cached_title, lock)

#----------------------------------Download Process-------------------------------------#

    def __ensure_soup_loaded(self):
        if self.soup is not None:
            return
        headers = {
            "User-Agent": "... (comme avant)"
        }
        response = requests.get(self.url, headers=headers)
        response.encoding = 'utf-8'
        self.soup = BeautifulSoup(response.text, 'lxml')

    def __extract_spotify_id(self, spotify_url: str) -> Optional[str]:
        pattern = r"track/([a-zA-Z0-9]+)"
        match = re.search(pattern, spotify_url)
        if match:
            return match.group(1)
        print(f"Spotify id not found: {spotify_url}")
        return None

    def __get_youtube_url_from_spotify(self) -> str:
        self.__ensure_soup_loaded()

        title = self.soup.find('meta', property='og:title')
        artist = self.soup.find('meta', attrs={'name': 'music:musician_description'})

        if not title or not artist:
            raise ValueError("Impossible d'extraire le titre ou l'artiste depuis Spotify")

        video_search = str(title['content'] + " " + artist['content']).replace(" ", "+")
        results = list(YoutubeSearch(video_search, max_results=1).to_dict())

        if not results:
            raise ValueError(f"Aucun résultat YouTube trouvé pour : {video_search}")

        return "https://www.youtube.com" + results[0]['url_suffix']

    #Override Function
    def download_audio(self) -> None:
        youtube_url = self.__get_youtube_url_from_spotify()
        yt = YouTube(youtube_url)
        audio_stream = yt.streams.filter(only_audio=True).first()

        temp_dir = tempfile.gettempdir()
        downloaded_file = audio_stream.download(output_path=temp_dir)

        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(self.metadata.path_to_save_audio_with_title)
        audio_clip.close()
        os.remove(downloaded_file)

    #Override Function
    def add_metadata(self) -> None:
        if not self.metadata.is_downloaded or self.metadata.metadata_updated:
            print("Audio is not downloaded")
            return

        title = self.__extract_title(self.url)
        artist = self.__extract_artist()
        album = self.__extract_album()
        image_url = self.extract_image()
        print("Image URL: " + image_url)
        self.register_metadata(title, artist, album, image_url)

    def __extract_title(self, url, file_mode: bool = False) -> str:
        self.__ensure_soup_loaded()

        raw_title = self.soup.find('meta', property='og:title')['content'].strip()

        if file_mode:
            cleaned_title = raw_title.translate(str.maketrans('', '', '|:"/\\?*<>')).strip()
        else:
            cleaned_title = raw_title

        return cleaned_title or f"track_{self.__extract_spotify_id(url)}"

    def __extract_artist(self) -> str:
        self.__ensure_soup_loaded()

        return self.soup.find('meta', attrs={'name': 'music:musician_description'})['content'].strip()

    def __extract_album(self) -> str:
        self.__ensure_soup_loaded()

        try:
            info_block = self.soup.find("div", {"data-testid": "entity-bottom-section"})
            spans = [s.text for s in info_block.find_all("span")]
            album = spans[0]

            if not album:
                return ""
            return album
        except Exception as e:
            print(f"An error occurred: {e}")
            return ""

    def extract_image(self) -> str:
        self.__ensure_soup_loaded()

        return self.soup.find('meta', attrs={'name': 'twitter:image'})['content']
