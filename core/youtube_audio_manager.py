from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from pytube import YouTube
import eyed3.id3
import requests
import eyed3

from moviepy.editor import *
import json
from core.metadata_finder import *
from core.utils import *

class YoutubeAudioManager:

    def __init__(self, url, path_to_save_audio, data_filepath, lock):
        self.lock = lock
        self.url = url
        self.path_to_save_audio = path_to_save_audio
        self.yt = YouTube(self.url)
        self.video_title = find_title_yt(self.yt)
        self.path_to_save_audio_with_title = f"{self.path_to_save_audio}\\{self.video_title}.mp3"
        self.data_filepath = data_filepath

        self.is_downloaded = False
        self.metadata_updated = False
        self.video_title = None
        self.title = None
        self.artist = None
        self.album = None
        self.image_url = None
        data = self.load_data()
        if not any(item['url'] == self.url for item in data):
            data.append(self.to_dict())
            self.save_data_to_file(data)
        else:
            for item in data:
                if item['url'] == self.url:
                    self.__from_dict(item)
                    print(self.url + " is already loaded !")

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
                success = True  # Si le clic réussit, sortir de la boucle
            except StaleElementReferenceException:
                attempts += 1  # Augmenter le nombre de tentatives si l'élément est devenu obsolète
            except TimeoutException:
                print("Le bouton 'Afficher plus' n'est pas trouvé après l'attente.")
                break  # Sortir de la boucle si le bouton n'est pas trouvé

        if not success:
            print("Impossible de cliquer sur le bouton 'Afficher plus' après plusieurs tentatives.")

        return driver
    
    def download(self):
        if self.is_downloaded:
            if not self.metadata_updated:
                self.add_metadata()
                return
            return

        print("downloading " + self.url + "...")
        self.__download_audio(self.yt, self.path_to_save_audio_with_title)

        print(self.url + " is downloaded!")
        self.is_downloaded = True
        self.__update_is_downloaded()
        self.add_metadata()
    
    def __download_audio(self, yt, path_to_save_audio_with_title):
        audio_stream = yt.streams.filter(only_audio=True).first()
        downloaded_file = audio_stream.download()
        
        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(path_to_save_audio_with_title)
        audio_clip.close()
        os.remove(downloaded_file)

    def add_metadata(self):
        if self.is_downloaded is False or self.metadata_updated is True:
            print("Audio is not downloaded")
            return

        selenium_driver = self.__get_selenium_driver()

        self.video_title = find_title_url(self.url)
        self.title_driver = find_title(selenium_driver)
        self.artist = find_artist(selenium_driver)
        self.album = find_album(selenium_driver)
        self.image_url = find_image(selenium_driver)
        selenium_driver.quit()

        audiofile = eyed3.load(self.path_to_save_audio_with_title)
        if (audiofile.tag == None):
            audiofile.initTag()

        audiofile.tag.title = self.title
        audiofile.tag.album = self.album
        audiofile.tag.artist = self.artist
        if self.image_url:
            response = requests.get(self.image_url)
            if response.status_code == 200:
                audiofile.tag.images.set(3, response.content, 'image/jpeg')
            else:
                self.image_url = None
        audiofile.tag.save(version=eyed3.id3.ID3_V2_3)
        print("Metadata is added in " + self.url)
        self.metadata_updated = True
        self.__update_data()

#-------------------------------------Load & Save--------------------------------------#
    
    def load_data(self):
        try:
            with open(self.data_filepath, 'r') as file:
                data = json.load(file)
            # Assurez-vous de retourner la liste des audios
            return data.get("audios", [])
        except FileNotFoundError:
            return []
        
    def save_data_to_file(self, audios_data):
        with self.lock:
            try:
                with open(self.data_filepath, 'r') as file:
                    data = json.load(file)
            except FileNotFoundError:
                data = {}  # Créez une nouvelle structure si le fichier n'existe pas

            # Mettez à jour le champ "audios" avec les données fournies
            data["audios"] = audios_data

            with open(self.data_filepath, 'w') as file:
                json.dump(data, file, indent=4)

#-----------------------------------------DICT------------------------------------------#
    
    def __from_dict(self, data):
        self.path_to_save_audio_with_title = data["path_to_save_audio_with_title"]
        self.is_downloaded = data["is_downloaded"]
        self.metadata_updated = data["metadata_updated"]
        self.video_title = data["video_title"]
        self.title = data["title"]
        self.artist = data["artist"]
        self.album = data["album"]
        self.image_url = data["image_url"]

    def to_dict(self):
        return {
            "url": self.url,
            "path_to_save_audio_with_title": self.path_to_save_audio_with_title,
            "is_downloaded": self.is_downloaded,
            "metadata_updated": self.metadata_updated,
            "video_title": self.video_title,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "image_url": self.image_url
        }
    
#----------------------------------------UPDATE-----------------------------------------#
    
    def __update_data(self):
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['is_downloaded'] = self.is_downloaded
                item['metadata_updated'] = self.metadata_updated
                item['video_title'] = self.video_title
                item['title'] = self.title
                item['artist'] = self.artist
                item['album'] = self.album
                item['image_url'] = self.image_url
                break 
        self.save_data_to_file(data)
    
    def __update_is_downloaded(self):
        data = self.load_data()
        updated = False
        for item in data:
            if item['url'] == self.url and not item['is_downloaded']:
                item['is_downloaded'] = self.is_downloaded
                updated = True
                break
        if updated:
            self.save_data_to_file(data)

    def __update_metadata_updated(self):
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['metadata_updated'] = self.metadata_updated

    def __update_video_title(self):
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['video_title'] = self.video_title

    def __update_title(self):
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['title'] = self.title
    
    def __update_artist(self):
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['artist'] = self.artist

    def __update_album(self):
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['album'] = self.album

    def __update_image_url(self):
        data = self.load_data()
        for item in data:
            if item['url'] == self.url:
                item['image_url'] = self.image_url

    def __delete_audio_file(self):
        if os.path.exists(self.path_to_save_audio_with_title):
            os.remove(self.path_to_save_audio_with_title)
            print(f"Fichier audio supprimé : {self.path_to_save_audio_with_title}")

    def __delete_audio_info(self):
        audios_data = self.load_data()
        audios_data = [audio for audio in audios_data if audio['url'] != self.url]
        self.save_data_to_file(audios_data)
        print("Informations audio supprimées du fichier JSON.")

    def delete(self):
        try:
            self.__delete_audio_file()
            self.__delete_audio_info()
        except Exception as e:
            print(f"Erreur lors de la suppression de l'audio : {e}")


#----------------------------------------GETTER----------------------------------------#

    def get_url(self):
        return self.url
