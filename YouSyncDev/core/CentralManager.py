import os
import re
import sys
import json
import logging
import datetime
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
from typing import List, Callable, Optional, Union, Dict, Any

from core.audio_managers.IAudioManager import IAudioManager
from core.playlist_managers.YoutubePlaylistManager import YoutubePlaylistManager
from core.playlist_managers.SpotifyPlaylistManager import SpotifyPlaylistManager
from core.playlist_managers.ApplePlaylistManager import ApplePlaylistManager

spotify_pattern = re.compile(r'https://open\.spotify\.com/.*')
youtube_pattern = re.compile(r'https://(www\.)?(youtube\.com|youtu\.be)/.*')
apple_pattern = re.compile(r'^https://music\.apple\.com/[a-z]{2}/(album|playlist)/.+')

class Platform(Enum):
    YOUTUBE = 1
    SPOTIFY = 2
    APPLE = 3


class PlaylistData:
    def __init__(self, id: str, url: str, path: str, title: str, last_update: Optional[str] = None):
        self.id = id
        self.url = url
        self.path = path
        self.title = title
        self.last_update = last_update or datetime.datetime.now().strftime("%B %d, %Y - %H:%M")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "path": self.path,
            "title": self.title,
            "last_update": self.last_update
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlaylistData':
        return cls(
            id=data["id"],
            url=data["url"],
            path=data["path"],
            title=data["title"],
            last_update=data.get("last_update")
        )


