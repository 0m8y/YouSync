import time
import threading
from selenium import webdriver
from youtube_audio_manager import *
from selenium.webdriver.common.by import By
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import *

class YoutubePlaylistManager:

    def __init__(self, playlist_url, path_to_save_audio):
        self.playlist_url = playlist_url
        self.path_to_save_audio = path_to_save_audio
        self.video_urls = []
        self.audios_manager = []
        self.name = None
        self.playlist_data_filepath = None
        self.name = get_playlist_id(playlist_url)
        self.__init()

        # def download_video(url, path_to_save_audio):
        #     if self.download_audio_from_youtube(url, path_to_save_audio):
        #         return url
        #     return None

        # with ThreadPoolExecutor(max_workers=4) as executor:
        #     futures = [executor.submit(download_video, url, path_to_save_audio) for url in self.video_urls]
        #     for future in futures:
        #         result = future.result()
        #         if result:
        #             videos_downloaded.append(result)

    def download(self):
        print("downloading video...")

    def __init(self):
        driver = self.__get_selenium_driver()
        self.__scroll_down_page(driver)
        self.video_urls = self.__get_video_urls_from_driver(driver)
        driver.quit()        

        check_yousync_folder(os.path.join(self.path_to_save_audio, ".yousync"))

        self.playlist_data_filepath = self.path_to_save_audio + "\\.yousync\\" + self.name + ".json"

        if not os.path.exists(self.playlist_data_filepath):
            with open(self.playlist_data_filepath, 'w') as fichier:
                fichier.write("[]")

        for video_url in self.video_urls:
            youtube_audio = YoutubeAudioManager(video_url, self.path_to_save_audio, self.playlist_data_filepath)
            self.audios_manager.append(youtube_audio)

        #TODO: check if data have deleted video from playlist

    def update(self):
        driver = self.__get_selenium_driver()
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

    def __get_selenium_driver(self):
        chrome_options = Options()
        # chrome_options.add_argument("--headless")

        driver = webdriver.Chrome(options=chrome_options)

        driver.get(self.playlist_url)
        accept_cookies(driver)
        WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
            )
        return driver