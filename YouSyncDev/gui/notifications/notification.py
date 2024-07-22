import os
import customtkinter
from PIL import Image
from typing import Any
from tkinter import Toplevel

from gui.style import NOTIFICATION_DURATION, WHITE_TEXT_COLOR, BUTTON_COLOR, HOVER_COLOR


class Notification(Toplevel):
    def __init__(self, parent: Any, message: str, image_path: str, duration: int = NOTIFICATION_DURATION, text_color: str = WHITE_TEXT_COLOR, **kwargs: Any) -> None:
        super().__init__(parent.parent)
        self.parent = parent
        self.message = message
        self.duration = duration
        self.image_path = image_path

        self.configure(bg=BUTTON_COLOR, padx=10, pady=5)
        self.geometry("+{}+{}".format(parent.parent.winfo_rootx() + 50, parent.parent.winfo_rooty() + 50))
        self.overrideredirect(True)

        self.message_label = customtkinter.CTkLabel(self, text=self.message, anchor="w", text_color=text_color, fg_color=BUTTON_COLOR)
        self.message_label.pack(side="left", padx=10, pady=5, fill="x", expand=True)

        close_image = Image.open(os.path.join(self.image_path, "close.png"))
        self.close_icon = customtkinter.CTkImage(close_image, size=(15, 15))
        self.close_button = customtkinter.CTkButton(self, text="", image=self.close_icon, command=self.close_notification, width=15, height=15, fg_color="transparent", hover_color=HOVER_COLOR)
        self.close_button.pack(side="right", padx=5, pady=5)

        self.after(self.duration, self.close_notification)

    def close_notification(self) -> None:
        self.parent.close_notification(self)
