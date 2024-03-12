from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.common.by import By
from core.youtube_audio_manager import *
from threading import Lock
from core.utils import *
import time

class YoutubePlaylistManager:

    def __init__(self, playlist_url, path_to_save_audio):
        self.lock = Lock()
        self.playlist_url = playlist_url
        self.path_to_save_audio = path_to_save_audio
        self.id = get_playlist_id(playlist_url)
        
        self.video_urls = []
        self.audios_manager = []
        self.__init()

    def __init(self):
        check_yousync_folder(os.path.join(self.path_to_save_audio, ".yousync"))

        self.playlist_data_filepath = self.path_to_save_audio + "\\.yousync\\" + self.id + ".json"

        if not os.path.exists(self.playlist_data_filepath):
            self.video_urls = self.__get_video_urls()
            with open(self.playlist_data_filepath, 'w') as fichier:
                fichier.write("[]")
            self.__initialize_playlist_data()
        else:
            self.__from_dict(self.load_playlist_data())

        for video_url in self.video_urls:
            youtube_audio = YoutubeAudioManager(video_url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            self.audios_manager.append(youtube_audio)

        #TODO: check if data have deleted video from playlist

    def update(self):
        driver = get_selenium_driver(self.playlist_url)
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
        )
        scroll_down_page(driver)
        video_urls_updated = self.__get_video_urls_from_driver(driver)
        driver.quit()

        for video_url_updated in video_urls_updated:
            if video_url_updated not in self.video_urls:
                self.video_urls.append(video_url_updated)

        print(str(len(self.video_urls_updated)) + " new videos finded !")

#----------------------------------------GETTER----------------------------------------#

    def __get_playlist_name(self, driver):
        try:
            playlist_name_selector = "yt-formatted-string#text"
            playlist_name = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, playlist_name_selector))
            )
            return playlist_name
        except Exception as e:
            print(f"Une erreur est survenue lors de la récupération du nom de la playlist : {e}")

    def __get_author_name(self, driver):
        try:
            autor_name_selector = "yt-formatted-string#owner-text > a"
            autor_name = WebDriverWait(driver, 1).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, autor_name_selector))
            )
            return autor_name
        except Exception as e:
            print(f"Une erreur est survenue lors de la récupération du nom de la playlist : {e}")

    def __get_video_urls_from_driver(self, driver):
        video_links = driver.find_elements(By.CSS_SELECTOR, 'a.yt-simple-endpoint.style-scope.ytd-playlist-video-renderer')

        video_urls = [video.get_attribute('href') for video in video_links if video.get_attribute('href') and 'watch?v=' in video.get_attribute('href')]

        recommended_videos_present = len(driver.find_elements(By.XPATH, "//div[@id='title' and contains(text(),'Vidéos recommandées')]")) > 0
        if recommended_videos_present:
            video_urls = video_urls[:-5]

        return video_urls

    def __get_video_urls(self):
        driver = get_selenium_driver(self.playlist_url)
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
        )
        scroll_down_page(driver)
        video_urls = self.__get_video_urls_from_driver(driver)
        driver.quit()
        return video_urls
#----------------------------------Download Process-------------------------------------#

    def download_audio(self, audio_manager):
        audio_manager.download()

    def download(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.download_audio, audio_manager) for audio_manager in self.audios_manager]
            for future in futures:
                future.result()
        print("downloading video...")

#-------------------------------------Load & Save--------------------------------------#

    def load_playlist_data(self):
        with self.lock:
            try:
                with open(self.playlist_data_filepath, 'r') as file:
                    return json.load(file)
            except FileNotFoundError:
                return {"playlist_url": self.playlist_url, "audios": []}
            
    def save_playlist_data(self, data):
        with self.lock:
            with open(self.playlist_data_filepath, 'w') as file:
                json.dump(data, file, indent=4)

    def __from_dict(self, data):
        self.video_urls = data["video_urls"]
        self.path_to_save_audio = data["path_to_save_audio"]
        audios = data["audios"]
        for audio in audios:
            self.video_urls.append(audio["url"])

    def __initialize_playlist_data(self):
        data = {
            "playlist_url": self.playlist_url,
            "path_to_save_audio": self.path_to_save_audio,
            "video_urls": self.video_urls,
        }
        with self.lock:
            with open(self.playlist_data_filepath, 'w') as file:
                json.dump(data, file, indent=4)