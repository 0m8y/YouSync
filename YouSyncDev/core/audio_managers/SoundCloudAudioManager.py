from core.audio_managers.IAudioManager import IAudioManager

import os
import subprocess
from typing import Any
from soundcloud import BasicTrack, MiniTrack
import logging

class SoundCloudAudioManager(IAudioManager):

    def __init__(self, url, path_to_save_audio, data_filepath, lock, track_info: Any | BasicTrack | MiniTrack, client_id: str):
        self.track_info = track_info
        self.client_id = client_id
        super().__init__(url, path_to_save_audio, data_filepath, str(self.track_info.id), self.track_info.title, lock)

    #Override Function
    def download_audio(self):
        if not os.path.exists(self.path_to_save_audio):
            os.makedirs(self.path_to_save_audio)
        command = f'scdl -l "{self.url}" --client-id {self.client_id} --path "{self.path_to_save_audio}" --no-playlist-folder'
        logging.debug(f"Downloading audio: {command}")
        print(f"Downloading audio: {command}")
        subprocess.run(command, shell=True, check=True)

    #Override Function
    def add_metadata(self):
        if self.is_downloaded is False or self.metadata_updated is True:
            print("Audio is not downloaded")
            return

        self.title = self.track_info.title
        self.artist = self.track_info.user.full_name
        self.video_title = self.track_info.title

        self.register_metadata(image_url=self.track_info.artwork_url)
