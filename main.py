from audio_downloader import *
from youtube_playlist_manager import *
from concurrent.futures import ThreadPoolExecutor
import threading

playlist_url = 'https://www.youtube.com/playlist?list=PLsOoDQgfBdd3rEtl2weVQ6XnQN421ODzq'
path_to_save_audio = "D:/OneDrive/Mix/NewYear"

playlist_url_test = 'https://youtube.com/playlist?list=PLsOoDQgfBdd0J6-f5xyvZ9yBy4PdLRaJR&si=LI4twcFn2i_wpHlu'
path_to_save_audio_test = "D:\\OneDrive\\Epsi\\dev_perso\\YouSync\\MyPlaylistTest"

def main():
    video_urls = get_all_video_links_from_playlist(playlist_url_test)
    videos_downloaded = []

    def download_video(url, path_to_save_audio_test):
        if download_audio_from_youtube(url, path_to_save_audio_test):
            return url
        return None

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(download_video, url, path_to_save_audio_test) for url in video_urls]
        for future in futures:
            result = future.result()
            if result:
                videos_downloaded.append(result)

    for url in videos_downloaded:
        add_metadata_to_mp3(url, path_to_save_audio_test)

if __name__ == "__main__": main()