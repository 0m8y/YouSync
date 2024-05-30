import os
import json
from core.youtube_playlist_manager import YoutubePlaylistManager
from core.utils import get_selenium_driver

import os

class PlaylistData:
    def __init__(self, id, url, path, title):
        self.id = id
        self.url = url
        self.path = path
        self.title = title

    def to_dict(self):
        return {
            "id": self.id,
            "url": self.url,
            "path": self.path,
            "title": self.title
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            url=data["url"],
            path=data["path"],
            title=data["title"]
        )

class CentralManager:
    def __init__(self, json_filename):
        self.project_path = self.get_project_path()
        self.json_filepath = os.path.join(self.project_path, json_filename)
        self.data = self.load_data()

    def get_project_path(self):
        return os.path.dirname(os.path.abspath(__file__))

    def load_data(self):
        if not os.path.exists(self.json_filepath):
            with open(self.json_filepath, 'w') as file:
                json.dump({"playlists": []}, file)
            return {"playlists": []}
        else:
            with open(self.json_filepath, 'r') as file:
                data = json.load(file)
                return {
                    "playlists": [PlaylistData.from_dict(pl) for pl in data["playlists"]]
                }

    def save_data(self):
        with open(self.json_filepath, 'w') as file:
            json.dump({
                "playlists": [pl.to_dict() for pl in self.data["playlists"]]
            }, file, indent=4)

    def add_playlist(self, playlist_url, path_to_save_audio):
        playlist_manager = YoutubePlaylistManager(playlist_url, path_to_save_audio)
        playlist_name = playlist_manager.get_playlist_name(get_selenium_driver(playlist_url))
        playlist_info = PlaylistData(
            id=playlist_manager.id,
            url=playlist_url,
            path= playlist_manager.playlist_data_filepath,
            title=playlist_name
        )
        self.data["playlists"].append(playlist_info.to_dict())
        self.save_data()

    def add_existing_playlists(self, folder_path):
        playlist_count = 0
        if not os.path.exists(folder_path):
            return f"{folder_path} folder does not exist"
        
        yousync_folder_name = ".yousync"
        
        if os.path.basename(folder_path) == yousync_folder_name:
            print(f"Vous êtes déjà dans le dossier {yousync_folder_name}.")
        else:
            yousync_folder_path = os.path.join(folder_path, yousync_folder_name)
            if os.path.exists(yousync_folder_path) and os.path.isdir(yousync_folder_path):
                os.chdir(yousync_folder_path)
                print(f"Vous avez accédé au dossier {yousync_folder_name}.")
            else:
                return f"Le dossier {yousync_folder_name} n'existe pas dans le répertoire courant."

        for filename in os.listdir(yousync_folder_path):
            if filename.endswith(".json"):
                filepath = os.path.join(yousync_folder_path, filename)
                try:
                    with open(filepath, 'r') as file:
                        playlist_data = json.load(file)
                        playlist_url = playlist_data.get("playlist_url")
                        path_to_save_audio = playlist_data.get("path_to_save_audio")
                        
                        if playlist_url and path_to_save_audio:
                            playlist_manager = YoutubePlaylistManager(playlist_url, path_to_save_audio)
                            playlist_name = playlist_manager.get_playlist_name(get_selenium_driver(playlist_url))

                            if any(pl['id'] == playlist_manager.id for pl in self.data["playlists"]):
                                print(f"La playlist avec l'ID {playlist_manager.id} existe déjà.")
                                continue

                            playlist_info = PlaylistData (
                                id=playlist_manager.id,
                                url=playlist_url,
                                path=filepath,
                                title=playlist_name
                            )
                            self.data["playlists"].append(playlist_info.to_dict())
                            playlist_count += 1
                        else:
                            print(f"Les données dans le fichier {filename} sont incomplètes.")
                except Exception as e:
                    return f"Erreur lors du chargement du fichier {filename}: {e}"

        self.save_data()
        if playlist_count == 0:
            return "No playlists found !"
        elif playlist_count == 1:
            return "1 playlist has been found !"
        else:
            return f"{playlist_count} playlists were found !"

    def remove_playlist(self, playlist_id):
        self.data["playlists"] = [pl for pl in self.data["playlists"] if pl.id != playlist_id]
        self.save_data()

    def list_playlists(self):
        return self.data["playlists"]

    def get_playlist(self, playlist_id):
        for pl in self.data["playlists"]:
            if pl.id == playlist_id:
                return pl
        return None
