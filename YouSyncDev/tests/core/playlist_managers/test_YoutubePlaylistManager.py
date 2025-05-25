import shutil
from core.playlist_managers.YoutubePlaylistManager import YoutubePlaylistManager
from threading import Lock
import pytest
import os
import eyed3

URL_YOUTUBE_PLAYLIST = "https://www.youtube.com/playlist?list=PLsOoDQgfBdd17erA74nVTQE4g7O1tjW6k"
URL_300_SONG_PLAYLIST = "https://www.youtube.com/playlist?list=PLsOoDQgfBdd0vQdAIsLOx4UoFjYjGQGux"

@pytest.fixture
def temp_path():
    path = os.path.join("tests", "temp_files", "yt_playlist_test")
    os.makedirs(path, exist_ok=True)
    return path

def test_youtube_playlist_manager_real(temp_path):
    manager = None
    try:
        manager = YoutubePlaylistManager(URL_YOUTUBE_PLAYLIST, temp_path)
        manager.update()
        audio_managers = manager.get_audio_managers()

        # ✅ Vérifie que 5 morceaux sont bien chargés (1 URL est invalide)
        assert len(audio_managers) == 5 # tolérance pour l'URL invalide

        # ✅ Lancer le téléchargement complet
        manager.download()

        for am in audio_managers:
            # Vérifie que le fichier existe
            assert os.path.exists(am.metadata.path_to_save_audio_with_title)

            assert am.metadata.is_downloaded == True
            assert am.metadata.metadata_updated == True
            # Vérifie que l'audio contient bien un tag
            audio = eyed3.load(am.metadata.path_to_save_audio_with_title)
            assert audio is not None
            assert audio.tag is not None

    finally:
        if manager:
            for am in manager.get_audio_managers():
                try:
                    am.delete()
                except Exception as e:
                    print(f"Deletion error: {e}")
        if os.path.exists(temp_path):
            try:
                shutil.rmtree(temp_path)
            except Exception as e:
                print(f"Folder deletion error {temp_path}: {e}")


@pytest.mark.skip(reason="To run only for advanced testing")
def test_youtube_playlist_manager_300_songs(temp_path):
    manager = None
    try:
        manager = YoutubePlaylistManager(URL_300_SONG_PLAYLIST, temp_path)
        manager.update()
        audio_managers = manager.get_audio_managers()

        # ✅ Vérifie que 5 morceaux sont bien chargés (1 URL est invalide)
        assert len(audio_managers) >= 250

        # ✅ Lancer le téléchargement complet
        manager.download()

        for am in audio_managers:
            # Vérifie que le fichier existe
            if not am.metadata.is_downloaded:
                print(f"⚠️ video unavailable {am.get_url()}")
                continue
            assert os.path.exists(am.metadata.path_to_save_audio_with_title)

            assert am.metadata.metadata_updated == True
            # Vérifie que l'audio contient bien un tag
            audio = eyed3.load(am.metadata.path_to_save_audio_with_title)
            assert audio is not None
            assert audio.tag is not None

    finally:
        if manager:
            for am in manager.get_audio_managers():
                try:
                    am.delete()
                except Exception as e:
                    print(f"Erreur lors du delete: {e}")
        if os.path.exists(temp_path):
            try:
                shutil.rmtree(temp_path)
            except Exception as e:
                print(f"Erreur lors de la suppression du dossier {temp_path}: {e}")
