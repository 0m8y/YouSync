from selenium.webdriver.support import expected_conditions as EC
from core.interface.IPlaylistManager import IPlaylistManager
from selenium.webdriver.support.ui import WebDriverWait
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.common.by import By
from core.spotify_audio_manager import SpotifyAudioManager
from core.utils import *
import logging

class SpotifyPlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url, path_to_save_audio):
        logging.debug("Initializing SpotifyPlaylistManager")  
        super().__init__(playlist_url, path_to_save_audio, get_spotify_playlist_id(playlist_url))
    
#----------------------------------------GETTER----------------------------------------#

    #Override Method
    def new_audio_manager(self, url):
        try:
            logging.debug("Creating SpotifyPlaylistManager")
            audio_manager = SpotifyAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            return audio_manager
        except Exception as e:
            logging.error(f"Error initializing SpotifyAudioManager: {e}")
            print(f"Error initializing SpotifyAudioManager: {e}")

    #Override Method
    def get_playlist_name(self, driver):
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        title = soup.find('meta', property='og:title')['content']
        return title
        
    #Override Method
    def get_playlist_image_url(self, driver):
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "img.mMx2LUixlnN_Fu45JpFB")))
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tag = soup.find('img', {'class': 'mMx2LUixlnN_Fu45JpFB'})
        srcset = img_tag.get('srcset')
        srcset_list = srcset.split(', ')
        desired_url = None
        for item in srcset_list:
            url, resolution = item.split(' ')
            if resolution == '640w':
                desired_url = url
                break

            print("Image URL with 640w resolution:", desired_url)
        else:
            raise Exception(f"Desired resolution not found for {driver.current_url}")
        return desired_url

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