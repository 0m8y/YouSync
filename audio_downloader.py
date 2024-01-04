from pytube import YouTube
from moviepy.editor import *
import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error, TIT2, TPE1, TALB
from youtube_metadata_finder import *
import eyed3
import eyed3.id3
from eyed3.id3.frames import CommentFrame

def add_metadata_to_mp3(url, path_to_save_audio):
    selenium_driver = get_selenium_driver(url)

    title = find_title_url(url)
    title_driver = find_title(selenium_driver)
    artist = find_artist(selenium_driver)
    album = find_album(selenium_driver)
    image_url = find_image(selenium_driver)
    selenium_driver.quit()

    path_to_save_audio_with_title = f"{path_to_save_audio}\\{title}.mp3"
    audiofile = eyed3.load(path_to_save_audio_with_title)
    if (audiofile.tag == None):
        audiofile.initTag()

    audiofile.tag.title = title_driver
    audiofile.tag.album = album
    audiofile.tag.artist = artist
    if image_url:
        response = requests.get(image_url)
        if response.status_code == 200:
            audiofile.tag.images.set(3, response.content, 'image/jpeg')
        else:
            print(f"Échec de la récupération de l'image depuis {image_url}")
    audiofile.tag.save(version=eyed3.id3.ID3_V2_3)
    print("Metadata is added in " + title + "." )

def download_audio(yt, path_to_save_audio_with_title):
    audio_stream = yt.streams.filter(only_audio=True).first()
    downloaded_file = audio_stream.download()
    
    audio_clip = AudioFileClip(downloaded_file)
    audio_clip.write_audiofile(path_to_save_audio_with_title)
    audio_clip.close()
    os.remove(downloaded_file)

def download_audio_from_youtube(url, path_to_save_audio):
    downloaded_links_file = "D:\OneDrive\Epsi\dev_perso\YouSync\data\downloaded_links.txt"
    yt = YouTube(url)
    title = find_title_yt(yt)

    if os.path.exists(downloaded_links_file):
        with open(downloaded_links_file, 'r') as file:
            if url in file.read():
                print(title + " is already downloaded.")
                return False

    print(title + " is finded!")
    path_to_save_audio_with_title = f"{path_to_save_audio}\\{title}.mp3"
    download_audio(yt, path_to_save_audio_with_title)

    with open(downloaded_links_file, 'a') as file:
        file.write(url + '\n')

    print(title + " is downloaded!")

    return True
