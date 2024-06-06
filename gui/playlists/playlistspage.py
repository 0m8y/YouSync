from tkinter import Canvas, filedialog
import threading, os, customtkinter
from PIL import Image, ImageTk

from gui.notifications.notificationmanager import NotificationManager
from gui.playlists.playlistpage import PlaylistPage
from gui.playlists.playlisttile import PlaylistTile
from gui.tooltip import ToolTip
from gui.utils import *
from gui.style import *

from core.central_manager import CentralManager

class PlaylistsPage(customtkinter.CTkFrame):
    def __init__(self, parent, image_path, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.image_path = image_path

        self.playlist_tiles = []
        self.syncing_playlists = []
        self.syncing_icons = []

        self.load_image = Image.open(os.path.join(self.image_path, "load.png"))
        self.adding_folder = False
        
        self.notification_manager = NotificationManager(self, self.image_path)
        self.progress_notification = None
        self.init_central_manager()
        
        self.setup_ui()

    def init_central_manager(self):
        if self.parent.central_manager is None:
            self.parent.central_manager = CentralManager("playlists.json", self.update_progress)
            self.join_thread = threading.Thread(target=self.join_load_managers_thread)
            self.join_thread.start()

    def reload(self):
        self.join_thread = threading.Thread(target=self.join_load_managers_thread)
        self.join_thread.start()

    def update_progress(self, current, total):
        if self.progress_notification is None:
            self.progress_notification = self.notification_manager.show_progress_bar_notification(total, "Loading playlists...")
        self.notification_manager.update_progress_bar_notification(self.progress_notification, current)

    def join_load_managers_thread(self):
        self.parent.central_manager.load_managers_thread.join()
        self.notification_manager.show_notification("Playlists loaded successfully!")
        self.parent.central_manager.playlist_loaded = True

    def setup_ui(self):
        self.title_label = customtkinter.CTkLabel(self, text="My playlists", font=("Roboto", 24, "bold"), fg_color="transparent", text_color=WHITE_TEXT_COLOR)
        self.title_label.pack(pady=20, padx=20, fill="x")

        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(fill="both", expand=True, pady=20, padx=(30, 0))

        # Add Button
        add_image = Image.open(os.path.join(self.image_path, "add.png"))
        self.add_ctk_image = customtkinter.CTkImage(light_image=add_image, dark_image=add_image)
        self.add_button = customtkinter.CTkButton(self, text="", command=self.add_existing_playlist, height=45, width=45, image=self.add_ctk_image, fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR)
        #!!! x postition hardcoded, need to replace logic
        self.add_button.place(x=800, y=30)
        ToolTip(self.add_button, "Retreive existing playlist")

        self.load_playlists()

    def load_playlists(self):
        for tile in self.playlist_tiles:
            tile[1].destroy()
        self.playlist_tiles.clear()

        playlists = self.parent.central_manager.list_playlists()

        rowlen = 4
        for index, playlist in enumerate(playlists):
            tile = self.add_playlist_tile(1 + index // rowlen, index % rowlen, playlist)
            self.playlist_tiles.append((playlist.id, tile))

    def add_playlist_tile(self, row, column, playlist):
        return PlaylistTile(self, row, column, playlist, self.image_path, self.scrollable_frame)

#*********************************ADD EXISTING PLAYLIST*********************************#
    def add_existing_playlist(self):
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
            add_thread = threading.Thread(target=self.parent.central_manager.add_existing_playlists, args=(folder_selected,))
            add_thread.start()
            self.sync_add_button_rotation(add_thread)

    def sync_add_button_rotation(self, thread, angle=0):
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
