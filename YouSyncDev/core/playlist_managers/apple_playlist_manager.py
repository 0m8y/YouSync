from selenium.webdriver.support import expected_conditions as EC
from core.playlist_managers.IPlaylistManager import IPlaylistManager
from selenium.webdriver.support.ui import WebDriverWait
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.common.by import By
from core.audio_managers.apple_audio_manager import AppleAudioManager
from core.utils import *
import logging, requests

class ApplePlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url, path_to_save_audio):
        self.html_page = requests.get(playlist_url).text
        self.soup = BeautifulSoup(self.html_page, 'html.parser')
        logging.debug("Initializing ApplePlaylistManager")  
        super().__init__(playlist_url, path_to_save_audio, get_spotify_playlist_id(playlist_url))
    
#----------------------------------------GETTER----------------------------------------#

    #Override Method
    def new_audio_manager(self, url):
        try:
            logging.debug("Creating ApplePlaylistManager")
            audio_manager = AppleAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            return audio_manager
        except Exception as e:
            logging.error(f"Error initializing AppleAudioManager: {e}")
            print(f"Error initializing AppleAudioManager: {e}")

    #Override Method
    def get_playlist_title(self):
        return self.soup.find('meta', attrs={'name':'apple:title'})['content']
    
    def extract_image(self):
        return self.soup.find('meta', property='og:image')['content']

    #Override Method
    def get_video_urls(self):
        driver = get_selenium_driver_for_spotify(self.playlist_url)

        driver.execute_script("document.body.style.zoom = '0.001'")

        total_songs = get_soundcloud_total_songs(driver)

        urls = get_soundcloud_url_list(driver, total_songs)

        print(f"{urls} songs founded.")

        driver.quit()
        return urls

#----------------------------------Download Process-------------------------------------#

    #Override Method
    def download(self):
        def download_audio(audio_manager):
            audio_manager.download()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(download_audio, audio_manager) for audio_manager in self.audio_managers]
            for future in futures:
                future.result()
        logging.debug("downloading videos ...")

    #Override Function
    def extract_video_id(self, url):
        pattern = r"track/([a-zA-Z0-9]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None