from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.common.by import By
from core.youtube_audio_manager import *
from threading import Lock
from core.utils import *
import threading
import time

class YoutubePlaylistManager:

    def __init__(self, playlist_url, path_to_save_audio):
        self.lock = Lock()
        self.playlist_url = playlist_url
        self.path_to_save_audio = path_to_save_audio
        self.video_urls = []
        self.audios_manager = []
        self.name = None
        self.playlist_data_filepath = None
        self.name = get_playlist_id(playlist_url)
        self.__init()

    def download_audio(self, audio_manager):
        audio_manager.download_mp3()

    def download(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.download_audio, audio_manager) for audio_manager in self.audios_manager]
            for future in futures:
                future.result()
        print("downloading video...")

    def __init(self):
        driver = get_selenium_driver(self.playlist_url)
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
        )
        self.__scroll_down_page(driver)
        self.video_urls = self.__get_video_urls_from_driver(driver)
        driver.quit()        

        check_yousync_folder(os.path.join(self.path_to_save_audio, ".yousync"))

        self.playlist_data_filepath = self.path_to_save_audio + "\\.yousync\\" + self.name + ".json"

        if not os.path.exists(self.playlist_data_filepath):
            with open(self.playlist_data_filepath, 'w') as fichier:
                fichier.write("[]")

        for video_url in self.video_urls:
            youtube_audio = YoutubeAudioManager(video_url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            self.audios_manager.append(youtube_audio)

        #TODO: check if data have deleted video from playlist

    def update(self):
        driver = get_selenium_driver(self.playlist_url)
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
        )
        self.__get_playlist_name(driver)
        self.__scroll_down_page(driver)
        video_urls_updated = self.__get_video_urls_from_driver(driver)
        driver.quit()

        for video_url_updated in video_urls_updated:
            if video_url_updated not in self.video_urls:
                self.video_urls.append(video_url_updated)

        print(str(len(self.video_urls_updated)) + " new videos finded !")

    def load_data(self):
        try:
            with open(self.playlist_data_filepath, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return []

    def __get_playlist_name(self, driver):
        try:
            playlist_name_selector = "yt-formatted-string#text"
            playlist_name = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, playlist_name_selector))
            )
            autor_name_selector = "yt-formatted-string#owner-text > a"
            autor_name = WebDriverWait(driver, 1).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, autor_name_selector))
            )
            self.name = playlist_name.text + "-" + autor_name.text
            self.name = self.name.replace(' ', '-').replace("|", "").replace(":", "").replace("\"", "").replace("/", "").replace("\\", "").replace("?", "").replace("*", "").replace("<", "").replace(">", "")
        except Exception as e:
            print(f"Une erreur est survenue lors de la récupération du nom de la playlist : {e}")

    def __get_video_urls_from_driver(self, driver):
        video_links = driver.find_elements(By.CSS_SELECTOR, 'a.yt-simple-endpoint.style-scope.ytd-playlist-video-renderer')

        video_urls = [video.get_attribute('href') for video in video_links if video.get_attribute('href') and 'watch?v=' in video.get_attribute('href')]

        recommended_videos_present = len(driver.find_elements(By.XPATH, "//div[@id='title' and contains(text(),'Vidéos recommandées')]")) > 0
        if recommended_videos_present:
            video_urls = video_urls[:-5]

        return video_urls

    def __scroll_down_page(self, driver):
        last_height = driver.execute_script("return document.documentElement.scrollHeight")

        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")

            time.sleep(1)

            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

