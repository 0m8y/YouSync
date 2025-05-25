from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class AudioMetadata:
    url: str
    path_to_save_audio_with_title: str
    is_downloaded: bool = False
    metadata_updated: bool = False
    video_title: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    image_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AudioMetadata':
        return cls(**data)
