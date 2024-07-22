import os
import threading
import customtkinter
from typing import Any
from tkinter import filedialog
from PIL import Image, ImageTk, ImageOps

from core.CentralManager import Platform
from gui.style import WHITE_TEXT_COLOR, HOVER_COLOR, BUTTON_COLOR
from gui.notifications.notificationmanager import NotificationManager


class NewSpotifyPlaylist(customtkinter.CTkFrame):
    def __init__(self, parent: customtkinter.CTk, image_path: str, **kwargs: Any):
        self.image_path: str = image_path
        self.parent_app: customtkinter.CTk = parent
        self.notification_manager: NotificationManager = self.parent_app.playlists_page.notification_manager
        super().__init__(parent, **kwargs)
        self.setup_ui()

    def create_label(self, text: str, row: int, font_size: int = 25, pady: tuple = (30, 0)) -> None:
        label = customtkinter.CTkLabel(self, text=text, text_color=WHITE_TEXT_COLOR, font=('Roboto Medium', font_size))
        label.grid(row=row, column=1, columnspan=2, pady=pady, sticky="w")

    def go_back(self) -> None:
        self.parent_app.go_back_home()

    def setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)

        # Back Button
        light_back_image = Image.open(os.path.join(self.image_path, "back_light.png"))
        self.back_ctk_image = customtkinter.CTkImage(light_image=light_back_image, dark_image=light_back_image)
        self.back_button = customtkinter.CTkButton(self, text="", command=self.go_back, height=45, width=45, image=self.back_ctk_image, fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR)
        self.back_button.place(x=30, y=30)

        # Logo Spotify
        spotify_logo = Image.open(os.path.join(self.image_path, "Spotify_logo.png"))
        padded_image = ImageOps.expand(spotify_logo, border=0, fill='black')
        resized_image = padded_image.resize((216, 65))
        tk_logo = ImageTk.PhotoImage(resized_image)
        self.logo_label = customtkinter.CTkLabel(self, image=tk_logo, text="")
        self.logo_label.image = tk_logo
        self.logo_label.grid(row=0, column=1, pady=(30, 40))

        # Spotify URL Section
        self.create_label("Enter Playlist URL", 1)
        self.create_label("Make sure the playlist is not private.", 2, font_size=11, pady=(0, 0))
        self.url_entry = customtkinter.CTkEntry(self, placeholder_text="Playlist URL", width=600, height=45, border_width=0, fg_color=BUTTON_COLOR)
        self.url_entry.grid(row=3, column=1, padx=(0, 0), pady=10, sticky="ew")

        # Path Section
        self.create_label("Search path to save playlist", 4)
        self.path_entry = customtkinter.CTkEntry(self, placeholder_text="Path to save", width=600, height=45, border_width=0, fg_color=BUTTON_COLOR)
        self.path_entry.configure(state="disabled")
        self.path_entry.grid(row=5, column=1, padx=(0, 0), pady=10, sticky="ew")

        # Folder Button
        light_photo_image = Image.open(os.path.join(self.image_path, "folder.png"))
        self.folder_ctk_image = customtkinter.CTkImage(light_image=light_photo_image, dark_image=light_photo_image)
        self.browse_button = customtkinter.CTkButton(self, text="", command=self.browse_file, width=45, height=45, image=self.folder_ctk_image, fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, corner_radius=0)
        self.browse_button.grid(row=5, column=1, sticky="e")

        # Save Button
        self.save_button = customtkinter.CTkButton(self, text="Save", command=self.save, width=120, height=45,
                                                   fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, text_color=WHITE_TEXT_COLOR)
        self.save_button.grid(row=6, column=1, padx=(0, 0), pady=40)

        # Notification Section
        self.notification_label = customtkinter.CTkLabel(self, text="", text_color=WHITE_TEXT_COLOR)
        self.notification_label.grid(row=7, column=1, sticky="ew")

    def clear_entries(self) -> None:
        self.url_entry.delete(0, customtkinter.END)
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, customtkinter.END)
        self.path_entry.configure(state="disabled")

    def browse_file(self) -> None:
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, customtkinter.END)
            self.path_entry.insert(0, folder_selected)
            self.path_entry.configure(state="disabled")

    def save(self) -> None:
        url = self.url_entry.get()
        path = self.path_entry.get()
        if not self.validate_path(path):
            self.notification_manager.show_notification("Please enter a valid path.", text_color=("red"))
        else:
            def add_and_load() -> None:
                self.notification_manager.show_notification("Adding playlist...")
                self.parent_app.get_central_manager().add_playlist(url, path, Platform.SPOTIFY)
                self.notification_manager.show_notification("The playlist has been added!")
                self.parent_app.playlists_page.reload()
                self.parent_app.playlists_page.load_playlists()
                self.clear_entries()

            add_thread = threading.Thread(target=add_and_load)
            add_thread.start()

    def validate_path(self, path: str) -> bool:
        if not os.path.exists(path):
            return False

        if not os.path.isdir(path):
            return False

        return True
