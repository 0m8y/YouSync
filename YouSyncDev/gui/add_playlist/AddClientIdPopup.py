from typing import Any
import customtkinter as ctk
import json

from core.CentralManager import CentralManager
from gui.style import WHITE_TEXT_COLOR, BUTTON_COLOR, HOVER_COLOR, NOTIFICATION_DURATION, RED_COLOR, GREEN_COLOR, RED_HOVER_COLOR, GREEN_HOVER_COLOR

class AddClientIdPopup(ctk.CTkToplevel):
    def __init__(self, parent, central_manager: CentralManager, *args: Any, **kwargs: Any) -> None:
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.central_manager = central_manager
        self.title("Enter SoundCloud Client ID")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        popup_width = 400
        popup_height = 380

        x_coordinate = (screen_width / 2) - (popup_width / 2)
        y_coordinate = (screen_height / 2) - (popup_height / 2)

        self.geometry(f"{popup_width}x{popup_height}+{int(x_coordinate)}+{int(y_coordinate)}")

        label = ctk.CTkLabel(self, text="Please enter your SoundCloud Client ID.", text_color=WHITE_TEXT_COLOR)
        label.pack(pady=10)

        explanation = ctk.CTkLabel(self, text="Steps to obtain soundlcoud client id:\n\n"
                                          "Step 1:\n       Connect to https://soundcloud.com.\n"
                                          "Step 2:\n       Press F12 to inspect elements.\n"
                                          "Step 3:\n       Go to Network section.\n"
                                          "Step 4:\n       Find a line containing client_id=...\n",
                               wraplength=300, justify="left", text_color=WHITE_TEXT_COLOR)
        explanation.pack(pady=10)

        self.entry = ctk.CTkEntry(self, width=300)
        self.entry.pack(pady=5)

        submit_button = ctk.CTkButton(self, text="Submit", command=self.submit_client_id, fg_color=BUTTON_COLOR, hover_color=HOVER_COLOR, text_color=WHITE_TEXT_COLOR)
        submit_button.pack(pady=10)

        self.wm_attributes("-topmost", 1)

    def submit_client_id(self) -> None:
        client_id: str = self.entry.get()
        if client_id:
            self.central_manager.encrypt_client_id(client_id)
            self.parent.notification_manager.show_notification("The client id has been added", text_color=("green"))
            self.destroy()  # Fermer la fenêtre popup
        else:
            self.parent.notification_manager.show_notification("Client ID cannot be empty!", text_color=("red"))
