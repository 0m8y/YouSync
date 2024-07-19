import customtkinter
import os
import threading
from PIL import ImageTk, Image
from tkinter import Canvas

from gui.utils import create_image, truncate_string
from gui.playlists.playlistpage import PlaylistPage
from gui.style import WHITE_TEXT_COLOR, NOTIFICATION_DURATION


class PlaylistTile:
    def __init__(self, parent, row, column, playlist, image_path, scrollable_frame):
        self.playlists_page = parent
        self.row = row
        self.column = column
        self.playlist_data = playlist
        self.image_path = image_path
        self.scrollable_frame = scrollable_frame
        self.on_update = False
        self.playlist_page = None

        self.sync_image = Image.open(os.path.join(self.image_path, "sync.png"))

        self.cover_frame = customtkinter.CTkFrame(self.scrollable_frame, corner_radius=5, fg_color="transparent")
        self.cover_frame.grid(row=row, column=column, padx=10, pady=10, sticky="nsew")

        self.cover_canvas = Canvas(self.cover_frame, width=180, height=140, bd=0, highlightthickness=0, bg=self.playlists_page['bg'])
        self.cover_canvas.pack()

        self.cover_filename = os.path.join(os.path.dirname(self.playlist_data.path), self.playlist_data.id + ".jpg")
        if not os.path.exists(self.cover_filename):
            self.cover_filename = os.path.join(self.image_path, "default_preview.png")
        self.cover_img = create_image(self.cover_filename, 180, 140)
        self.cover_image_id = self.cover_canvas.create_image(90, 70, image=self.cover_img)
        self.cover_canvas.image = self.cover_img
        self.cover_canvas.tag_bind(self.cover_image_id, "<Button-1>", lambda event: self.open_playlist_page(self.playlist_data, self.cover_canvas))

        sync_icon_photo = ImageTk.PhotoImage(self.sync_image)
        self.cover_canvas.sync_icon_id = self.cover_canvas.create_image(160, 120, image=sync_icon_photo)
        self.cover_canvas.sync_icon_photo = sync_icon_photo

        self.cover_canvas.tag_bind(self.cover_canvas.sync_icon_id, "<Button-1>", lambda event, c=self.cover_canvas: self.update_playlist())

        title_label = customtkinter.CTkLabel(self.cover_frame, text=truncate_string(self.playlist_data.title, 18), text_color=WHITE_TEXT_COLOR)
        title_label.pack(pady=(0, 10))

    def update_cover(self):
        print("Updating cover...")
        new_cover_filename = os.path.join(os.path.dirname(self.playlist_data.path), self.playlist_data.id + ".jpg")
        if self.cover_filename == new_cover_filename:
            return
        if not os.path.exists(new_cover_filename):
            self.cover_filename = os.path.join(self.image_path, "default_preview.png")
        else:
            self.cover_filename = new_cover_filename
        self.cover_img = create_image(self.cover_filename, 180, 140)
        self.cover_canvas.itemconfig(self.cover_image_id, image=self.cover_img)
        print(f"Cover updated: {self.cover_filename}")

    def update_playlist(self):
        if self.on_update:
            self.playlists_page.notification_manager.show_notification(
                "This playlist is on update. Please try again later.",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
        elif self.playlists_page.parent.central_manager.playlist_loaded:
            self.playlists_page.notification_manager.show_notification(
                f"{self.playlist_data.title} synchronization in progress...",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            self.on_update = True
            self.update_thread = threading.Thread(target=self.playlists_page.parent.central_manager.update_playlist, args=(self.playlist_data.id,))
            self.update_thread.start()
            self.sync_playlist_rotation()
        else:
            self.playlists_page.notification_manager.show_notification(
                "Playlist is not yet loaded. Please try again later.",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )

    def sync_playlist_rotation(self, angle=0):
        if self.on_update and self.update_thread is not None and self.update_thread.is_alive():
            rotated_image = self.sync_image.rotate(angle)
            rotated_photo = ImageTk.PhotoImage(rotated_image)
            self.cover_canvas.itemconfig(self.cover_canvas.sync_icon_id, image=rotated_photo)
            self.cover_canvas.sync_icon_photo = rotated_photo  # Update reference!
            self.cover_canvas.after(50, lambda: self.sync_playlist_rotation(angle + 10))
            if self.playlist_page is not None:
                self.playlist_page.update_sync_icon(angle)
        else:
            print("Rotation completed!")
            sync_icon_photo = ImageTk.PhotoImage(self.sync_image)
            self.cover_canvas.itemconfig(self.cover_canvas.sync_icon_id, image=sync_icon_photo)
            self.cover_canvas.sync_icon_photo = sync_icon_photo
            self.cover_canvas.tag_bind(self.cover_canvas.sync_icon_id, "<Button-1>", lambda event: self.update_playlist())
            self.on_update = False
            self.playlists_page.notification_manager.show_notification(
                f"{self.playlist_data.title} is synchronized.",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            self.update_cover()
            if self.playlist_page is not None:
                self.playlist_page.update_cover(self.cover_filename)
                self.playlist_page.sync_completed()
                self.playlist_page.update_tracklist()

    def open_playlist_page(self, playlist, canvas):
        if not self.playlists_page.parent.central_manager.playlist_loaded:
            self.playlists_page.notification_manager.show_notification(
                "This playlist is being synchronized. Please try again later.",
                duration=NOTIFICATION_DURATION,
                text_color=WHITE_TEXT_COLOR
            )
            return
        self.playlist_page = PlaylistPage(self.playlists_page, self.image_path, self.cover_filename, playlist, self, fg_color="transparent")
        self.playlist_page.grid(row=0, column=1, sticky="nsew")
        self.playlist_page.lift()

    def update_sync_icon(self, angle):
        rotated_image = self.sync_image.rotate(angle)
        rotated_photo = ImageTk.PhotoImage(rotated_image)
        self.cover_canvas.itemconfig(self.cover_canvas.sync_icon_id, image=rotated_photo)
        self.cover_canvas.sync_icon_photo = rotated_photo  # Update reference!
        self.cover_canvas.update_idletasks()

    def destroy(self):
        self.cover_frame.destroy()
