import logging
import requests
from core.playlist_managers.IPlaylistManager import IPlaylistManager
from concurrent.futures import ThreadPoolExecutor
from core.audio_managers.SoundCloudAudioManager import SoundCloudAudioManager
from typing import List, Optional
from soundcloud import SoundCloud
from bs4 import BeautifulSoup

class SoundCloudPlaylistManager(IPlaylistManager):

    def __init__(self, playlist_url: str, path_to_save_audio: str, client_id: str) -> None:
        self.client_id = client_id
        self.client = SoundCloud(self.client_id)
        resolved_url = self.client.resolve(playlist_url)

        if not resolved_url or resolved_url.kind != 'playlist':
            print("Invalid URL")
            raise ValueError(f'Playlist NOT FOUND: {playlist_url}')

        self.playlist_data = resolved_url

        logging.debug("Initializing SoundCloudPlaylistManager")
        super().__init__(playlist_url, path_to_save_audio, str(self.playlist_data.id))

    # Override Method
    def new_audio_manager(self, url: str) -> Optional[SoundCloudAudioManager]:
        try:
            logging.debug("Creating SoundCloudAudioManager")
            if url is None:
                return None
            track = next((track for track in self.playlist_data.tracks if track.permalink_url == url), None)
            audio_manager = SoundCloudAudioManager(url, self.path_to_save_audio, self.playlist_data_filepath, self.lock, track, self.client_id)
            return audio_manager
        except Exception as e:
            logging.error(f"Error initializing SoundCloudAudioManager: {e}")
            print(f"Error initializing SoundCloudAudioManager: {e}")
            return None

    # Override Method
    def get_playlist_title(self) -> str:
        return self.playlist_data.title

    # Override Function
    def extract_image(self) -> str:
        if self.playlist_data.artwork_url is not None:
            return self.playlist_data.artwork_url
        html_page = requests.get(self.playlist_url).text
        soup = BeautifulSoup(html_page, 'html.parser')
        return soup.find('meta', property='og:image')['content']

    # Override Method
    def get_video_urls(self) -> List[str]:
        # Check if tracks are of type MiniTrack and resolve them to full tracks if necessary
        full_tracks = []
        for track in self.playlist_data.tracks:
            if not hasattr(track, 'permalink_url'):
                # If the track does not have a permalink_url, make an API request to get the full track details
                track_url = f"https://api.soundcloud.com/tracks/{track.id}?client_id={self.client_id}"
                print(track_url)
                track_response = requests.get(track_url)
                print(f"track response: {track_response}")
                if track_response.status_code == 200:
                    track_data = track_response.json()
                    print(f"track track_data: {track_data}")
                    track.permalink_url = track_data['permalink_url']
                    print(f"track permalink_url: {track.permalink_url}")
                else:
                    logging.error(f"Failed to fetch track details for track ID {track.id}")
                    print(f"Failed to fetch track details for track ID {track.id}")
                    continue
            full_tracks.append(track)
        return [track.permalink_url for track in full_tracks]

    # Override Method
    def download(self) -> None:
        def download_audio(audio_manager: SoundCloudAudioManager) -> None:
            audio_manager.download()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(download_audio, audio_manager) for audio_manager in self.audio_managers]
            for future in futures:
                future.result()
        logging.debug("Downloading videos ...")

    # Override Function
    def extract_video_id(self, url: str) -> Optional[str]:
        track = next((track for track in self.playlist_data.tracks if track.permalink_url == url), None)
        return str(track.id) if track else None
