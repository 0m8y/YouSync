from tkinter import filedialog
import threading
import os
import customtkinter
import sys
import re
from PIL import Image, ImageTk
import queue
from typing import Any

from gui.notifications.notificationmanager import NotificationManager
from gui.notifications.progressbarnotification import ProgressBarNotification
from gui.playlists.playlisttile import PlaylistTile
from gui.tooltip import ToolTip
import logging
from core.CentralManager import CentralManager
from gui.style import WHITE_TEXT_COLOR, BUTTON_COLOR, HOVER_COLOR, NOTIFICATION_DURATION, RED_COLOR, GREEN_COLOR, RED_HOVER_COLOR, GREEN_HOVER_COLOR
from gui.playlists.playlisttile import PlaylistTile
from core.CentralManager import PlaylistData

spotify_pattern = re.compile(r'https://open\.spotify\.com/.*')
youtube_pattern = re.compile(r'https://(www\.)?(youtube\.com|youtu\.be)/.*')
apple_pattern = re.compile(r'https://music\.apple\.com/[a-z]{2}/(album|playlist)/[a-zA-Z0-9\-%.]+/[a-zA-Z0-9\-%.]+')

class PlaylistsPage(customtkinter.CTkFrame):
    def __init__(self, parent: Any, image_path: str, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.image_path = image_path

        self.playlist_tiles: list[PlaylistTile] = []
        self.platform: str = "all"

        self.central_manager: CentralManager | None = None

        self.load_image = Image.open(os.path.join(self.image_path, "load.png"))
        self.adding_folder = False

        self.notification_manager = NotificationManager(self, self.image_path)
        self.progress_notification: ProgressBarNotification = None
        self.init_central_manager()

        self.setup_ui()

    def init_central_manager(self) -> None:
        if self.central_manager is None:
            self.central_manager = CentralManager("playlists.json", self.update_progress)

            playlists_data = self.central_manager.list_playlists()

            for playlist_data in playlists_data:
                if not os.path.exists(os.path.dirname(playlist_data.path)):
                    self.show_path_not_found_popup(playlist_data)

            try:
                self.join_thread = threading.Thread(target=self.join_load_managers_thread)
                self.join_thread.start()
            except Exception as e:
                logging.debug(f"Error init central manager. : {e}")

    def show_path_not_found_popup(self, playlist_data: PlaylistData) -> None:
        def on_close() -> None:
            self.parent.quit()
            popup.destroy()
            sys.exit(0)
        popup = customtkinter.CTkToplevel(self)
        popup.title(f"{playlist_data.title} path not found")

        message = customtkinter.CTkLabel(popup, text=f"The playlist path {playlist_data.title} no longer exists. Old path: {os.path.dirname(os.path.dirname(playlist_data.path))}.", text_color=WHITE_TEXT_COLOR)
        message.pack(pady=(20, 0), padx=20)

        message2 = customtkinter.CTkLabel(popup, text="What would you like to do?", text_color=WHITE_TEXT_COLOR)
        message2.pack(pady=(0, 20), padx=20)

        button_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        button_frame.pack(pady=20)

        delete_button = customtkinter.CTkButton(button_frame, text="Delete Playlist", command=lambda: self.delete_playlist(popup, playlist_data), fg_color=RED_COLOR, hover_color=RED_HOVER_COLOR, text_color=WHITE_TEXT_COLOR)
        delete_button.pack(side="left", padx=20)

        resync_button = customtkinter.CTkButton(button_frame, text="Re-sync Playlist", command=lambda: self.resync_playlist(popup, playlist_data), fg_color=GREEN_COLOR, hover_color=GREEN_HOVER_COLOR, text_color=WHITE_TEXT_COLOR)
        resync_button.pack(side="right", padx=20)

        popup.update_idletasks()

        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()

        popup_width = popup.winfo_width()
        popup_height = popup.winfo_height()

        x_coordinate = (screen_width / 2) - (popup_width / 2)
        y_coordinate = (screen_height / 2) - (popup_height / 2)

        popup.geometry(f"+{int(x_coordinate)}+{int(y_coordinate)}")

        popup.protocol("WM_DELETE_WINDOW", on_close)

        popup.grab_set()  # Make the popup modal
        self.wait_window(popup)  # Wait until the popup is closed

    def delete_playlist(self, popup: customtkinter.CTkToplevel, playlist_data: PlaylistData) -> None:
        popup.grab_release()  # Release the grab before destroying the popup
        popup.destroy()
        self.central_manager.delete_playlist(playlist_data.id)

    def resync_playlist(self, popup: customtkinter.CTkToplevel, playlist_data: PlaylistData) -> None:
        folder_selected = filedialog.askdirectory()
        if (self.central_manager.update_path(folder_selected, playlist_data.id)):
            popup.grab_release()  # Release the grab before destroying the popup
            popup.destroy()
            return
        self.notification_manager.show_notification(
            "Path found no .yousync files.",
            duration=NOTIFICATION_DURATION,
            text_color=WHITE_TEXT_COLOR
        )

    def reload(self) -> None:
        self.join_thread = threading.Thread(target=self.join_load_managers_thread)
        self.join_thread.start()

    def update_progress(self, current: int, total: int) -> None:
        if self.progress_notification is None:
            self.progress_notification = self.notification_manager.show_progress_bar_notification(total, "Loading playlists...")
        self.notification_manager.update_progress_bar_notification(self.progress_notification, current)

    def join_load_managers_thread(self) -> None:
        def load_managers() -> None:
            self.central_manager.instantiate_playlist_managers()
            self.queue.put("playlists_loaded")

        self.queue: queue.Queue[str] = queue.Queue()
        self.load_managers_thread = threading.Thread(target=load_managers)
        self.load_managers_thread.start()
        self.check_queue()

    def check_queue(self) -> None:
        try:
            while True:
                task = self.queue.get_nowait()
                if task == "playlists_loaded":
                    self.notification_manager.show_notification("Playlists loaded successfully!")
                    self.parent.playlist_loaded = True
                    for id, tile in self.playlist_tiles:
                        tile.update_cover()
        except queue.Empty:
            pass
        self.after(100, self.check_queue)

    def setup_ui(self) -> None:
        self.title_label = customtkinter.CTkLabel(self, text="My playlists", font=("Roboto", 24, "bold"), fg_color="transparent", text_color=WHITE_TEXT_COLOR)
        self.title_label.pack(pady=20, padx=20, fill="x")

        # Filter buttons
        filter_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(pady=(0, 10))

        self.all_button = customtkinter.CTkButton(filter_frame, text="All", command=lambda: self.filter_playlists("all"), fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, text_color=WHITE_TEXT_COLOR)
        self.all_button.pack(side="left", padx=10)

        self.youtube_button = customtkinter.CTkButton(filter_frame, text="YouTube", command=lambda: self.filter_playlists("youtube"), fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, text_color=WHITE_TEXT_COLOR)
        self.youtube_button.pack(side="left", padx=10)

        self.spotify_button = customtkinter.CTkButton(filter_frame, text="Spotify", command=lambda: self.filter_playlists("spotify"), fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, text_color=WHITE_TEXT_COLOR)
        self.spotify_button.pack(side="left", padx=10)

        self.apple_button = customtkinter.CTkButton(filter_frame, text="Apple Music", command=lambda: self.filter_playlists("apple"), fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, text_color=WHITE_TEXT_COLOR)
        self.apple_button.pack(side="left", padx=10)

        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(fill="both", expand=True, pady=20, padx=(30, 0))

        # Add Button
        add_image = Image.open(os.path.join(self.image_path, "add.png"))
        self.add_ctk_image = customtkinter.CTkImage(light_image=add_image, dark_image=add_image)
        self.add_button = customtkinter.CTkButton(self, text="", command=self.add_existing_playlist, height=45, width=45, image=self.add_ctk_image, fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR)
        #!!! x postition hardcoded, need to replace logic
        self.add_button.place(x=800, y=30)
        ToolTip(self.add_button, "Retreive existing playlist")

        self.update_button_colors()
        self.load_playlists()

    def load_playlists(self) -> None:
        for tile in self.playlist_tiles:
            tile[1].destroy()
        self.playlist_tiles.clear()

        playlists = self.central_manager.list_playlists()

        rowlen = 4
        index = 0
        for playlist in playlists:
            if self.platform == "all" or (self.platform == "spotify" and spotify_pattern.match(playlist.url)) or (self.platform == "youtube" and youtube_pattern.match(playlist.url)) or (self.platform == "apple" and apple_pattern.match(playlist.url)):
                tile = self.add_playlist_tile(1 + index // rowlen, index % rowlen, playlist)
                self.playlist_tiles.append((playlist.id, tile))
                index += 1

    def filter_playlists(self, platform: str) -> None:
        if self.platform != platform:
            self.platform = platform
            self.update_button_colors()
            self.load_playlists()

    def update_button_colors(self) -> None:
        buttons = {
            "all": self.all_button,
            "youtube": self.youtube_button,
            "spotify": self.spotify_button,
            "apple": self.apple_button
        }

        for key, button in buttons.items():
            if key == self.platform:
                button.configure(fg_color=HOVER_COLOR)
            else:
                button.configure(fg_color=BUTTON_COLOR)

    def add_playlist_tile(self, row: int, column: int, playlist: PlaylistData) -> PlaylistTile:
        return PlaylistTile(self, row, column, playlist, self.image_path, self.scrollable_frame)

#*********************************ADD EXISTING PLAYLIST*********************************#
    def add_existing_playlist(self) -> None:
        if self.adding_folder:
            self.notification_manager.show_notification(
                "One file is already being recovered. Please try again later.",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            return
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.notification_manager.show_notification(
                "Start of playlist recovery.",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            self.adding_folder = True
            add_thread = threading.Thread(target=self.central_manager.add_existing_playlists, args=(folder_selected,))
            add_thread.start()
            self.sync_add_button_rotation(add_thread)

    def sync_add_button_rotation(self, thread: threading.Thread, angle: int = 0) -> None:
        if thread.is_alive():
            rotated_image = self.load_image.rotate(angle)
            rotated_photo = ImageTk.PhotoImage(rotated_image)
            self.add_button.configure(image=rotated_photo)
            self.add_button.image = rotated_photo  # Update reference
            self.add_button.after(50, lambda: self.sync_add_button_rotation(thread, angle + 10))
        else:
            print("Addition completed!")
            self.add_button.configure(image=self.add_ctk_image)
            self.add_button.image = self.add_ctk_image
            self.adding_folder = False
            self.load_playlists()
            self.notification_manager.show_notification(
                "New playlist loaded!",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
