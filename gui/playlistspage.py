import customtkinter
from PIL import Image, ImageTk
import os
from PIL import Image
from tkinter import Canvas
from gui.playlistpage import PlaylistPage
from tkinter import filedialog
from gui.utils import *
import threading
from gui.tooltip import ToolTip
from gui.notifications.notificationmanager import NotificationManager
from gui.style import *
from core.central_manager import CentralManager


class PlaylistsPage(customtkinter.CTkFrame):
    def __init__(self, parent, image_path, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.image_path = image_path
        self.tiles = []
        self.sync_image = Image.open(os.path.join(self.image_path, "sync.png"))
        self.load_image = Image.open(os.path.join(self.image_path, "load.png"))
        self.notification_manager = NotificationManager(self, self.image_path)
        self.adding_folder = False
        self.syncing_playlists = []
        self.parent.central_manager = CentralManager("playlists.json", self.update_progress)
        self.join_thread = threading.Thread(target=self.join_load_managers_thread)
        self.join_thread.start()
        len(self.parent.central_manager.list_playlists())
        self.setup_ui()

    def update_progress(self, current, total ):
        if self.notification_manager.progress_notification is None:
            self.notification_manager.show_progress_bar_notification(total)
        self.notification_manager.update_progress_bar_notification(current)

    def setup_ui(self):
        self.title_label = customtkinter.CTkLabel(self, text="My playlists", font=("Roboto", 24, "bold"), fg_color="transparent", text_color=WHITE_TEXT_COLOR)
        self.title_label.pack(pady=20, padx=20, fill="x")

        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(fill="both", expand=True, pady=20, padx=(30, 0))

        # Add Button
        add_image = Image.open(os.path.join(self.image_path, "add.png"))
        self.add_ctk_image = customtkinter.CTkImage(light_image=add_image, dark_image=add_image)
        self.add_button = customtkinter.CTkButton(self, text="", command=self.add, height=45, width=45, image=self.add_ctk_image, fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR)
        #!!! x postition hardcoded, need to replace logic
        self.add_button.place(x=800, y=30)
        ToolTip(self.add_button, "Retreive existing playlist")

        self.load_playlists()

    def join_load_managers_thread(self):
        self.parent.central_manager.load_managers_thread.join()
        self.notification_manager.show_notification("Playlists loaded successfully!")

    def add(self):
        if self.adding_folder:
            self.notification_manager.show_notification(
                "One file is already being recovered. Please try again later.",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            return
        folder_selected = filedialog.askdirectory()
        if folder_selected:
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


    def load_playlists(self):
        for tile in self.tiles:
            tile[1].destroy()
        self.tiles.clear()

        playlists = self.parent.central_manager.list_playlists()
        rowlen = 4
        index = 0
        for playlist in playlists:
            print(f"playlist: {playlist.id}")

            tile = self.add_playlist_tile(1 + index // rowlen, index % rowlen, playlist)
            self.tiles.append((playlist.id, tile))
            index += 1

    def truncate_string(self, s, max_length):
        if s is None:
            return None
        if len(s) > max_length:
            return s[:max_length-3] + "..."
        return s

    def add_playlist_tile(self, row, column, playlist):
        image_file = os.path.join(os.path.dirname(playlist.path), "cover.jpg")
        frame = customtkinter.CTkFrame(self.scrollable_frame, corner_radius=5, fg_color="transparent")
        frame.grid(row=row, column=column, padx=10, pady=10, sticky="nsew")

        canvas = Canvas(frame, width=180, height=140, bd=0, highlightthickness=0, bg=self['bg'])
        canvas.pack()

        image_path = os.path.join(self.image_path, image_file)
        photo_img = create_image(image_path, 180, 140)

        image_id = canvas.create_image(90, 70, image=photo_img)
        canvas.image = photo_img

        sync_icon_photo = ImageTk.PhotoImage(self.sync_image)
        canvas.sync_icon_id = canvas.create_image(160, 120, image=sync_icon_photo)
        canvas.sync_icon_photo = sync_icon_photo
        canvas.tag_bind(image_id, "<Button-1>", lambda event, title=playlist.title, image_path=image_path: self.open_playlist_page(title, image_path, playlist))

        canvas.tag_bind(canvas.sync_icon_id, "<Button-1>", lambda event, c=canvas, p=playlist: self.update_playlist(c, self.sync_image, p))

        title_label = customtkinter.CTkLabel(frame, text=self.truncate_string(playlist.title, 18), text_color=WHITE_TEXT_COLOR)
        title_label.pack(pady=(0, 10))

        return frame

    def open_playlist_page(self, title, image_path, playlist):
        playlist_page = PlaylistPage(self.parent, title, self.image_path, image_path, playlist, fg_color="transparent")
        playlist_page.grid(row=0, column=1, sticky="nsew")
        playlist_page.lift()

    def sync_playlist_rotation(self, canvas, image, playlist, angle=0, thread=None):
        if thread is None or not thread.is_alive():
            print("Rotation completed!")
            sync_icon_photo = ImageTk.PhotoImage(self.sync_image)
            canvas.itemconfig(canvas.sync_icon_id, image=sync_icon_photo)
            canvas.sync_icon_photo = sync_icon_photo
            canvas.tag_bind(canvas.sync_icon_id, "<Button-1>", lambda event, c=canvas: self.update_playlist(c, self.sync_image, playlist))
            self.syncing_playlists.remove(playlist.id)
        else:
            rotated_image = image.rotate(angle)
            rotated_photo = ImageTk.PhotoImage(rotated_image)
            canvas.itemconfig(canvas.sync_icon_id, image=rotated_photo)
            canvas.sync_icon_photo = rotated_photo  # Update reference!
            canvas.after(50, lambda: self.sync_playlist_rotation(canvas, image, playlist, angle + 10, thread))

    def update_playlist(self, canvas, image, playlist):
        if playlist.id in self.syncing_playlists:
            self.notification_manager.show_notification(
                "This playlist is being synchronized. Please try again later.",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
        elif self.parent.central_manager.playlist_loaded:
            self.syncing_playlists.append(playlist.id)
            update_thread = threading.Thread(target=self.parent.central_manager.update_playlist, args=(playlist.id,))
            update_thread.start()
            self.sync_playlist_rotation(canvas, image, playlist, thread=update_thread)
        else:
            self.notification_manager.show_notification(
                "Playlist is not yet loaded. Please try again later.",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )

#TODO: Notification de début et de fin de chargement des playlists
#TODO: Notification lorsque on clique sur add et qu'il est déjà en chargement d'une playlist