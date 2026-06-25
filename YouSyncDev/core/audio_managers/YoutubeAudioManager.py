from core.audio_managers.IAudioManager import IAudioManager
from core.utils import extract_json_object, get_cached_video_title, get_cached_video_id

from moviepy.audio.io.AudioFileClip import AudioFileClip
from bs4 import BeautifulSoup
from pytubefix import YouTube
from threading import Lock
import requests
import tempfile
import json
import os


class YoutubeAudioManager(IAudioManager):

    def __init__(self, url: str, path_to_save_audio: str, data_filepath: str, lock: Lock) -> None:
        self.url = url
        self.yt = None
        cached_title = get_cached_video_title(url, data_filepath) or self.__extract_title(True)
        video_id = get_cached_video_id(url, data_filepath) or self.__get_video_id()
        super().__init__(url, path_to_save_audio, data_filepath, video_id, cached_title, lock)

#----------------------------------Download Process-------------------------------------#

    def __ensure_youtube_loaded(self):
        if self.yt:
            return
        self.yt = YouTube(self.url)

    def __get_video_id(self):
        self.__ensure_youtube_loaded()
        return self.yt.video_id

    #Override Function
    def download_audio(self) -> None:
        self.__ensure_youtube_loaded()
        audio_stream = self.yt.streams.filter(only_audio=True).first()

        temp_dir = tempfile.gettempdir()
        downloaded_file = audio_stream.download(output_path=temp_dir)

        audio_clip = AudioFileClip(downloaded_file)
        audio_clip.write_audiofile(self.metadata.path_to_save_audio_with_title)
        audio_clip.close()
        os.remove(downloaded_file)

    #Override Function
    def add_metadata(self) -> None:
        self.__ensure_youtube_loaded()

        print("Adding Metada...")

        if not self.metadata.is_downloaded or self.metadata.metadata_updated:
            print("Audio is not downloaded or already updated")
            return

        json_data = None

        for attempt in range(10):
            print(f"\n========== METADATA DEBUG ATTEMPT {attempt + 1} ==========")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.get(self.url, headers=headers)
            print("[DEBUG] status_code:", response.status_code)

            if response.status_code != 200:
                print("❌ Erreur lors de la récupération de la page.")
                continue

            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")

            script_tags = soup.find_all("script")
            print("[DEBUG] script count:", len(script_tags))

            for index, script in enumerate(script_tags):
                if not script.string:
                    continue

                has_horizontal = "horizontalCardListRenderer" in script.string
                has_attribute = "videoAttributeViewModel" in script.string

                if has_horizontal or has_attribute:
                    print(f"\n[DEBUG] matching script index: {index}")
                    print("[DEBUG] has horizontalCardListRenderer:", has_horizontal)
                    print("[DEBUG] has videoAttributeViewModel:", has_attribute)
                    print("[DEBUG] script length:", len(script.string))

                if has_horizontal and has_attribute:
                    key_index = script.string.find("horizontalCardListRenderer")
                    attr_index = script.string.find("videoAttributeViewModel")

                    print("[DEBUG] horizontalCardListRenderer index:", key_index)
                    print("[DEBUG] videoAttributeViewModel index:", attr_index)

                    print("\n[DEBUG] around horizontalCardListRenderer:")
                    print(script.string[max(0, key_index - 500):key_index + 1500])

                    print("\n[DEBUG] around videoAttributeViewModel:")
                    print(script.string[max(0, attr_index - 500):attr_index + 1500])

                    key_index = script.string.find("horizontalCardListRenderer")

                    print("\n========== RAW AROUND REAL KEY ==========")
                    print(
                        script.string[
                            max(0, key_index - 2000):
                            key_index + 5000
                        ]
                    )

                    all_indexes = []

                    start = 0
                    while True:
                        idx = script.string.find("horizontalCardListRenderer", start)

                        if idx == -1:
                            break

                        all_indexes.append(idx)
                        start = idx + 1

                    print("\n========== ALL OCCURRENCES ==========")
                    print("count =", len(all_indexes))

                    for i, idx in enumerate(all_indexes[:20]):
                        print(f"\n--- occurrence {i} @ {idx} ---")
                        print(script.string[max(0, idx - 100):idx + 300])

                    json_data = extract_json_object(script.string, "horizontalCardListRenderer")

                    print("\n[DEBUG] extract_json_object result is None:", json_data is None)

                    if json_data:
                        print("[DEBUG] extracted json length:", len(json_data))
                        print("[DEBUG] extracted json start:")
                        print(json_data[:1000])
                        print("[DEBUG] extracted json end:")
                        print(json_data[-1000:])

                        try:
                            data = json.loads(json_data)
                            print("[DEBUG] json.loads OK")
                            print("[DEBUG] top-level type:", type(data))
                            print("[DEBUG] top-level keys:", list(data.keys()) if isinstance(data, dict) else None)
                            print(
                                "[DEBUG] horizontalCardListRenderer at root:",
                                isinstance(data, dict) and "horizontalCardListRenderer" in data
                            )

                            cards = data.get("horizontalCardListRenderer", {}).get("cards", []) if isinstance(data, dict) else []
                            print("[DEBUG] cards type:", type(cards))
                            print("[DEBUG] cards length:", len(cards) if isinstance(cards, list) else None)

                            if cards:
                                print("[DEBUG] first card keys:", list(cards[0].keys()))
                                print("[DEBUG] first card preview:")
                                print(json.dumps(cards[0], ensure_ascii=False)[:2000])

                        except json.JSONDecodeError as e:
                            print("[DEBUG] json.loads FAILED:", e)

                    if json_data:
                        break

            if not json_data:
                print("⚠️ No JSON found, retrying...")
                continue

            try:
                data = json.loads(json_data)
                cards = data.get("horizontalCardListRenderer", {}).get("cards", [])
                if cards:
                    print("[DEBUG] valid cards found, leaving retry loop")
                    break

                print("⚠️ JSON found but no cards, retrying...")

            except json.JSONDecodeError as e:
                print("[DEBUG] JSON decode failed after extraction:", e)
                json_data = None

        if not json_data:
            self.register_metadata("", "", "", self.yt.thumbnail_url)
            return

        try:
            data = json.loads(json_data)
            cards = data.get("horizontalCardListRenderer", {}).get("cards", [])

            if not cards:
                raise KeyError("cards")

            music_data = cards[0].get("videoAttributeViewModel", {})

            print("\n[DEBUG] final music_data:")
            print(json.dumps(music_data, ensure_ascii=False, indent=2)[:3000])

            title = music_data.get("title", "")
            artist = music_data.get("subtitle", "")
            album = music_data.get("secondarySubtitle", {}).get("content", "")
            image_sources = music_data.get("image", {}).get("sources", [])
            image_url = image_sources[0].get("url", "") if image_sources else self.yt.thumbnail_url

            print(f"**Titre**   : {title}")
            print(f"**Artiste** : {artist}")
            print(f"**Album**   : {album}")
            print(f"**Image**   : {image_url}")

            self.register_metadata(title, artist, album, image_url)
            print(f"[{self.metadata.video_title}] Metadata updated? {self.metadata.metadata_updated}")

        except (KeyError, json.JSONDecodeError) as e:
            print(f"⚠️ Erreur lors de l'extraction des métadonnées pour {self.url}: {e}")
            self.register_metadata("", "", "", self.yt.thumbnail_url)

    def __extract_title(self, file_mode: bool = False):
        self.__ensure_youtube_loaded()

        raw_title = self.yt.title

        if file_mode:
            # Supprime les caractères interdits dans les noms de fichiers
            cleaned_title = raw_title.translate(str.maketrans('', '', '|:"/\\?*<>')).strip()
        else:
            cleaned_title = raw_title.strip()

        if not cleaned_title:
            return f"track_{self.yt.video_id}"

        return cleaned_title
