#app.py
import customtkinter
import os
from PIL import Image, ImageOps
from gui.homepage import HomePage
from gui.newyoutubeplaylist import NewYoutubePlaylist
from gui.playlistspage import PlaylistsPage
from core.central_manager import CentralManager

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.central_manager = CentralManager("playlists.json")

        self.title("YouSync")
        self.geometry("1100x650")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 1100
        window_height = 650
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        self.resizable(width=False, height=False)
        self.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.image_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets/images")
        self.logo_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(self.image_path, "YouSyncLogo_light.png")), 
                                                 dark_image=Image.open(os.path.join(self.image_path, "YouSyncLogo_dark.png")), size=(180, 65))
        self.home_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(self.image_path, "home_dark.png")), dark_image=Image.open(os.path.join(self.image_path, "home_light.png")), size=(20, 20))
        self.playlist_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(self.image_path, "chat_dark.png")),
                                                 dark_image=Image.open(os.path.join(self.image_path, "chat_light.png")), size=(20, 20))
        self.settings_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(self.image_path, "chat_dark.png")),
                                                     dark_image=Image.open(os.path.join(self.image_path, "chat_light.png")), size=(20, 20))

        self.navigation_frame = customtkinter.CTkFrame(self, corner_radius=0)
        self.navigation_frame.grid(row=0, column=0, sticky="nsew")
        self.navigation_frame.grid_rowconfigure(4, weight=1)

        self.navigation_frame_label = customtkinter.CTkLabel(self.navigation_frame, text="", image=self.logo_image,
                                                             compound="left", font=customtkinter.CTkFont(size=15, weight="bold"))
        self.navigation_frame_label.grid(row=0, column=0, padx=20, pady=20)

        self.home_button = customtkinter.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10, text="Home",
                                                   fg_color="transparent", text_color=("#282828", "#E5E4DE"), hover_color=("gray70", "gray30"),
                                                   image=self.home_image, anchor="w", command=self.home_button_event)
        self.home_button.grid(row=1, column=0, sticky="ew")

        self.frame_2_button = customtkinter.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10, text="Playlists",
                                                      fg_color="transparent", text_color=("#282828", "#E5E4DE"), hover_color=("gray70", "gray30"),
                                                      image=self.playlist_image, anchor="w", command=self.frame_2_button_event)
        self.frame_2_button.grid(row=2, column=0, sticky="ew")

        self.frame_3_button = customtkinter.CTkButton(self.navigation_frame, corner_radius=0, height=40, border_spacing=10, text="Settings",
                                                      fg_color="transparent", text_color=("#282828", "#E5E4DE"), hover_color=("gray70", "gray30"),
                                                      image=self.settings_image, anchor="w", command=self.frame_3_button_event)
        self.frame_3_button.grid(row=3, column=0, sticky="ew")

        # self.appearance_mode_menu = customtkinter.CTkOptionMenu(self.navigation_frame, values=["Dark", "Light", "System"],
                                                                # command=self.change_appearance_mode_event, fg_color=("gray70", "gray30"), button_color=("gray80", "gray40"), button_hover_color=("gray90", "gray50"), text_color=("#282828", "#E5E4DE"))
        # self.appearance_mode_menu.grid(row=6, column=0, padx=20, pady=20, sticky="s")

        self.home_page = HomePage(self, self.image_path, corner_radius=0, fg_color="transparent")
        self.playlists_page = PlaylistsPage(self, self.image_path, corner_radius=0, fg_color="transparent")
        self.playlist_page = None
        self.third_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.new_youtube_playlist_page = NewYoutubePlaylist(self, self.image_path, fg_color="transparent")

        self.home_page.grid(row=0, column=1, sticky="nsew")
        self.playlists_page.grid(row=0, column=1, sticky="nsew")
        self.third_frame.grid(row=0, column=1, sticky="nsew")
        self.new_youtube_playlist_page.grid(row=0, column=1, sticky="nsew")

        self.playlists_page.lower()
        self.third_frame.lower()
        self.new_youtube_playlist_page.lower()

        self.select_frame_by_name("playlists_page")

    def show_new_youtube_playlist(self):
        self.select_frame_by_name("new_youtube_playlist")

    def select_frame_by_name(self, name):
        self.home_button.configure(fg_color=("gray75", "gray25") if name == "home" else "transparent")
        self.frame_2_button.configure(fg_color=("gray75", "gray25") if name == "playlists_page" else "transparent")
        self.frame_3_button.configure(fg_color=("gray75", "gray25") if name == "frame_3" else "transparent")

        for frame in [self.home_page, self.playlists_page, self.third_frame, self.new_youtube_playlist_page]:
            frame.lower()
        if name == "home":
            self.home_page.lift()
        elif name == "playlists_page":
            self.playlists_page.lift()
        elif name == "frame_3":
            self.third_frame.lift()
        elif name == "new_youtube_playlist":
            self.new_youtube_playlist_page.lift()

    def home_button_event(self):
        self.select_frame_by_name("home")

    def frame_2_button_event(self):
        if not self.playlist_page:
            self.playlist_page = PlaylistsPage(self, self.image_path, corner_radius=0, fg_color="transparent")
            self.playlist_page.grid(row=0, column=1, sticky="nsew")
        self.select_frame_by_name("playlists_page")

    def frame_3_button_event(self):
        self.select_frame_by_name("frame_3")

    def change_appearance_mode_event(self, new_appearance_mode):
        customtkinter.set_appearance_mode(new_appearance_mode)
        self.playlists_page.update_image_mode()

    def go_back_home(self):
        self.home_page.lift()

    def go_back_playlists(self):
        self.playlists_page.lift()
