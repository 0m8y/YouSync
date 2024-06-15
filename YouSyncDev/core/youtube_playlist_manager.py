from selenium.webdriver.support import expected_conditions as EC
from core.interface.IPlaylistManager import IPlaylistManager
from selenium.webdriver.support.ui import WebDriverWait
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.common.by import By
from core.youtube_audio_manager import *
from core.utils import *
import logging
import requests

class YoutubePlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url, path_to_save_audio):
        print("YoutubePlaylistManager Loaded")  
        self.html_page = requests.get(playlist_url).text
        self.soup = BeautifulSoup(self.html_page, 'html.parser')
        logging.debug("Initializing YoutubePlaylistManager")  
        super().__init__(playlist_url, path_to_save_audio, get_youtube_playlist_id(playlist_url))
    
#----------------------------------------GETTER----------------------------------------#

    #Override Method
    def new_audio_manager(self, url):
        try:
            audio_manager = YoutubeAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
        except Exception as e:
            logging.error(f"Error initializing YoutubeAudioManager: {e}")
            print(f"Error initializing YoutubeAudioManager: {e}")
        return audio_manager

    #Override Method    
    def get_playlist_title(self):
        soup = BeautifulSoup(self.html_page, 'html.parser')
        title = soup.find('meta', property='og:title')['content']
        print(f"title founded: {title}")
        return title

    #Override Method
    def get_video_urls(self):
        driver = get_selenium_driver(self.playlist_url)
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
        )
        scroll_down_page(driver)
        urls = self.__get_video_urls_from_driver(driver)
        driver.quit()
        return urls

    def __get_video_urls_from_driver(self, driver):
        video_links = driver.find_elements(By.CSS_SELECTOR, 'a.yt-simple-endpoint.style-scope.ytd-playlist-video-renderer')

        urls = [video.get_attribute('href') for video in video_links if video.get_attribute('href') and 'watch?v=' in video.get_attribute('href')]

        recommended_videos_present = len(driver.find_elements(By.XPATH, "//div[@id='title' and contains(text(),'Vidéos recommandées')]")) > 0
        if recommended_videos_present:
            urls = urls[:-5]

        return urls
    
    def __get_author_name(self, driver):
        try:
            autor_name_selector = "yt-formatted-string#owner-text > a"
            autor_name = WebDriverWait(driver, 1).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, autor_name_selector))
            )
            return autor_name
        except Exception as e:
            logging.error(f"Une erreur est survenue lors de la récupération du nom de la playlist : {e}")

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
        query = urlparse(url).query
        params = parse_qs(query)
        return params.get('v', [None])[0]
    
    #Override Function
    def extract_image(self):
        title = self.soup.find('meta', property='og:image')['content']
        print(f"title founded: {title}")
        return title