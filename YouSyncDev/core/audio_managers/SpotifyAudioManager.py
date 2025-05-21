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
        self.html_page = requests.get(url)
        self.soup = BeautifulSoup(self.html_page.text, 'lxml')
        logging.debug(f"New SpotifyAudioManager\nURL: {url}\npath_to_save_audio: {path_to_save_audio}\ndata_filepath: {data_filepath}\n")
        super().__init__(url, path_to_save_audio, data_filepath, self.__extract_spotify_id(url), self.__extract_title(), lock)

#----------------------------------Download Process-------------------------------------#

    def __extract_spotify_id(self, spotify_url: str) -> Optional[str]:
        pattern = r"track/([a-zA-Z0-9]+)"
        match = re.search(pattern, spotify_url)
        if match:
            return match.group(1)
        print(f"Spotify id not found: {spotify_url}")
        return None

    def __get_youtube_url_from_spotify(self) -> str:
        title = self.soup.find('meta', property='og:title')['content']
        artist = self.soup.find('meta', attrs={'name': 'music:musician_description'})['content']
        video_search = str(title + " " + artist).replace(" ", "+")
        result = str(list(YoutubeSearch(str(video_search), max_results=1).to_dict())[-1]['url_suffix'])
        return result

    #Override Function
    def download_audio(self) -> None:
        youtube_url = self.__get_youtube_url_from_spotify()
        yt = YouTube(youtube_url)
        audio_stream = yt.streams.filter(only_audio=True).first()

        temp_dir = tempfile.gettempdir()
        downloaded_file = audio_stream.download(output_path=temp_dir)

        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(self.path_to_save_audio_with_title)
        audio_clip.close()
        os.remove(downloaded_file)

    #Override Function
    def add_metadata(self) -> None:
        if not self.is_downloaded or self.metadata_updated:
            print("Audio is not downloaded")
            return

        video_title = self.__extract_title()
        artist = self.__extract_artist()
        album = self.__extract_album()
        image_url = self.extract_image()
        print("Image URL: " + image_url)
        self.register_metadata(video_title, video_title, artist, album, image_url)

    def __extract_title(self) -> str:
        title = self.soup.find('meta', property='og:title')['content'].replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
        return title

    def __extract_artist(self) -> str:
        return self.soup.find('meta', attrs={'name': 'music:musician_description'})['content'].replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")

    def __extract_album(self) -> str:
        try:
            album_link_meta = self.soup.find('meta', attrs={'name': 'music:album'})
            if not album_link_meta:
                return ""

            album_link = album_link_meta['content']
            html_page = requests.get(album_link)
            soup = BeautifulSoup(html_page.text, 'lxml')

            title_meta = soup.find('meta', property='og:title')
            if not title_meta:
                return ""

            return title_meta['content'].replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
        except Exception as e:
            print(f"An error occurred: {e}")
            return ""

    def extract_image(self) -> str:
        return self.soup.find('meta', attrs={'name': 'twitter:image'})['content']
