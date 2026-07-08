from core.audio_managers.IAudioManager import IAudioManager
from core.utils import (
    get_cached_video_title,
    get_deezer_track_data,
    get_deezer_track_id,
    normalize_deezer_track,
)

from threading import Lock
from typing import Any, Dict, Optional

import logging
import os
import tempfile


class DeezerAudioManager(IAudioManager):
    def __init__(
        self,
        url: str,
        path_to_save_audio: str,
        data_filepath: str,
        lock: Lock,
        deezer_track_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.url = url
        self.deezer_track_data = deezer_track_data or {}
        self.track_id = get_deezer_track_id(url)

        if not self.deezer_track_data and self.track_id:
            try:
                self.deezer_track_data = normalize_deezer_track(get_deezer_track_data(self.track_id))
            except Exception as exc:
                logging.warning(f"Unable to fetch Deezer track metadata for {url}: {exc}")
                self.deezer_track_data = {}

        cached_title = get_cached_video_title(url, data_filepath) or self.__extract_title()
        super().__init__(url, path_to_save_audio, data_filepath, self.track_id, cached_title, lock)

        if self.deezer_track_data:
            self.__apply_deezer_metadata_to_cache()

#----------------------------------Download Process-------------------------------------#

    def __youtube_search_query(self) -> str:
        parts = [self.__extract_title(), self.__extract_artist()]
        return " ".join(part for part in parts if part).strip()

    def __get_youtube_url_from_deezer(self) -> str:
        from youtube_search import YoutubeSearch

        query = self.__youtube_search_query()

        if not query:
            raise ValueError(f"Unable to build a YouTube search query for Deezer track: {self.url}")

        results = list(YoutubeSearch(query, max_results=1).to_dict())

        if not results:
            raise ValueError(f"No YouTube result found for Deezer track: {query}")

        return "https://www.youtube.com" + results[0]["url_suffix"]

    def download_audio(self) -> None:
        from moviepy.audio.io.AudioFileClip import AudioFileClip
        from pytubefix import YouTube

        youtube_url = self.__get_youtube_url_from_deezer()
        yt = YouTube(youtube_url)
        audio_stream = yt.streams.filter(only_audio=True).first()

        temp_dir = tempfile.gettempdir()
        downloaded_file = audio_stream.download(
            output_path=temp_dir,
            filename=self.safe_download_filename(getattr(audio_stream, "subtype", "mp4")),
        )

        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(self.metadata.path_to_save_audio_with_title)
        audio_clip.close()
        os.remove(downloaded_file)

    def add_metadata(self) -> None:
        if not self.metadata.is_downloaded or self.metadata.metadata_updated:
            print("Audio is not downloaded")
            return

        self.register_metadata(
            self.__extract_title(),
            self.__extract_artist(),
            self.__extract_album(),
            self.__extract_image(),
        )

    def __apply_deezer_metadata_to_cache(self) -> None:
        self.metadata.title = self.__extract_title()
        self.metadata.artist = self.__extract_artist()
        self.metadata.album = self.__extract_album()
        self.metadata.image_url = self.__extract_image()
        self.metadata.duration = self.__extract_duration()
        self.update_data()

    def __extract_title(self) -> str:
        title = str(self.deezer_track_data.get("title") or "").strip()
        return title or f"track_{self.track_id or 'deezer'}"

    def __extract_artist(self) -> str:
        artists = self.deezer_track_data.get("artists")

        if isinstance(artists, list):
            return ", ".join(str(artist).strip() for artist in artists if str(artist).strip())

        return str(artists or "").strip()

    def __extract_album(self) -> str:
        return str(self.deezer_track_data.get("album") or "").strip()

    def __extract_image(self) -> str:
        return str(self.deezer_track_data.get("cover") or "").strip()

    def __extract_duration(self) -> Optional[int]:
        duration = self.deezer_track_data.get("duration")

        try:
            return int(duration) if duration not in (None, "") else None
        except (TypeError, ValueError):
            return None
