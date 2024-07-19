from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from core.audio_managers.IAudioManager import IAudioManager
from selenium import webdriver

from pytubefix import YouTube

from core.metadata_finder import find_title, find_artist, find_album, find_image, find_title_yt
from moviepy.editor import AudioFileClip
from threading import Lock
from core.utils import get_selenium_driver
import os


class YoutubeAudioManager(IAudioManager):

    def __init__(self, url: str, path_to_save_audio: str, data_filepath: str, lock: Lock) -> None:
        self.yt = YouTube(url)
        super().__init__(url, path_to_save_audio, data_filepath, self.yt.video_id, find_title_yt(self.yt), lock)

#----------------------------------Download Process-------------------------------------#

    def __get_selenium_driver(self) -> webdriver.Chrome:
        driver = get_selenium_driver(self.url)

        success = False
        attempts = 0
        while not success and attempts < 3:
            try:
                show_description = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//tp-yt-paper-button[@id='expand']"))
                )
                show_description.click()
                success = True
            except StaleElementReferenceException:
                attempts += 1
            except TimeoutException:
                print("Le bouton 'Afficher plus' n'est pas trouvé après l'attente.")
                break

        if not success:
            print("Impossible de cliquer sur le bouton 'Afficher plus' après plusieurs tentatives.")

        return driver

    #Override Function
    def download_audio(self) -> None:
        audio_stream = self.yt.streams.filter(only_audio=True).first()
        downloaded_file = audio_stream.download()

        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(self.path_to_save_audio_with_title)
        audio_clip.close()
        os.remove(downloaded_file)

    #Override Function
    def add_metadata(self) -> None:
        if not self.is_downloaded or self.metadata_updated:
            print("Audio is not downloaded")
            return

        selenium_driver = self.__get_selenium_driver()

        title = find_title(selenium_driver)
        artist = find_artist(selenium_driver)
        album = find_album(selenium_driver)
        image_url = find_image(selenium_driver)
        selenium_driver.quit()

        self.register_metadata(self.video_title, title, artist, album, image_url)
