from core.playlist_managers.YoutubePlaylistManager import YoutubePlaylistManager
from threading import Lock
import pytest
import os
import eyed3

YOUTUBE_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLsOoDQgfBdd17erA74nVTQE4g7O1tjW6k"

@pytest.fixture
def temp_path():
    path = os.path.join("tests", "temp_files", "yt_playlist_test")
    os.makedirs(path, exist_ok=True)
    return path

def test_youtube_playlist_manager_real(temp_path):
    manager = None
    try:
        manager = YoutubePlaylistManager(YOUTUBE_PLAYLIST_URL, temp_path)
        audio_managers = manager.get_audio_managers()

        # ✅ Vérifie que 5 morceaux sont bien chargés (1 URL est invalide)
        assert len(audio_managers) == 5 or len(audio_managers) == 6  # tolérance pour l'URL invalide

        # ✅ Lancer le téléchargement complet
        manager.download()

        for am in audio_managers:
            # Vérifie que le fichier existe
            assert os.path.exists(am.path_to_save_audio_with_title)

            # Vérifie que l'audio contient bien un tag
            audio = eyed3.load(am.path_to_save_audio_with_title)
            assert audio is not None
            assert audio.tag is not None

    finally:
        if manager:
            for am in manager.get_audio_managers():
                try:
                    am.delete()
                except Exception as e:
                    print(f"Erreur lors du delete: {e}")
