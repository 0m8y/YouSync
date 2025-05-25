import os
from core.utils import get_cached_playlist_id, get_selenium_driver_for_apple, scroll_down_apple_page, is_valid_apple_music_url
from core.playlist_managers.IPlaylistManager import IPlaylistManager
from core.audio_managers.AppleAudioManager import AppleAudioManager

from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
import requests
import logging
import re


class ApplePlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url: str, path_to_save_audio: str) -> None:
        self.playlist_url = playlist_url
        self.soup = None
        if not is_valid_apple_music_url(playlist_url):
            raise ValueError("Lien Apple Music invalide ou non partageable.")

        logging.debug("Initializing ApplePlaylistManager")
        super().__init__(playlist_url, path_to_save_audio, self.get_apple_playlist_id())

#----------------------------------------GETTER----------------------------------------#
    def __ensure_soup_loaded(self):
        if self.soup is not None:
            return
        response = requests.get(self.playlist_url)
        response.encoding = 'utf-8'
        self.soup = BeautifulSoup(response.text, 'lxml')

    def get_apple_playlist_id(self):
        self.__ensure_soup_loaded()
        return self.soup.find('meta', attrs={'name': 'apple:content_id'})['content'].replace('-', '').replace('.', '')

    # Override Method
    def new_audio_manager(self, url: str) -> Optional[AppleAudioManager]:
        try:
            logging.debug("Creating AppleAudioManager")
            if url is None:
                return None
            audio_manager = AppleAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            return audio_manager
        except Exception as e:
            logging.error(f"Error initializing AppleAudioManager: {e}")
            print(f"Error initializing AppleAudioManager: {e}")
            return None

    # Override Method
    def get_playlist_title(self) -> str:
        self.__ensure_soup_loaded()
        return self.soup.find('meta', attrs={'name': 'apple:title'})['content']

    # Override Function
    def extract_image(self) -> str:
        self.__ensure_soup_loaded()
        image_url = self.soup.find('meta', property='og:image')['content']

        # Vérifie si l'image est valide
        try:
            response = requests.get(image_url, stream=True, timeout=5)
            if response.status_code != 200 or 'apple-music-60.png' in image_url:
                raise ValueError("Image invalide détectée")
        except Exception as e:
            print(f"⚠️ Image invalide détectée, tentative de fallback : {e}")
            return self.generate_collage_from_first_songs()

        return image_url

    def generate_collage_from_first_songs(self) -> str:
        urls = self.get_video_urls()[:4]
        images = []

        for url in urls:
            try:
                audio_manager = AppleAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
                audio_manager.download()
                response = requests.get(audio_manager.extract_image(), timeout=5)
                img = Image.open(BytesIO(response.content)).resize((180, 180))
                images.append(img)
            except Exception as e:
                print(f"Erreur de téléchargement d'image : {e}")

        if len(images) == 0:
            return os.path.join(self.path_to_save_audio, "default_preview.png")

        collage = Image.new('RGB', (360, 360))
        positions = [(0,0), (180,0), (0,180), (180,180)]
        for i, img in enumerate(images):
            collage.paste(img, positions[i])

        collage_path = os.path.join(self.path_to_save_audio, ".yousync", f"{self.id}_collage.jpg")
        collage.save(collage_path)
        return collage_path


    # Override Method
    def get_video_urls(self) -> List[str]:
        driver = get_selenium_driver_for_apple(self.playlist_url)

        scroll_down_apple_page(driver)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        song_links = [link['href'] for link in soup.select('a[data-testid="click-action"]')
                    if link.has_attr('href') and "/song/" in link['href']]


        driver.quit()
        return song_links

#----------------------------------Download Process-------------------------------------#

    # Override Method
    def download(self) -> None:
        def download_audio(audio_manager: AppleAudioManager) -> None:
            audio_manager.download()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(download_audio, audio_manager) for audio_manager in self.audio_managers]
            for future in futures:
                future.result()
        logging.debug("Downloading videos ...")

    # Override Function
    def extract_video_id(self, url: str) -> Optional[str]:
        pattern = r"/song/[^/]+/([0-9]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
