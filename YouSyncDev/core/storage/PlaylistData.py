from dataclasses import dataclass
from typing import List
from core.storage.AudioMetadata import AudioMetadata

@dataclass
class PlaylistData:
    playlist_url: str
    path_to_save_audio: str
    title: str
    audios: List[AudioMetadata]
