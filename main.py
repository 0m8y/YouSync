from core.youtube_playlist_manager import *

playlist_url = 'https://www.youtube.com/playlist?list=PLsOoDQgfBdd3rEtl2weVQ6XnQN421ODzq'
path_to_save_audio = "D:\\OneDrive\\Mix\\All"

playlist_url_test = 'https://www.youtube.com/playlist?list=PLsOoDQgfBdd0wOkApkqy5VutMnoK2RKeK'
path_to_save_audio_test = "D:\\OneDrive\\Epsi\\dev_perso\\YouSync\\MyPlaylistTest"

def main():
   playlist_manager = YoutubePlaylistManager(playlist_url_test, path_to_save_audio_test)

   playlist_manager.download()

if __name__ == "__main__": main()
