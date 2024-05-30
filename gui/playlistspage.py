import customtkinter
from PIL import Image, ImageTk
import os
from PIL import Image, ImageOps, ImageDraw
from tkinter import Canvas
from playlistpage import PlaylistPage
from tkinter import filedialog
from utils import *

class PlaylistsPage(customtkinter.CTkFrame):
    def __init__(self, parent, image_path, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.image_path = image_path
        self.sync_images = []
        self.light_sync_image = Image.open(os.path.join(self.image_path, "sync_light.png"))
        self.dark_sync_image = Image.open(os.path.join(self.image_path, "sync_dark.png"))
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
        print("add")
        # folder_selected = filedialog.askdirectory()
        # if folder_selected:
            # Suppose that the folder name is the playlist name and contains an image file named "cover.png"
            # playlist_name = os.path.basename(folder_selected)
            # cover_image_path = os.path.join(folder_selected, "cover.png")

            # Add the new playlist to the list
            # self.playlists.append((playlist_name, cover_image_path))
            # self.load_playlists()

    def load_playlists(self):
        playlists = [
            ("BigParty", "BigParty.png"),
            ("CremRap", "default_preview.png"),
            ("Rap US", "default_preview.png"),
            ("Rap FR", "default_preview.png"),
            ("Techno", "default_preview.png"),
            ("ACID", "default_preview.png"),
            ("2STEP", "default_preview.png"),
            ("HARD", "default_preview.png"),
        ]
        rowlen = 4
        for index, (title, image_file) in enumerate(playlists):
            self.add_playlist_tile(1 + index // rowlen, index % rowlen, title, image_file)

    def add_playlist_tile(self, row, column, title, image_file):
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
        canvas.tag_bind(image_id, "<Button-1>", lambda event, title=title, image_path=image_path: self.open_playlist_page(title, image_path))

        canvas.tag_bind(canvas.sync_icon_id, "<Button-1>", lambda event, c=canvas: self.start_rotation(c, self.light_sync_image))

        title_label = customtkinter.CTkLabel(frame, text=title)
        title_label.pack(pady=(0, 10))

    def open_playlist_page(self, title, image_path):
        # This method switches to the PlaylistPage, passing the title and image path
        playlist_page = PlaylistPage(self.parent, title, self.image_path, image_path, fg_color="transparent")
        playlist_page.grid(row=0, column=1, sticky="nsew")
        playlist_page.lift()

    def draw_round_button_with_image(self, canvas, x, y, image):
        img_id = canvas.create_image(x, y, image=image)
        canvas.tag_bind(img_id, "<Button-1>", lambda event, c=canvas: self.start_rotation(c, image))
        # canvas.tag_bind(img_id, "<Button-1>", self.button_click_action)

    def start_rotation(self, canvas, image, angle=0):
        if angle < 360:
            rotated_image = image.rotate(angle)
            rotated_photo = ImageTk.PhotoImage(rotated_image)
            canvas.itemconfig(canvas.sync_icon_id, image=rotated_photo)
            canvas.sync_icon_photo = rotated_photo  # Update reference!
            canvas.after(50, lambda: self.start_rotation(canvas, image, angle + 10))
        else:
            print("Rotation completed!")
            sync_icon_photo = ImageTk.PhotoImage(self.light_sync_image)
            canvas.sync_icon_id = canvas.create_image(160, 120, image=sync_icon_photo)
            canvas.sync_icon_photo = sync_icon_photo
            canvas.tag_bind(canvas.sync_icon_id, "<Button-1>", lambda event, c=canvas: self.start_rotation(c, self.light_sync_image))

    def button_click_action(self, event):
        print("Button clicked!")

    def update_image_mode(self, mode):
        if mode == "light":
            new_image = ImageTk.PhotoImage(self.light_sync_image)
        else:
            new_image = ImageTk.PhotoImage(self.dark_sync_image)
        self.sync_image = new_image
        self.draw_round_button_with_image(self.canvas, 165, 125, 30, self.sync_image)