class CentralManager:
    def __init__(self, json_filename: str, progress_callback: Optional[Callable[[int, int], None]] = None):
        print("CentralManager Open")
        self.project_path = self.get_project_path()
        self.json_filepath = os.path.join(self.project_path, json_filename)
        self.data = self.load_data_from_json()
        self.playlist_managers: List[Union[YoutubePlaylistManager, SpotifyPlaylistManager, ApplePlaylistManager]] = []
        self.progress_callback = progress_callback
        self.playlist_loaded = False

    def get_project_path(self) -> str:
        if getattr(sys, 'frozen', False):
            user_dir = os.path.expanduser("~")
            project_dir = os.path.join(user_dir, '.yousync_project')

            if not os.path.exists(project_dir):
                os.makedirs(project_dir)

            return project_dir
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def load_data_from_json(self) -> Dict[str, Any]:
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

    def save_data_to_json(self) -> None:
        with open(self.json_filepath, 'w') as file:
            json.dump({
                "playlists": [pl.to_dict() if isinstance(pl, PlaylistData) else PlaylistData.from_dict(pl).to_dict() for pl in self.data["playlists"]]
            }, file, indent=4)

    def instantiate_playlist_managers(self) -> None:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures: List[Future] = [executor.submit(self.create_playlist_manager, pl) for pl in self.data["playlists"]]
            total_playlists = len(futures)
            if total_playlists == 0:
                self.playlist_loaded = True
                return
            if self.progress_callback:
                self.progress_callback(0, total_playlists)
            for i, future in enumerate(futures):
                result = future.result()
                if result:
                    self.playlist_managers.append(result)
                if self.progress_callback:
                    self.progress_callback(i + 1, total_playlists)
        self.playlist_loaded = True

    def create_playlist_manager(self, pl: PlaylistData) -> Optional[Union[YoutubePlaylistManager, SpotifyPlaylistManager, ApplePlaylistManager]]:
        path_to_save_audio = os.path.dirname(os.path.dirname(pl.path))
        playlist_manager = next((pm for pm in self.playlist_managers if pm.id == pl.id), None)
        if not playlist_manager:
            try:
                if youtube_pattern.match(pl.url):
                    return YoutubePlaylistManager(pl.url, path_to_save_audio)
                elif spotify_pattern.match(pl.url):
                    return SpotifyPlaylistManager(pl.url, path_to_save_audio)
                elif apple_pattern.match(pl.url):
                    return ApplePlaylistManager(pl.url, path_to_save_audio)
            except Exception as e:
                logging.debug(f"Error when creating playlist manager: {e}")
        return None

    def add_playlist(self, playlist_url: str, path_to_save_audio: str, platform: Platform) -> str:
        match platform:
            case Platform.YOUTUBE:
                print("Adding new youtube playlist...")
                playlist_manager = YoutubePlaylistManager(playlist_url, path_to_save_audio)
            case Platform.SPOTIFY:
                print("Adding new spotify playlist...")
                playlist_manager = SpotifyPlaylistManager(playlist_url, path_to_save_audio)
            case Platform.APPLE:
                print("Adding new apple playlist...")
                playlist_manager = ApplePlaylistManager(playlist_url, path_to_save_audio)
            case _:
                print("Adding new youtube playlist...")
                playlist_manager = YoutubePlaylistManager(playlist_url, path_to_save_audio)

        if any(pl.id == playlist_manager.id for pl in self.data["playlists"]):
            return "The playlist is already registered."

        playlist_manager.download_cover_image()
        playlist_info = PlaylistData(
            id=playlist_manager.id,
            url=playlist_url,
            path=playlist_manager.playlist_data_filepath,
            title=playlist_manager.title,
        )
        self.data["playlists"].append(playlist_info)
        self.playlist_managers.append(playlist_manager)
        self.save_data_to_json()
        print("Playlist added successfully.")
        return "Playlist added successfully."

    def add_existing_playlists(self, folder_path: str) -> str:
        playlist_count = 0
        if not os.path.exists(folder_path):
            return f"{folder_path} folder does not exist"

        yousync_folder_name = ".yousync"

        if os.path.basename(folder_path) == yousync_folder_name:
            print(f"Vous êtes déjà dans le dossier {yousync_folder_name}.")
        else:
            folder_path = os.path.join(folder_path, yousync_folder_name)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                os.chdir(folder_path)
                print(f"Vous avez accédé au dossier {yousync_folder_name}.")
            else:
                return f"Le dossier {yousync_folder_name} n'existe pas dans le répertoire courant."

        for filename in os.listdir(folder_path):
            if filename.endswith(".json"):
                filepath = os.path.join(folder_path, filename)
                try:
                    with open(filepath, 'r') as file:
                        playlist_data = json.load(file)
                        playlist_url = playlist_data.get("playlist_url")
                        path_to_save_audio = playlist_data.get("path_to_save_audio")
                        if playlist_url and path_to_save_audio:
                            try:
                                if youtube_pattern.match(playlist_url):
                                    playlist_manager = YoutubePlaylistManager(playlist_url, path_to_save_audio)
                                elif spotify_pattern.match(playlist_url):
                                    playlist_manager = SpotifyPlaylistManager(playlist_url, path_to_save_audio)
                                elif apple_pattern.match(playlist_url):
                                    playlist_manager = ApplePlaylistManager(playlist_url, path_to_save_audio)
                                else:
                                    raise Exception(f"Unknown playlist url: {playlist_url}")
                            except Exception as e:
                                logging.error(f"Error initializing PlaylistManager: {e}")
                                print(f"Error initializing PlaylistManager: {e}")

                            if any(PlaylistData.from_dict(pl).id == playlist_manager.id if isinstance(pl, dict) else pl.id == playlist_manager.id for pl in self.data["playlists"]):
                                print(f"La playlist avec l'ID {playlist_manager.id} existe déjà.")
                                continue
                            playlist_manager.download_cover_image()
                            playlist_info = PlaylistData(
                                id=playlist_manager.id,
                                url=playlist_url,
                                path=filepath,
                                title=playlist_manager.title,
                            )
                            self.data["playlists"].append(playlist_info)
                            self.playlist_managers.append(playlist_manager)
                            self.save_data_to_json()
                            playlist_count += 1
                        else:
                            print(f"Les données dans le fichier {filename} sont incomplètes.")
                except Exception as e:
                    return f"Erreur lors du chargement du fichier {filename}: {e}"

        self.save_data_to_json()
        if playlist_count == 0:
            return "No playlists found !"
        elif playlist_count == 1:
            return "1 playlist has been found !"
        else:
            return f"{playlist_count} playlists were found !"

    def remove_playlist(self, playlist_id: str) -> None:
        self.data["playlists"] = [pl for pl in self.data["playlists"] if pl.id != playlist_id]
        self.playlist_managers = [pm for pm in self.playlist_managers if pm.id != playlist_id]
        self.save_data_to_json()

    def update_playlist(self, playlist_id: str) -> Union[str, None]:
        try:
            playlist = self.get_playlist(playlist_id)

            if not playlist:
                return f"Playlist with ID {playlist_id} not found."

            playlist_manager = next((pm for pm in self.playlist_managers if pm.id == playlist_id), None)
            if playlist_manager:
                playlist_manager.update()
                playlist.last_update = datetime.datetime.now().strftime("%B %d, %Y - %H:%M")
                self.save_data_to_json()
        except Exception as e:
            print(f"Error updating playlist with ID {playlist_id}: {e}", exc_info=True)
            logging.error(f"Error updating playlist with ID {playlist_id}: {e}", exc_info=True)
            return f"An error occurred while updating the playlist with ID {playlist_id}. Please check the logs for more details."
        return None

    def list_playlists(self) -> List[PlaylistData]:
        return [PlaylistData.from_dict(pl) if isinstance(pl, dict) else pl for pl in self.data["playlists"]]

    def get_playlist(self, playlist_id: str) -> Optional[PlaylistData]:
        for pl in self.data["playlists"]:
            if pl.id == playlist_id:
                return pl
        return None

    def get_audio_managers(self, playlist_id: str) -> Optional[List[IAudioManager]]:
        for pl in self.playlist_managers:
            if pl.id == playlist_id:
                return pl.get_audio_managers()
        print(f"Playlist {playlist_id} not found in CentralManager.")
        logging.error(f"Playlist {playlist_id} not found in CentralManager.")
        return None

    def delete_playlist(self, playlist_id: str) -> None:
        # Supprimer la playlist des données
        self.data["playlists"] = [pl for pl in self.data["playlists"] if pl.id != playlist_id]

        # Sauvegarder les données mises à jour dans le fichier JSON
        self.save_data_to_json()

    def update_path(self, new_path: str, playlist_id: str) -> bool:
        yousync_folder_name = ".yousync"
        if os.path.basename(new_path) != yousync_folder_name:
            new_path = os.path.join(new_path, yousync_folder_name)
            if not os.path.exists(new_path):
                return False

        # Vérifier si le fichier {playlist_data.id}.json se trouve dans le dossier
        playlist_file = f"{playlist_id}.json"
        playlist_file_path = os.path.join(new_path, playlist_file)
        if os.path.exists(playlist_file_path):
            for playlist in self.data["playlists"]:
                if playlist.id == playlist_id:
                    playlist.path = playlist_file_path
                    playlist_manager = next((pm for pm in self.playlist_managers if pm.id == playlist_id), None)
                    if not playlist_manager:
                        playlist_manager = self.create_playlist_manager(playlist)
                        self.playlist_managers.append(playlist_manager)
                    playlist_manager.update_path(os.path.dirname(new_path))
                    self.save_data_to_json()
                    return True
            return False
        else:
            return False
