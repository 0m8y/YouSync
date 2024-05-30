import customtkinter
from tkinter import filedialog
from PIL import Image, ImageTk, ImageOps
import os
import re

class NewYoutubePlaylist(customtkinter.CTkFrame):
    def __init__(self, parent, image_path, **kwargs):
        self.image_path = image_path
        self.parent_app = parent
        super().__init__(parent, **kwargs)
        self.setup_ui()

    def create_label(self, text, row):
        label = customtkinter.CTkLabel(self, text=text, text_color=("#282828", "#E5E4DE"), font=('Roboto Medium', 25))
        label.grid(row=row, column=1, columnspan=2, pady=(30, 0), sticky="w")

    def go_back(self):
        self.parent_app.go_back_home()


    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)

        # Back Button
        light_back_image = Image.open(os.path.join(self.image_path, "back_light.png"))
        self.back_ctk_image = customtkinter.CTkImage(light_image=light_back_image, dark_image=light_back_image)
        self.back_button = customtkinter.CTkButton(self, text="", command=self.go_back, height=45, width=45, image=self.back_ctk_image, fg_color=("#bdbdbd", "#333333"), hover_color=("gray70", "gray30"))
        self.back_button.place(x=30, y=30)

        # Logo YouTube
        youtube_logo = Image.open(os.path.join(self.image_path, "Youtube_logo.png"))
        padded_image = ImageOps.expand(youtube_logo, border=0, fill='black')
        resized_image = padded_image.resize((179, 75))
        tk_logo = ImageTk.PhotoImage(resized_image)
        self.logo_label = customtkinter.CTkLabel(self, image=tk_logo, text="")
        self.logo_label.image = tk_logo
        self.logo_label.grid(row=0, column=1, pady=(30, 40))

        # Youtube URL Section
        self.create_label("Enter Playlist URL", 1)
        self.url_entry = customtkinter.CTkEntry(self, placeholder_text="Playlist URL", width=600, height=45, border_width=0, fg_color=("#bdbdbd", "#333333"))
        self.url_entry.grid(row=2, column=1, padx=(0, 0), pady=10, sticky="ew")

        # Path Section
        self.create_label("Search path to save playlist", 3)
        self.path_entry = customtkinter.CTkEntry(self, placeholder_text="Path to save", width=600, height=45, border_width=0, fg_color=("#bdbdbd", "#333333"))
        self.path_entry.configure(state="disabled")
        self.path_entry.grid(row=4, column=1, padx=(0, 0), pady=10, sticky="ew")

        # Folder Button
        light_photo_image = Image.open(os.path.join(self.image_path, "folder.png"))
        self.folder_ctk_image = customtkinter.CTkImage(light_image=light_photo_image, dark_image=light_photo_image)
        self.browse_button = customtkinter.CTkButton(self, text="", command=self.browse_file, width=45, height=45, image=self.folder_ctk_image, fg_color=("#bdbdbd", "#333333"), hover_color=("gray70", "gray30"), corner_radius=0)
        self.browse_button.grid(row=4, column=1, sticky="e")

        # Save Button
        self.save_button = customtkinter.CTkButton(self, text="Save", command=self.save, width=120, height=45,
                                                    fg_color=("#bdbdbd", "#333333"), hover_color=("gray70", "gray30"), text_color=("#282828", "#E5E4DE"))
        self.save_button.grid(row=5, column=1, padx=(0, 0), pady=40)

        # Notification Section
        self.notification_label = customtkinter.CTkLabel(self, text="", text_color=("#FF0000", "#FFFFFF"))
        self.notification_label.grid(row=6, column=1, sticky="ew")

    def browse_file(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, customtkinter.END)
            self.path_entry.insert(0, folder_selected)
            self.path_entry.configure(state="disabled")

    def save(self):
        url = self.url_entry.get()
        path = self.path_entry.get()
        if not self.validate_youtube_url(url):
            self.notification_label.configure(text="Please enter a valid YouTube URL.", text_color=("red"))
        elif not self.validate_path(path):
            self.notification_label.configure(text="Please enter a valid path.", text_color=("red"))
        else:
            self.notification_label.configure(text="The YouTube URL is valid.", text_color=("green"))

    def validate_youtube_url(self, url):
        youtube_regex = (
            r'^https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|playlist\?list=)|youtu\.be/)([\w\-]+)(?:&[\w\-]+)*$'
        )
        return re.match(youtube_regex, url) is not None
    
    def validate_path(self, path):
        if not os.path.exists(path):
            return False

        if not os.path.isdir(path):
            return False

        return True

