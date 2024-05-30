import os
import json
from youtube_playlist_manager import YoutubePlaylistManager

class CentralManager:
    def __init__(self, json_filepath):
        self.json_filepath = json_filepath
        self.data = self.load_data()

    def load_data(self):
        if not os.path.exists(self.json_filepath):
            with open(self.json_filepath, 'w') as file:
                json.dump({"playlists": []}, file)
            return {"playlists": []}
        else:
            with open(self.json_filepath, 'r') as file:
                return json.load(file)

    def save_data(self):
        with open(self.json_filepath, 'w') as file:
            json.dump(self.data, file, indent=4)

    def add_playlist(self, playlist_url, path_to_save_audio):
        playlist_manager = YoutubePlaylistManager(playlist_url, path_to_save_audio)
        playlist_name = playlist_manager.__get_playlist_name(playlist_manager.get_selenium_driver(playlist_url))
        playlist_info = {
            "id": playlist_manager.id,
            "url": playlist_url,
            "path": path_to_save_audio,
            "title": playlist_name
        }
        self.data["playlists"].append(playlist_info)
        self.save_data()

    def remove_playlist(self, playlist_id):
        self.data["playlists"] = [pl for pl in self.data["playlists"] if pl["id"] != playlist_id]
        self.save_data()

    def list_playlists(self):
        return self.data["playlists"]

    def get_playlist(self, playlist_id):
        for pl in self.data["playlists"]:
            if pl["id"] == playlist_id:
                return pl
        return None

# Usage example
if __name__ == "__main__":
    manager = CentralManager("playlists.json")
    manager.add_playlist("https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID", "/path/to/save/audio")
    print(manager.list_playlists())
