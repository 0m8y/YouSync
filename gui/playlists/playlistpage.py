import os, threading, customtkinter
from PIL import Image, ImageTk, ImageOps
from concurrent.futures import ThreadPoolExecutor

from gui.utils import create_image
from gui.tooltip import ToolTip
from gui.style import *

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
        self.song_list_frame = None
        self.download_green = Image.open(os.path.join(self.image_path, "download_green.png"))
        self.download_orange = Image.open(os.path.join(self.image_path, "download_orange.png"))
        self.download_red = Image.open(os.path.join(self.image_path, "download_red.png"))

        self.setup_ui()

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

        self.reload_song_list()

    def download_playlist(self):
        if not self.on_download:
            self.playlists_page.notification_manager.show_notification(
                "download is already in progress!", 
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            return

        audio_managers_not_downloaded = [am for am in self.audio_managers if not am.is_downloaded or not am.metadata_updated]

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
                self.reload_song_list()
                self.playlists_page.notification_manager.update_progress_bar_notification(self.progress_notification, i + 1)
                self.on_download = False



    def download_audio(self, audio_manager):
        audio_manager.download()

    def reload_song_list(self):
        if hasattr(self, 'song_list_frame') and self.song_list_frame is not None:
            self.song_list_frame.destroy()

        self.song_list_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.song_list_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        for i, manager in enumerate(self.audio_managers):
            bg_color = SECOND_COLOR if i % 2 == 0 else FIRST_COLOR
            song_frame = customtkinter.CTkFrame(self.song_list_frame, fg_color=bg_color, height=40)
            song_frame.grid_columnconfigure(0, weight=0)
            song_frame.grid_columnconfigure(1, weight=5)
            song_frame.pack(fill="x", pady=2, padx=10)
            
            track_number_label = customtkinter.CTkLabel(song_frame, text=f"{i + 1}.", anchor="w", fg_color="transparent", text_color=HOVER_COLOR)
            track_number_label.grid(row=0, column=0, sticky="w", padx=(10, 5))

            song_title_label = customtkinter.CTkLabel(song_frame, text=f"{manager.video_title}", anchor="w", fg_color="transparent", text_color=WHITE_TEXT_COLOR)
            song_title_label.grid(row=0, column=1, sticky="w", padx=(5, 10))

            if manager.is_downloaded:
                icon_ctk_image = customtkinter.CTkImage(self.download_green, size=(15, 15))
                tip = "The music is fully downloaded."
            elif manager.metadata_updated:
                icon_ctk_image = customtkinter.CTkImage(self.download_orange, size=(15, 15))
                tip = "Metadata not downloaded, click to download."
            else:
                icon_ctk_image = customtkinter.CTkImage(self.download_red, size=(15, 15))
                tip = "Music not downloaded, click to download."

            icon_label = customtkinter.CTkLabel(song_frame, text="", image=icon_ctk_image, fg_color="transparent")
            icon_label.image = icon_ctk_image
            icon_label.grid(row=0, column=2, sticky="e", padx=(10, 10))
            ToolTip(icon_label, tip)

            if not manager.is_downloaded:
                icon_label.bind("<Button-1>", lambda event, m=manager, l=icon_label, i=customtkinter.CTkImage(self.download_green, size=(15, 15)): self.download_music(m, l, i))

    def download_music(self, manager, icon_label, icon_ctk_image):
        def download():
            self.playlists_page.notification_manager.show_notification(
                f"Downloading {manager.video_title}...", 
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            manager.download()
            self.playlists_page.notification_manager.show_notification(
                f"{manager.video_title} is downloaded!", 
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            icon_label.configure(image=icon_ctk_image)
            icon_label.image = icon_ctk_image
        download_thread = threading.Thread(target=download)
        download_thread.start()

    def update_sync_icon(self, angle):
        rotated_image = self.sync_image.rotate(angle)
        rotated_photo = ImageTk.PhotoImage(rotated_image)
        self.sync_button.configure(image=rotated_photo)
        self.sync_button.image = rotated_photo  # Update reference
        self.sync_button.update_idletasks()

    def sync_completed(self):
        sync_icon_photo = ImageTk.PhotoImage(self.sync_image)
        self.sync_button.configure(image=sync_icon_photo)
        self.sync_button.image = sync_icon_photo
        self.on_update = False
