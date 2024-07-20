from PIL import Image, ImageOps, ImageTk
import customtkinter
import os
from gui.style import WHITE_TEXT_COLOR, HOVER_COLOR, BUTTON_COLOR, NOTIFICATION_DURATION


class HomePage(customtkinter.CTkFrame):
    def __init__(self, parent, image_path, **kwargs):
        self.image_path = image_path
        self.parent = parent
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.create_label("Add new playlist")
        self.__create_youtube_button__()
        self.__create_spotify_button__()
        self.__create_apple_button__()
        self.__create_soundcloud_button__()

    def create_label(self, text):
        label = customtkinter.CTkLabel(self, text=text, text_color=WHITE_TEXT_COLOR, font=('Roboto Medium', 32))
        label.grid(row=0, column=0, columnspan=2, pady=(30, 0), sticky="ew")

    def __create_youtube_button__(self):
        youtube_image = Image.open(os.path.join(self.image_path, "Youtube_logo.png"))
        padded_image = ImageOps.expand(youtube_image, border=0, fill='black')
        resized_image = padded_image.resize((179, 75))
        tk_image = ImageTk.PhotoImage(resized_image)

        self.youtube_button = customtkinter.CTkButton(self, image=tk_image, width=300, height=120,
                                                      command=self.youtube_button_event, text="",
                                                      fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR)
        self.youtube_button.image = tk_image
        self.youtube_button.grid(row=1, column=0, padx=(50, 0), pady=(30, 0))

    def __create_spotify_button__(self):
        spotify_image = Image.open(os.path.join(self.image_path, "Spotify_logo.png"))
        padded_image = ImageOps.expand(spotify_image, border=0, fill='black')
        resized_image = padded_image.resize((216, 65))

        tk_image = ImageTk.PhotoImage(resized_image)

        self.spotify_button = customtkinter.CTkButton(self, image=tk_image, width=300, height=120,
                                                      command=self.spotify_button_event, text="",
                                                      fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR)
        self.spotify_button.image = tk_image
        self.spotify_button.grid(row=1, column=1, padx=(0, 50), pady=(30, 0))

    def __create_apple_button__(self):
        apple_image = Image.open(os.path.join(self.image_path, "Apple_logo.png"))
        padded_image = ImageOps.expand(apple_image, border=0, fill='black')
        resized_image = padded_image.resize((213, 51))

        tk_image = ImageTk.PhotoImage(resized_image)

        self.apple_button = customtkinter.CTkButton(self, image=tk_image, width=300, height=120,
                                                         command=self.apple_button_event, text="",
                                                         fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR)
        self.apple_button.image = tk_image
        self.apple_button.grid(row=2, column=0, padx=(50, 0), pady=(40, 0))

    def __create_soundcloud_button__(self):
        soundcloud_image = Image.open(os.path.join(self.image_path, "SoundCloud_logo.png"))
        padded_image = ImageOps.expand(soundcloud_image, border=0, fill='black')
        resized_image = padded_image.resize((160, 91))

        tk_image = ImageTk.PhotoImage(resized_image)

        self.soundcloud_button = customtkinter.CTkButton(self, image=tk_image, width=300, height=120,
                                                         command=self.soundcloud_button_event, text="",
                                                         fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR)
        self.soundcloud_button.image = tk_image
        self.soundcloud_button.grid(row=2, column=1, padx=(0, 50), pady=(40, 0))

    def soundcloud_button_event(self):
        self.parent.playlists_page.notification_manager.show_notification(
            "Soundcloud Comming soon...",
            duration=NOTIFICATION_DURATION,
            text_color=WHITE_TEXT_COLOR
        )

    def youtube_button_event(self):
        self.parent.show_new_youtube_playlist()

    def spotify_button_event(self):
        self.parent.show_new_spotify_playlist()

    def apple_button_event(self):
        self.parent.show_new_apple_playlist()