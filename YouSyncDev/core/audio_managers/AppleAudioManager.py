from core.audio_managers.IAudioManager import IAudioManager

from youtube_search import YoutubeSearch
from pytubefix import YouTube
import tempfile

from moviepy.editor import AudioFileClip
import requests
from bs4 import BeautifulSoup
import re
import os
import time

class AppleAudioManager(IAudioManager):

    def __init__(self, url, path_to_save_audio, data_filepath, lock):
        self.html_page = requests.get(url)
        self.soup = BeautifulSoup(self.html_page.text, 'lxml')
        super().__init__(url, path_to_save_audio, data_filepath, self.__extract_apple_id(url), self.__extract_title(), lock)

#----------------------------------Download Process-------------------------------------#

    def __extract_apple_id(self, apple_url):
        # Définir une expression régulière pour extraire l'ID de la piste
        pattern = r"/song/[^/]+/([0-9]+)"
        match = re.search(pattern, apple_url)
        if match:
            return match.group(1)
        return None

    def __get_youtube_url_from_apple(self):
        title = self.__extract_title()
        artist = self.__extract_artist()
        video_search = str(title + " " + artist).replace(" ", "+")
        result = str(list(YoutubeSearch(str(video_search), max_results=1).to_dict())[-1]['url_suffix'])
        return result

    #Override Function
    def download_audio(self):
        youtube_url = self.__get_youtube_url_from_apple()
        yt = YouTube(youtube_url)
        audio_stream = yt.streams.filter(only_audio=True).first()

        temp_dir = tempfile.gettempdir()
        downloaded_file = audio_stream.download(output_path=temp_dir)

        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(self.path_to_save_audio_with_title)
        audio_clip.close()

        # Attempt to remove the file with a retry mechanism
        max_retries = 5
        for attempt in range(max_retries):
            try:
                os.remove(downloaded_file)
                print(f"File {downloaded_file} removed successfully")
                break
            except PermissionError:
                print(f"PermissionError: retrying to remove the file {downloaded_file} (attempt {attempt + 1}/{max_retries})")
                time.sleep(1)  # Wait a bit before retrying
        else:
            print(f"Failed to remove the file {downloaded_file} after {max_retries} attempts")

    #Override Function
    def add_metadata(self):
        if self.is_downloaded is False or self.metadata_updated is True:
            print("Audio is not downloaded")
            return

        video_title = self.__extract_title()
        artist = self.__extract_artist()
        album = self.__extract_album()
        image_url = self.extract_image()
        print("Image URL: " + image_url)
        self.register_metadata(video_title, video_title, artist, album, image_url)

    def __extract_title(self):
        return self.soup.find('meta', attrs={'name': 'apple:title'})['content'].replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")

    def __extract_artist(self):
        artist_elements = self.soup.select('span.song-subtitles-item span a[data-testid="click-action"]')
        return ", ".join([artist.get_text(strip=True) for artist in artist_elements])

    def __extract_album(self):
        album_element = self.soup.select_one('span[data-testid="song-subtitle-album"] span[data-testid="song-subtitle-album-link"] a[data-testid="click-action"]')
        if album_element:
            return album_element.get_text(strip=True)
        else:
            return None

    def extract_image(self):
        return self.soup.find('meta', attrs={'name': 'twitter:image'})['content']
