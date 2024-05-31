import customtkinter
from PIL import Image
import os
from tkinter import Toplevel

class Notification(Toplevel):
    def __init__(self, parent, message, duration=5000, text_color="white", **kwargs):
        super().__init__(parent.parent)
        self.parent = parent
        self.message = message
        self.duration = duration
        
        self.configure(bg="#333", padx=10, pady=5)
        self.geometry("+{}+{}".format(parent.parent.winfo_rootx() + 50, parent.parent.winfo_rooty() + 50))
        self.overrideredirect(True)
        
        self.message_label = customtkinter.CTkLabel(self, text=self.message, anchor="w", text_color=text_color, fg_color="#333")
        self.message_label.pack(side="left", padx=10, pady=5, fill="x", expand=True)

        self.image_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets/images")
        close_image = Image.open(os.path.join(self.image_path, "close.png"))
        self.close_icon = customtkinter.CTkImage(close_image, size=(15, 15))
        self.close_button = customtkinter.CTkButton(self, text="", image=self.close_icon, command=self.close_notification, width=15, height=15, fg_color="transparent")
        self.close_button.pack(side="right", padx=5, pady=5)

        self.after(self.duration, self.close_notification)

    def close_notification(self):
        self.parent.close_notification(self)

class NotificationManager:
    def __init__(self, parent):
        self.parent = parent
        self.notifications = []

    def show_notification(self, message, duration=5000, text_color="white"):
        notification = Notification(self, message, duration, text_color=text_color)
        self.notifications.append(notification)
        self.place_notification()
        
    def place_notification(self):
        for i, n in enumerate(self.notifications):
            n.update_idletasks()
            parent_width = self.parent.winfo_width()
            notification_width = n.winfo_width()
            x = self.parent.winfo_rootx() + (parent_width - notification_width) // 2
            y = self.parent.winfo_rooty() + self.parent.winfo_height() - (i + 1) * (n.winfo_height() + 10) - 50
            n.geometry("+{}+{}".format(x, y))
            n.deiconify()

    def close_notification(self, notification):
        if notification in self.notifications:
            self.notifications.remove(notification)
            notification.withdraw()
            self.reorder_notifications()

    def reorder_notifications(self):
        for i, n in enumerate(self.notifications):
            parent_width = self.parent.winfo_width()
            notification_width = n.winfo_width()
            x = self.parent.winfo_rootx() + (parent_width - notification_width) // 2
            y = self.parent.winfo_rooty() + self.parent.winfo_height() - (i + 1) * (n.winfo_height() + 10) - 50
            n.geometry("+{}+{}".format(x, y))
            n.deiconify()

