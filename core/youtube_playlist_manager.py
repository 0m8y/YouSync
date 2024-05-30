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
            print("FROM DICT")
            self.__from_dict(self.load_playlist_data())

        for video_url in self.video_urls:
            youtube_audio = YoutubeAudioManager(video_url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            self.audios_manager.append(youtube_audio)

        #TODO: check if data have deleted video from playlist
    
    def __add_audio(self, url):
            print("Adding audio: " + url)
            youtube_audio = YoutubeAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock)
            self.audios_manager.append(youtube_audio)
            self.video_urls.append(url)

    def __remove_audio(self, url):
        audio_manager_index = next((i for i, am in enumerate(self.audios_manager) if am.get_url() == url), None)

        if audio_manager_index is not None:
            self.audios_manager[audio_manager_index].delete()

            del self.audios_manager[audio_manager_index]

            self.video_urls = [video_url for video_url in self.video_urls if video_url != url]

            print(f"Audio supprimé : {url}")
        else:
            print(f"Audio non trouvé : {url}")


    def update(self):
        print("Updating playlist " + self.id)
        #TODO: Not working, to update with new logic
        new_video_urls = self.__get_video_urls()
        for video_url in self.video_urls:
            print("video url: " + video_url)
        for new_video_url in new_video_urls:
            print("new video url: " + new_video_url)

        for new_video_url in new_video_urls:
            new_video_id = extract_video_id(new_video_url)
            existing_video_ids = [extract_video_id(video_url) for video_url in self.video_urls]
            if new_video_id not in existing_video_ids:
                self.__add_audio(new_video_url)

        for video_url in list(self.video_urls):
            video_id = extract_video_id(video_url)
            new_video_ids = [extract_video_id(new_video_url) for new_video_url in new_video_urls]
            if video_id not in new_video_ids:
                self.__remove_audio(video_url)


#----------------------------------------GETTER----------------------------------------#

    def get_playlist_name(self, driver):
        try:
            playlist_name_selector = "yt-formatted-string#text"
            playlist_name_element = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, playlist_name_selector))
            )
            playlist_name = playlist_name_element.get_attribute("textContent")
            return playlist_name
        except Exception as e:
            print(f"Une erreur est survenue lors de la récupération du nom de la playlist : {e}")
            return None
        
    def get_playlist_image_url(self, driver):
        try:
            image_selector = "img#img"
            image_element = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, image_selector))
            )
            image_url = image_element.get_attribute("src")
            return image_url
        except Exception as e:
            print(f"Une erreur est survenue lors de la récupération de l'URL de l'image : {e}")
            return None

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

        urls = [video.get_attribute('href') for video in video_links if video.get_attribute('href') and 'watch?v=' in video.get_attribute('href')]

        recommended_videos_present = len(driver.find_elements(By.XPATH, "//div[@id='title' and contains(text(),'Vidéos recommandées')]")) > 0
        if recommended_videos_present:
            urls = urls[:-5]

        return urls

    def __get_video_urls(self):
        driver = get_selenium_driver(self.playlist_url)
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
        )
        scroll_down_page(driver)
        urls = self.__get_video_urls_from_driver(driver)
        driver.quit()
        return urls
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
        self.path_to_save_audio = data["path_to_save_audio"]
        audios = data["audios"]
        for audio in audios:
            self.video_urls.append(audio["url"])

    def __initialize_playlist_data(self):
        data = {
            "playlist_url": self.playlist_url,
            "path_to_save_audio": self.path_to_save_audio,
        }
        with self.lock:
            with open(self.playlist_data_filepath, 'w') as file:
                json.dump(data, file, indent=4)