import os
import json
import pytest
from threading import Lock
from pytubefix import YouTube
from unittest.mock import mock_open, patch
import builtins
from unittest.mock import patch, mock_open, MagicMock

# Copier la classe IAudioManager ici si besoin ou l'importer correctement
from core.audio_managers.IAudioManager import IAudioManager

URL = "https://www.youtube.com/watch?v=lxd1b-abNJw&ab_channel=Omay-Topic"

@pytest.fixture(scope="session")
def temp_path():
    path = os.path.join("tests", "temp_files")
    os.makedirs(path, exist_ok=True)
    return path

# Dummy class pour tester la classe abstraite
class DummyAudioManager(IAudioManager):
    def download_audio(self): pass
    def add_metadata(self): pass

@pytest.fixture
def dummy_audio_manager(temp_path):
    return DummyAudioManager(
        url=URL,
        path_to_save_audio=str(temp_path),
        data_filepath=os.path.join(temp_path, "test_IAudioManager.json"),
        lock=Lock(),
        id= YouTube(URL).video_id,
        video_title="SampleVideo"
    )

def test_load_data_file_not_found(dummy_audio_manager):
    with patch("builtins.open", side_effect=FileNotFoundError()):
        assert dummy_audio_manager.load_data() == []

def test_load_data_valid_file(dummy_audio_manager):
    # On prépare des données simulées comme si elles étaient lues depuis un fichier JSON
    test_data = {
        "audios": [
            {
                "url": URL,
                "path_to_save_audio_with_title": "tests/temp_files/SampleVideo.mp3",
                "is_downloaded": True,
                "metadata_updated": True,
                "video_title": "SampleVideo",
                "title": "SomeTitle",
                "artist": "SomeArtist",
                "album": "SomeAlbum",
                "image_url": "http://example.com/image.jpg"
            }
        ]
    }

    # On simule l'ouverture du fichier et le contenu retourné
    mocked_open = mock_open(read_data=json.dumps(test_data))

    with patch("builtins.open", mocked_open):
        result = dummy_audio_manager.load_data()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["url"] == URL
        assert result[0]["title"] == "SomeTitle"

def test_save_data_to_file(dummy_audio_manager):
    test_data = [
        {
            "url": URL,
            "path_to_save_audio_with_title": dummy_audio_manager.path_to_save_audio_with_title,
            "is_downloaded": dummy_audio_manager.is_downloaded,
            "metadata_updated": dummy_audio_manager.metadata_updated,
            "video_title": dummy_audio_manager.video_title,
            "title": dummy_audio_manager.title,
            "artist": dummy_audio_manager.artist,
            "album": dummy_audio_manager.album,
            "image_url": dummy_audio_manager.image_url
        }
    ]

    # Simule un fichier JSON initial vide
    initial_json = json.dumps({"audios": [dummy_audio_manager.to_dict()]})
    mocked_open = mock_open(read_data=initial_json)

    with patch("builtins.open", mocked_open):
        dummy_audio_manager.save_data_to_file(test_data)

        # On récupère tous les appels à write()
        handle = mocked_open()
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)

        # Vérifie que le JSON est valide
        written = json.loads(written_content)
        assert "audios" in written
        assert written["audios"][0]["url"] == URL

def test_delete_audio_manager(dummy_audio_manager):
    # Simuler l'existence du fichier .mp3
    with patch("os.path.exists", return_value=True), \
         patch("os.remove") as mock_remove, \
         patch("builtins.open", mock_open(read_data=json.dumps({
             "audios": [dummy_audio_manager.to_dict()]
         }))) as mock_file:

        # Appeler delete()
        dummy_audio_manager.delete()

        # ✅ Vérifie que le fichier .mp3 a bien été supprimé
        mock_remove.assert_called_once_with(dummy_audio_manager.path_to_save_audio_with_title)

        # ✅ Vérifie que les nouvelles données ne contiennent plus l'entrée
        handle = mock_file()
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        data = json.loads(written_content)
        assert "audios" in data
        assert dummy_audio_manager.url not in [a["url"] for a in data["audios"]]

def test_delete_audio_manager_no_file_but_json_entry(dummy_audio_manager):
    with patch("os.path.exists", return_value=False), \
         patch("os.remove") as mock_remove, \
         patch("builtins.open", mock_open(read_data=json.dumps({
             "audios": [dummy_audio_manager.to_dict()]
         }))) as mock_file:

        dummy_audio_manager.delete()

        mock_remove.assert_not_called()

        handle = mock_file()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        data = json.loads(written)
        assert dummy_audio_manager.url not in [entry["url"] for entry in data["audios"]]

def test_delete_audio_manager_file_exists_but_no_json_entry(dummy_audio_manager):
    with patch("os.path.exists", return_value=True), \
         patch("os.remove") as mock_remove, \
         patch("builtins.open", mock_open(read_data=json.dumps({
             "audios": []  # JSON ne contient pas l'URL
         }))) as mock_file:

        dummy_audio_manager.delete()

        mock_remove.assert_called_once_with(dummy_audio_manager.path_to_save_audio_with_title)

        handle = mock_file()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        data = json.loads(written)
        assert data["audios"] == []

def test_delete_audio_manager_nothing_to_delete(dummy_audio_manager):
    with patch("os.path.exists", return_value=False), \
         patch("os.remove") as mock_remove, \
         patch("builtins.open", mock_open(read_data=json.dumps({
             "audios": []
         }))) as mock_file:

        dummy_audio_manager.delete()

        mock_remove.assert_not_called()

        handle = mock_file()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        data = json.loads(written)
        assert data["audios"] == []

def test_update_data(dummy_audio_manager):
    # Simuler une entrée JSON existante avec valeurs initiales
    initial_data = {"audios": [dummy_audio_manager.to_dict()]}

    # On modifie les attributs de l'instance
    dummy_audio_manager.title = "Titre mis à jour"
    dummy_audio_manager.artist = "Artiste mis à jour"
    dummy_audio_manager.album = "Album mis à jour"
    dummy_audio_manager.image_url = "https://example.com/image.jpg"
    dummy_audio_manager.is_downloaded = True
    dummy_audio_manager.metadata_updated = True

    mocked_open = mock_open(read_data=json.dumps(initial_data))

    with patch("builtins.open", mocked_open):
        dummy_audio_manager.update_data()

        handle = mocked_open()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        data = json.loads(written)
        updated_entry = next(a for a in data["audios"] if a["url"] == dummy_audio_manager.url)
        assert updated_entry["title"] == "Titre mis à jour"
        assert updated_entry["artist"] == "Artiste mis à jour"
        assert updated_entry["album"] == "Album mis à jour"
        assert updated_entry["image_url"] == "https://example.com/image.jpg"

def test_download_triggers_metadata_only(dummy_audio_manager):
    dummy_audio_manager.is_downloaded = True
    dummy_audio_manager.metadata_updated = False

    with patch.object(dummy_audio_manager, 'add_metadata') as mock_metadata:
        dummy_audio_manager.download()
        mock_metadata.assert_called_once()
