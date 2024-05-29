import customtkinter
from PIL import Image, ImageTk
import os
from PIL import Image, ImageOps, ImageDraw
from tkinter import Canvas

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
        self.grid_columnconfigure(0, weight=1)

        self.title_label = customtkinter.CTkLabel(self, text="My playlists", font=("Roboto", 24, "bold"), fg_color="transparent")
        self.title_label.grid(row=0, column=0, pady=20, sticky="ew")

        self.tiles_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self.tiles_frame.grid(row=1, column=0, pady=10, sticky="ew")
        self.tiles_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.tiles_frame.bind("<Configure>", self.onFrameConfigure)

        self.load_playlists()

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
            ("HARD", "default_preview.png"),
            ("HARD", "default_preview.png"),
            ("HARD", "default_preview.png"),
            ("HARD", "default_preview.png"),
        ]

        for index, (title, image_file) in enumerate(playlists):
            row = 1 + index // 3
            column = index % 3
            self.add_playlist_tile(row, column, title, image_file)

    def add_playlist_tile(self, row, column, title, image_file):
        frame = customtkinter.CTkFrame(self.tiles_frame, corner_radius=5, fg_color="transparent")
        frame.grid(row=row, column=column, padx=10, pady=10, sticky="nsew")
        canvas = Canvas(frame, width=180, height=140, bd=0, highlightthickness=0, bg=self['bg'])
        canvas.pack()

        image_path = os.path.join(self.image_path, image_file)
        img = Image.open(image_path)
        img = img.resize((180, 140))
        img = self.add_round_corners(img, rad=7)
        photo_img = ImageTk.PhotoImage(img)

        canvas.create_image(90, 70, image=photo_img)
        canvas.image = photo_img

        sync_icon_photo = ImageTk.PhotoImage(self.light_sync_image)
        canvas.sync_icon_id = canvas.create_image(160, 120, image=sync_icon_photo)
        canvas.sync_icon_photo = sync_icon_photo
        canvas.tag_bind(canvas.sync_icon_id, "<Button-1>", lambda event, c=canvas: self.start_rotation(c, self.light_sync_image))

        title_label = customtkinter.CTkLabel(frame, text=title)
        title_label.pack(pady=(0, 10))

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

    #TODO
    def add_round_corners(self, im, rad):
        circle = Image.new('L', (rad * 2, rad * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
        alpha = Image.new('L', im.size, 255)
        w,h = im.size
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        im.putalpha(alpha)
        return im
    
    def onFrameConfigure(self, event):
        '''Reset the scroll region to encompass the inner frame'''
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
