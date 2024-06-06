# progressbarnotification.py

import customtkinter
from tkinter import Toplevel
from gui.style import *

class ProgressBarNotification(Toplevel):
    def __init__(self, parent, total, text, **kwargs):
        super().__init__(parent.parent)
        print("OPEN PROGRESS BAR")
        self.parent = parent
        self.total = total
        self.current = 0
        self.text = text
        self.configure(bg="#333", padx=10, pady=5)
        self.geometry("+{}+{}".format(parent.parent.winfo_rootx() + 50, parent.parent.winfo_rooty() + 50))
        self.overrideredirect(True)

        self.label = customtkinter.CTkLabel(self, text=self.text, anchor="w", fg_color=BUTTON_COLOR, text_color=WHITE_TEXT_COLOR)
        self.label.pack(side="left", padx=10, pady=5, fill="x", expand=True)

        self.progress_bar = customtkinter.CTkProgressBar(self, progress_color=WHITE_TEXT_COLOR)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="right", padx=10, pady=5, fill="x", expand=True)

    def update_progress(self, current):
        print("UPDATE PROGRESS BAR")
        self.current = current
        progress = self.current / self.total
        self.progress_bar.set(progress)
        if self.current >= self.total:
            self.close_notification()

    def close_notification(self):
        print("CLOSE PROGRESS BAR")
        self.parent.close_notification(self)
