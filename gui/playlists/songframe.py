import os, threading, customtkinter
from PIL import Image, ImageTk, ImageOps
from concurrent.futures import ThreadPoolExecutor

from gui.utils import create_image
from gui.tooltip import ToolTip
from gui.style import *

class SongFrame:
    def __init__(self, parent, track_frame, song_number, bg_color, audio_manager, green_image, orange_image, red_image):
        self.playlist_page = parent
        self.track_frame = track_frame
        self.id = audio_manager.id
        self.audio_manager = audio_manager
        self.green_image = green_image
        self.orange_image = orange_image
        self.red_image = red_image
        self.on_progress = False
        self.song_frame = customtkinter.CTkFrame(self.track_frame, fg_color=bg_color, height=40)
        self.song_frame.grid_columnconfigure(0, weight=0)
        self.song_frame.grid_columnconfigure(1, weight=5)
        self.song_frame.pack(fill="x", pady=2, padx=10)
    
        track_number_label = customtkinter.CTkLabel(self.song_frame, text=f"{song_number}.", anchor="w", fg_color="transparent", text_color=HOVER_COLOR)
        track_number_label.grid(row=0, column=0, sticky="w", padx=(10, 5))

        song_title_label = customtkinter.CTkLabel(self.song_frame, text=f"{self.audio_manager.video_title}", anchor="w", fg_color="transparent", text_color=WHITE_TEXT_COLOR)
        song_title_label.grid(row=0, column=1, sticky="w", padx=(5, 10))

        self.update_icon_status()

    def update_icon_status(self):
        if hasattr(self, 'icon_label'):
            self.icon_label.after(1, self.icon_label.destroy)

        if not self.audio_manager.is_downloaded:
            icon_ctk_image = customtkinter.CTkImage(self.red_image, size=(15, 15))
            tip = "Music not downloaded, click to download."
        elif not self.audio_manager.metadata_updated:
            icon_ctk_image = customtkinter.CTkImage(self.orange_image, size=(15, 15))
            tip = "Metadata not downloaded, click to download."
        else:
            icon_ctk_image = customtkinter.CTkImage(self.green_image, size=(15, 15))
            tip = "The music is fully downloaded."

        self.icon_label = customtkinter.CTkLabel(self.song_frame, text="", image=icon_ctk_image, fg_color="transparent")
        self.icon_label.image = icon_ctk_image
        self.icon_label.grid(row=0, column=2, sticky="e", padx=(10, 10))
        ToolTip(self.icon_label, tip)
        if not self.audio_manager.is_downloaded or not self.audio_manager.metadata_updated:
            self.icon_label.bind("<Button-1>", lambda event: self.download_music())

    def download_music(self):
        if self.on_progress:
            self.playlist_page.playlists_page.notification_manager.show_notification(
                f"{self.audio_manager.video_title} is already in progress!", 
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            return
        download_thread = threading.Thread(target=self._download)
        download_thread.start()

    def download(self):
        self.audio_manager.download()
        self.update_icon_status()

    def _download(self):
        self.on_progress = True
        self.playlist_page.playlists_page.notification_manager.show_notification(
            f"Downloading {self.audio_manager.video_title}...", 
            duration=NOTIFICATION_DURATION,
            text_color=WHITE_TEXT_COLOR
        )
        self.download()
        self.playlist_page.playlists_page.notification_manager.show_notification(
            f"{self.audio_manager.video_title} is downloaded!", 
            duration=NOTIFICATION_DURATION,
            text_color=WHITE_TEXT_COLOR
        )
        self.on_progress = False

    def destroy(self):
        self.song_frame.destroy()