# progressbarnotification.py

import customtkinter
from tkinter import Toplevel

class ProgressBarNotification(Toplevel):
    def __init__(self, parent, total, **kwargs):
        super().__init__(parent.parent)
        print("OPEN PROGRESS BAR")
        self.parent = parent
        self.total = total
        self.current = 0

        self.configure(bg="#333", padx=10, pady=5)
        self.geometry("+{}+{}".format(parent.parent.winfo_rootx() + 50, parent.parent.winfo_rooty() + 50))
        self.overrideredirect(True)

        self.label = customtkinter.CTkLabel(self, text="Loading playlists...", anchor="w", fg_color="#333")
        self.label.pack(side="left", padx=10, pady=5, fill="x", expand=True)

        self.progress_bar = customtkinter.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="right", padx=10, pady=5, fill="x", expand=True)

    def update_progress(self, current):
        self.current = current
        progress = self.current / self.total
        self.progress_bar.set(progress)
        if self.current >= self.total:
            self.close_notification()

    def close_notification(self):
        self.parent.close_notification(self)
