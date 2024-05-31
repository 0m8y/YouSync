import customtkinter
from PIL import Image
import os
from tkinter import Toplevel
from gui.style import *
from gui.notifications.notification import Notification
from gui.notifications.progressbarnotification import ProgressBarNotification

class NotificationManager:
    def __init__(self, parent, image_path):
        self.parent = parent
        self.notifications = []
        self.image_path = image_path
        self.progress_notification = None

    def show_notification(self, message, duration=NOTIFICATION_DURATION, text_color=WHITE_TEXT_COLOR):
        notification = Notification(self, message, self.image_path, duration, text_color=text_color)
        self.notifications.append(notification)
        self.place_notification()
        
    def place_notification(self):
        for i, notification in enumerate(self.notifications):
            notification.update_idletasks()
            parent_width = self.parent.winfo_width()
            notification_width = notification.winfo_width()
            x = self.parent.winfo_rootx() + (parent_width - notification_width) // 2
            y = self.parent.winfo_rooty() + self.parent.winfo_height() - (i + 1) * (notification.winfo_height() + 10) - 50
            notification.geometry("+{}+{}".format(x, y))
            notification.deiconify()

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

    def show_progress_bar_notification(self, total):
        self.progress_notification = ProgressBarNotification(self, total, fg_color="#333", corner_radius=10)
        self.notifications.append(self.progress_notification)
        self.place_notification()

    def update_progress_bar_notification(self, current):
        if hasattr(self, 'progress_notification'):
            self.progress_notification.update_progress(current)

