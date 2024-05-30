import customtkinter
from PIL import Image, ImageTk
import os
from gui.utils import create_image

class PlaylistPage(customtkinter.CTkFrame):
    def __init__(self, parent, title, image_path, image_file, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.title = title
        self.image_path = image_path
        self.cover_pic = os.path.join(self.image_path, image_file)
        self.song_count = 26
        self.last_updated = "26 Avril 2024"
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Frame principale pour aligner le contenu à gauche
        main_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        # Configuration de la grille pour la disposition
        main_frame.grid_columnconfigure(0, minsize=180)
        main_frame.grid_columnconfigure(1, weight=1)

        # Image de la playlist
        photo = create_image(self.cover_pic, 180, 180)
        self.image_label = customtkinter.CTkLabel(main_frame, image=photo, text="")
        self.image_label.image = photo  # Garder une référence
        self.image_label.grid(row=0, column=0, rowspan=2, padx=(55, 20), sticky="ns")

        # Sous-frame pour les labels de texte
        text_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        text_frame.grid(row=0, column=1, sticky="ew")

        # Titre de la playlist
        self.title_label = customtkinter.CTkLabel(text_frame, text=self.title, font=("Roboto", 20, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w")

        # Détails supplémentaires
        details_label = f"{self.song_count} songs"
        self.details_label = customtkinter.CTkLabel(text_frame, text=details_label, justify=customtkinter.LEFT)
        self.details_label.grid(row=1, column=0, sticky="w")

        details_label2 = f"Last Update: {self.last_updated}"
        self.details_label2 = customtkinter.CTkLabel(text_frame, text=details_label2, justify=customtkinter.LEFT)
        self.details_label2.grid(row=2, column=0, sticky="w")

        self.add_song_list()

        # Back Button
        light_back_image = Image.open(os.path.join(self.image_path, "back_light.png"))
        dark_back_image = Image.open(os.path.join(self.image_path, "back_dark.png"))
        self.back_ctk_image = customtkinter.CTkImage(light_image=dark_back_image, dark_image=light_back_image)
        self.back_button = customtkinter.CTkButton(self, text="", command=self.parent.go_back_playlists, height=45, width=45, image=self.back_ctk_image, fg_color=("#bdbdbd", "#333333"), hover_color=("gray70", "gray30"))
        self.back_button.place(x=15, y=30)

    def add_song_list(self):
        song_list_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        song_list_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        for i in range(1, 27):
            bg_color = "#2E2E2E" if i % 2 == 0 else "transparent"
            song_frame = customtkinter.CTkFrame(song_list_frame, fg_color=bg_color, height=40)
            song_frame.grid_columnconfigure(0, weight=0)
            song_frame.grid_columnconfigure(1, weight=5)
            song_frame.pack(fill="x", pady=2, padx=10)
            
            track_number_label = customtkinter.CTkLabel(song_frame, text=f"{i}.", anchor="w", fg_color="transparent")
            track_number_label.grid(row=0, column=0, sticky="w", padx=(10, 5))

            song_title_label = customtkinter.CTkLabel(song_frame, text=f"Song Title {i}", anchor="w", fg_color="transparent")
            song_title_label.grid(row=0, column=1, sticky="w", padx=(5, 10))
