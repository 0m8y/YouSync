import os
import threading
import customtkinter
import platform
import subprocess
from PIL import Image, ImageTk, ImageOps
from concurrent.futures import ThreadPoolExecutor

from gui.utils import create_image
from gui.tooltip import ToolTip
from gui.playlists.songframe import SongFrame
from gui.style import WHITE_TEXT_COLOR, BUTTON_COLOR, HOVER_COLOR, NOTIFICATION_DURATION


class PlaylistPage(customtkinter.CTkFrame):
    def __init__(self, parent, image_path, image_file, playlist, playlist_tile, **kwargs):
        super().__init__(parent.parent, **kwargs)
        self.main_app = parent.parent
        self.playlists_page = parent
        self.central_manager = self.main_app.central_manager
        self.playlist_data = playlist
        self.title = self.playlist_data.title
        self.image_path = image_path
        self.cover_pic = os.path.join(self.image_path, image_file)
        self.last_update = self.playlist_data.last_update
        self.audio_managers = self.central_manager.get_audio_managers(playlist.id)
        self.song_count = len(self.audio_managers)
        self.on_update = False
        sync_image = Image.open(os.path.join(self.image_path, "sync2.png"))
        sync_padded_image = ImageOps.expand(sync_image, border=0, fill='black')
        self.sync_image = sync_padded_image.resize((25, 25))

        self.playlist_tile = playlist_tile
        self.progress_notification = None
        self.on_download = False
        self.songframe_by_id = {}
        self.track_frame = None
        self.download_green = Image.open(os.path.join(self.image_path, "download_green.png"))
        self.download_orange = Image.open(os.path.join(self.image_path, "download_orange.png"))
        self.download_red = Image.open(os.path.join(self.image_path, "download_red.png"))
        folder_image = Image.open(os.path.join(self.image_path, "folder.png"))
        sync_padded_image = ImageOps.expand(folder_image, border=0, fill='black')
        self.folder_image = sync_padded_image.resize((26, 26))

        self.setup_ui()

    def update_cover(self, new_image_path):
        if new_image_path == self.image_path:
            return
        if os.path.exists(new_image_path):
            self.image_path = new_image_path
            photo = create_image(self.image_path, 180, 180)
            self.image_label.configure(image=photo)
            self.image_label.image = photo
        else:
            print(f"Error: Image {new_image_path} not found.")

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Frame principale pour aligner le contenu à gauche
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        # Configuration de la grille pour la disposition
        main_frame.grid_columnconfigure(0, minsize=180)
        main_frame.grid_columnconfigure(1, weight=1)

        # Image de la playlist
        photo = create_image(self.cover_pic, 180, 180)
        self.image_label = customtkinter.CTkLabel(main_frame, image=photo, text="")
        self.image_label.image = photo  # Garder une référence
        self.image_label.grid(row=0, column=0, rowspan=2, padx=(55, 20), sticky="ns")

        # Sous-frame pour les labels de texte
        text_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        text_frame.grid(row=0, column=1, sticky="ew")

        # Titre de la playlist
        self.title_label = customtkinter.CTkLabel(text_frame, text=self.title, font=("Roboto", 20, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w")

        # Détails supplémentaires
        details_label = f"{self.song_count} songs"
        self.details_label = customtkinter.CTkLabel(text_frame, text=details_label, justify=customtkinter.LEFT, text_color=WHITE_TEXT_COLOR)
        self.details_label.grid(row=1, column=0, sticky="w")

        details_label2 = f"Last Update: {self.last_update}"
        self.details_label2 = customtkinter.CTkLabel(text_frame, text=details_label2, justify=customtkinter.LEFT, text_color=WHITE_TEXT_COLOR)
        self.details_label2.grid(row=2, column=0, sticky="w")

        # Back Button
        light_back_image = Image.open(os.path.join(self.image_path, "back_light.png"))
        self.back_ctk_image = customtkinter.CTkImage(light_image=light_back_image, dark_image=light_back_image)
        self.back_button = customtkinter.CTkButton(self, text="", command=self.main_app.go_back_playlists, height=45, width=45, image=self.back_ctk_image, fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR)
        self.back_button.place(x=15, y=30)

        # Synchronization Button
        sync_icon_photo = ImageTk.PhotoImage(self.sync_image)
        self.sync_button = customtkinter.CTkButton(self, width=25, height=25, text="", fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, image=sync_icon_photo, command=lambda: self.playlist_tile.update_playlist())
        self.sync_button.image = sync_icon_photo
        self.sync_button.place(x=274, y=135)
        ToolTip(self.sync_button, "Synchronize playlist.")

        # Download Button
        self.download_default_image = Image.open(os.path.join(self.image_path, "download.png"))
        padded_image = ImageOps.expand(self.download_default_image, border=0, fill='black')
        resized_image = padded_image.resize((25, 25))
        dl_icon_photo = ImageTk.PhotoImage(resized_image)
        self.download_all_button = customtkinter.CTkButton(self, width=25, height=25, text="", fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, image=dl_icon_photo, command=lambda: self.download_playlist())
        self.download_all_button.image = dl_icon_photo
        self.download_all_button.place(x=330, y=135)
        ToolTip(self.download_all_button, "Download all missing sounds.")

        # Folder Button
        folder_icon_photo = ImageTk.PhotoImage(self.folder_image)
        self.folder_button = customtkinter.CTkButton(self, width=25, height=25, text="", fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, image=folder_icon_photo, command=lambda: self.go_to_folder())
        self.folder_button.image = folder_icon_photo
        self.folder_button.place(x=386, y=135)
        ToolTip(self.folder_button, "Playlist folder.")

        self.track_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.track_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        self.init_tracklist()

    def go_to_folder(self):
        systeme = platform.system()
        path = os.path.dirname(os.path.dirname(self.playlist_data.path))
        if systeme == "Windows":
            os.startfile(path)
        elif systeme == "Darwin":  # macOS
            subprocess.Popen(["open", path])
        elif systeme == "Linux":
            subprocess.Popen(["xdg-open", path])
        else:
            raise NotImplementedError(f"Système d'exploitation non supporté: {systeme}")

    def download_playlist(self):
        if self.on_download:
            self.playlists_page.notification_manager.show_notification(
                "download is already in progress!",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            return

        audio_managers_not_downloaded = [am for am in self.audio_managers if (not am.is_downloaded or not am.metadata_updated) and not self.songframe_by_id[am.id].on_progress]

        if not audio_managers_not_downloaded:
            self.playlists_page.notification_manager.show_notification(
                "Everything is downloaded!",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            return

        self.progress_notification = self.playlists_page.notification_manager.show_progress_bar_notification(
            len(audio_managers_not_downloaded),
            f"Downloading {len(audio_managers_not_downloaded)} songs."
        )

        # Démarrer le téléchargement dans un thread séparé
        download_thread = threading.Thread(target=self._download_playlist, args=(audio_managers_not_downloaded,))
        download_thread.start()

    def _download_playlist(self, audio_managers_not_downloaded):

        self.on_download = True
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.download_audio, audio_manager) for audio_manager in audio_managers_not_downloaded]
            for i, future in enumerate(futures):
                future.result()
                self.playlists_page.notification_manager.update_progress_bar_notification(self.progress_notification, i + 1)
                self.on_download = False

    def download_audio(self, audio_manager):
        self.songframe_by_id[audio_manager.id].download()

    def init_tracklist(self):
        for i, manager in enumerate(self.audio_managers):
            songframe = SongFrame(self, self.track_frame, i + 1, manager, self.download_green, self.download_orange, self.download_red)
            self.songframe_by_id[songframe.id] = songframe

    def update_tracklist(self):
        for audio_manager in self.audio_managers:
            if audio_manager.id not in self.songframe_by_id:
                songframe = SongFrame(self, self.track_frame, 0, audio_manager, self.download_green, self.download_orange, self.download_red)
                self.songframe_by_id[songframe.id] = songframe

        id_to_delete = [id for id, songframe in self.songframe_by_id.items() if not any(audio_manager.id == id for audio_manager in self.audio_managers)]

        for id in id_to_delete:
            songframe = self.songframe_by_id.pop(id)
            songframe.song_frame.destroy()

        self.update_details_label()
        self.update_tracknumber()

    def update_tracknumber(self):
        for i, (id, songframe) in enumerate(self.songframe_by_id.items()):
            songframe.update_display(i + 1)

    def update_details_label(self):
        self.song_count = len(self.audio_managers)
        new_details_label = f"{self.song_count} songs"
        self.details_label.configure(text=new_details_label)
        self.details_label.update_idletasks()

        new_details_label2 = f"Last update: {self.playlist_data.last_update}"
        self.details_label2.configure(text=new_details_label2)
        self.details_label2.update_idletasks()

    def update_sync_icon(self, angle):
        rotated_image = self.sync_image.rotate(angle)
        rotated_photo = ImageTk.PhotoImage(rotated_image)
        self.sync_button.configure(image=rotated_photo)
        self.sync_button.image = rotated_photo
        self.sync_button.update_idletasks()

    def sync_completed(self):
        sync_icon_photo = ImageTk.PhotoImage(self.sync_image)
        self.sync_button.configure(image=sync_icon_photo)
        self.sync_button.image = sync_icon_photo
        self.on_update = False
