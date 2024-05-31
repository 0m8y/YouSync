import customtkinter
from PIL import Image, ImageTk
import os
from PIL import Image, ImageOps, ImageDraw
from tkinter import Canvas
from gui.playlistpage import PlaylistPage
from tkinter import filedialog
from gui.utils import *
import threading

class PlaylistsPage(customtkinter.CTkFrame):
    def __init__(self, parent, image_path, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.image_path = image_path
        self.tiles = []
        self.light_sync_image = Image.open(os.path.join(self.image_path, "sync_light.png"))
        self.setup_ui()

    def setup_ui(self):
        self.title_label = customtkinter.CTkLabel(self, text="My playlists", font=("Roboto", 24, "bold"), fg_color="transparent")
        self.title_label.pack(pady=20, padx=20, fill="x")

        self.scrollable_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(fill="both", expand=True, pady=20, padx=(30, 0))

        # Add Button
        add_image = Image.open(os.path.join(self.image_path, "add.png"))
        self.add_ctk_image = customtkinter.CTkImage(light_image=add_image, dark_image=add_image)
        self.add_button = customtkinter.CTkButton(self, text="", command=self.add, height=45, width=45, image=self.add_ctk_image, fg_color=("#bdbdbd", "#333333"), hover_color=("gray70", "gray30"))
        self.add_button.place(x=30, y=30)

        self.load_playlists()

    # Mettez à jour la méthode add
    def add(self):
        folder_selected = filedialog.askdirectory()
        print(f"add on {folder_selected}")
        if folder_selected:
            response = self.parent.central_manager.add_existing_playlists(folder_selected)
            print(f"{response}")
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

        sync_icon_photo = ImageTk.PhotoImage(self.light_sync_image)
        canvas.sync_icon_id = canvas.create_image(160, 120, image=sync_icon_photo)
        canvas.sync_icon_photo = sync_icon_photo
        canvas.tag_bind(image_id, "<Button-1>", lambda event, title=playlist.title, image_path=image_path: self.open_playlist_page(title, image_path))

        canvas.tag_bind(canvas.sync_icon_id, "<Button-1>", lambda event, c=canvas, p=playlist: self.update_playlist(c, self.light_sync_image, p))

        title_label = customtkinter.CTkLabel(frame, text=self.truncate_string(playlist.title, 18))
        title_label.pack(pady=(0, 10))

        return frame

    def open_playlist_page(self, title, image_path):
        playlist_page = PlaylistPage(self.parent, title, self.image_path, image_path, fg_color="transparent")
        playlist_page.grid(row=0, column=1, sticky="nsew")
        playlist_page.lift()

    def start_rotation(self, canvas, image, playlist, angle=0, thread=None):
        if thread is None or not thread.is_alive():
            print("Rotation completed!")
            sync_icon_photo = ImageTk.PhotoImage(self.light_sync_image)
            canvas.itemconfig(canvas.sync_icon_id, image=sync_icon_photo)
            canvas.sync_icon_photo = sync_icon_photo
            canvas.tag_bind(canvas.sync_icon_id, "<Button-1>", lambda event, c=canvas: self.update_playlist(c, self.light_sync_image, playlist))
        else:
            rotated_image = image.rotate(angle)
            rotated_photo = ImageTk.PhotoImage(rotated_image)
            canvas.itemconfig(canvas.sync_icon_id, image=rotated_photo)
            canvas.sync_icon_photo = rotated_photo  # Update reference!
            canvas.after(50, lambda: self.start_rotation(canvas, image, playlist, angle + 10, thread))

    def update_playlist(self, canvas, image, playlist):
        update_thread = threading.Thread(target=self.parent.central_manager.update_playlist, args=(playlist.id,))
        update_thread.start()
        self.start_rotation(canvas, image, playlist, thread=update_thread)
