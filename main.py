from core.youtube_playlist_manager import YoutubePlaylistManager
from core.central_manager import CentralManager
from gui.app import App
playlist_url = 'https://www.youtube.com/playlist?list=PLsOoDQgfBdd3rEtl2weVQ6XnQN421ODzq'
path_to_save_audio = "D:\\OneDrive\\Mix\\All"

# playlist_url_cremaillere = 'https://youtube.com/playlist?list=PLsOoDQgfBdd3qF2F8JG6PLvLQvqD1bCSp&si=LSB6-WkArQ0XpNYU'
# path_to_save_audio_cremaillere = "D:\\OneDrive\\Mix\\Cremaillere"

playlist_url_cremaillere = 'https://www.youtube.com/playlist?list=PLsOoDQgfBdd3ok3NPsyHXbJQqTy9dyRp4'
path_to_save_audio_cremaillere = "D:\\OneDrive\\Mix\\CremRap"

# playlist_url_cremaillere = 'https://youtube.com/playlist?list=PLVgnYBw1_6zLmjVxSthCY5F-yaLB-DS4b&si=1P4LcuyHW9vh7kLX'
# path_to_save_audio_cremaillere = "D:\\OneDrive\\Mix\\Tom"

# playlist_url_cremaillere = 'https://youtube.com/playlist?list=PLPY6550L-B8v2Tjd7XGQkqk-dssZZRGNn&si=y3Ibez6Oj26upZIG'
# path_to_save_audio_cremaillere = "D:\\OneDrive\\Mix\\Mateo"


# playlist_url_cremaillere = 'https://youtube.com/playlist?list=PL-x9tU9Igq7KVfMTHmFqggAanp6oCSAT7&si=0qcwUShkBUQxJqgh'
# path_to_save_audio_cremaillere = "D:\\OneDrive\\Mix\\Chris"

playlist_url_test = 'https://www.youtube.com/playlist?list=PLsOoDQgfBdd0wOkApkqy5VutMnoK2RKeK'
path_to_save_audio_test = "D:\\OneDrive\\Epsi\\dev_perso\\YouSync\\MyPlaylistTest"

# def main():
#    playlist_manager = YoutubePlaylistManager(playlist_url_cremaillere, path_to_save_audio_cremaillere)


#    playlist_manager.update()
#    playlist_manager.download()


# if __name__ == "__main__": main()

# if __name__ == "__main__":
#     manager = CentralManager("playlists.json")
#     print(manager.add_existing_playlists("D:\\OneDrive\\Mix\\Mateo"))
#     # manager.add_playlist("https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID", "/path/to/save/audio")
#     # print(manager.list_playlists())

if __name__ == "__main__":
    app = App()
    app.mainloop()
