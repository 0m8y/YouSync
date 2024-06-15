from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from core.interface.IAudioManager import IAudioManager

from selenium import webdriver
from pytube import YouTube
import eyed3

from moviepy.editor import *
import json
from core.metadata_finder import *
from core.utils import *

class YoutubeAudioManager(IAudioManager):

    def __init__(self, url, path_to_save_audio, data_filepath, lock):
        self.yt = YouTube(url)
        super().__init__(url, path_to_save_audio, data_filepath, self.yt.video_id, find_title_yt(self.yt), lock)

#----------------------------------Download Process-------------------------------------#

    def __get_selenium_driver(self):
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
    def download_audio(self):
        audio_stream = self.yt.streams.filter(only_audio=True).first()
        downloaded_file = audio_stream.download()
        
        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(self.path_to_save_audio_with_title)
        audio_clip.close()
        os.remove(downloaded_file)

    #Override Function
    def add_metadata(self):
        if self.is_downloaded is False or self.metadata_updated is True:
            print("Audio is not downloaded")
            return

        selenium_driver = self.__get_selenium_driver()

        title = find_title(selenium_driver)
        artist = find_artist(selenium_driver)
        album = find_album(selenium_driver)
        image_url = find_image(selenium_driver)
        selenium_driver.quit()

        self.register_metadata(self.video_title, title, artist, album, image_url)
