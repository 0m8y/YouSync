from gui.style import NOTIFICATION_DURATION, WHITE_TEXT_COLOR
from gui.notifications.notification import Notification
from gui.notifications.progressbarnotification import ProgressBarNotification


class NotificationManager:
    def __init__(self, parent, image_path):
        self.parent = parent
        self.app = self.parent.parent
        self.notifications = []
        self.image_path = image_path

        self.app.bind("<Configure>", self.on_parent_configure)

    def show_notification(self, message, duration=NOTIFICATION_DURATION, text_color=WHITE_TEXT_COLOR):
        notification = Notification(self, message, self.image_path, duration, text_color=text_color)
        self.notifications.append(notification)
        self.place_notifications()

    def place_notifications(self):
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
            self.place_notifications()

    def show_progress_bar_notification(self, total, text):
        progress_notification = ProgressBarNotification(self, total, text, fg_color="#333", corner_radius=10)
        self.notifications.append(progress_notification)
        self.place_notifications()
        return progress_notification

    def update_progress_bar_notification(self, notification, current):
        if notification in self.notifications:
            notification.update_progress(current)
        self.place_notifications()

    def on_parent_configure(self, event):
        self.place_notifications()
