import customtkinter
from PIL import Image
import os
from tkinter import Toplevel
from gui.style import *

class Notification(Toplevel):
    def __init__(self, parent, message, image_path, duration=NOTIFICATION_DURATION, text_color=WHITE_TEXT_COLOR, **kwargs):
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

    def close_notification(self):
        self.parent.close_notification(self)