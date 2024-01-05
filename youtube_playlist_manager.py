import time
import threading
from selenium import webdriver
from youtube_audio_manager import *
from selenium.webdriver.common.by import By
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class YoutubePlaylistManager:

    def __init__(self, playlist_url, path_to_save_audio):
        self.playlist_url = playlist_url
        self.path_to_save_audio = path_to_save_audio
        self.video_urls = []
        self.youtube_audios = []
        self.name = None
        self.data_filepath = None
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

        # for url in videos_downloaded:
        #     youtube_audio = YoutubeAudioManager(url, self.path_to_save_audio)
        #     youtube_audio.add_metadata()
        #     self.youtube_audios.append(youtube_audio)
    def download(self):
        if not self.youtube_audios:
            for video_url in self.video_urls:
                youtube_audio = YoutubeAudioManager(video_url, self.path_to_save_audio, self.data_filepath)
                self.youtube_audios.append(youtube_audio)

    def __init(self):
        chrome_profile_path = r'C:\Users\msoub\AppData\Local\Google\Chrome\User Data'
        chrome_options = Options()
        chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
        chrome_options.add_argument("--profile-directory=Default")
        chrome_options.add_argument("--headless")

        driver = webdriver.Chrome(options=chrome_options)

        driver.get(self.playlist_url)

        WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//*[@id=\"page-manager\"]/ytd-browse/ytd-playlist-header-renderer/div/div[2]/div[1]/div"))
            )
        self.__get_playlist_name(driver)
        self.__scroll_down_page(driver)

        self.video_urls = self.__get_video_urls_from_driver(driver)
        driver.quit()
        self.data_filepath = "data\\" + self.name + ".json"
        if os.path.exists(self.data_filepath):
            print("exist !")
        else:
            with open(self.data_filepath, 'w') as fichier:
                fichier.write("[]")

    def update(self):
        chrome_profile_path = r'C:\Users\msoub\AppData\Local\Google\Chrome\User Data'
        chrome_options = Options()
        chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
        chrome_options.add_argument("--profile-directory=Default")
        chrome_options.add_argument("--headless")

        driver = webdriver.Chrome(options=chrome_options)

        driver.get(self.playlist_url)

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

    def __get_playlist_name(self, driver):
        try:
            playlist_name_selector = 'body > ytd-app:nth-child(4) > div:nth-child(7) > ytd-page-manager:nth-child(4) > ytd-browse:nth-child(1) > ytd-playlist-header-renderer:nth-child(7) > div:nth-child(2) > div:nth-child(2) > div:nth-child(1) > div:nth-child(2) > ytd-inline-form-renderer:nth-child(2) > div:nth-child(1) > yt-dynamic-sizing-formatted-string:nth-child(1) > div:nth-child(1) > yt-formatted-string:nth-child(1)'
            playlist_name = WebDriverWait(driver, 1).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, playlist_name_selector))
            )
            autor_name_selector = "yt-formatted-string[id='owner-text'] a[class='yt-simple-endpoint style-scope yt-formatted-string']"
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