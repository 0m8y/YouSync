import queue
from typing import Any
from gui.notifications.notification import Notification
from gui.style import NOTIFICATION_DURATION, WHITE_TEXT_COLOR

from gui.notifications.progressbarnotification import ProgressBarNotification


class NotificationManager:
    def __init__(self, parent: Any, image_path: str) -> None:
        self.parent = parent
        self.app = self.parent.parent
        self.notifications = []
        self.image_path = image_path

        self.queue = queue.Queue()
        self.app.bind("<Configure>", self.on_parent_configure)
        self.check_queue()

    def show_notification(self, message: str, duration: int = NOTIFICATION_DURATION, text_color: str = WHITE_TEXT_COLOR) -> None:
        self.queue.put(("show_notification", message, duration, text_color))

    def handle_show_notification(self, message: str, duration: int, text_color: str) -> None:
        notification = Notification(self, message, self.image_path, duration, text_color=text_color)
        self.notifications.append(notification)
        self.place_notifications()

    def check_queue(self) -> None:
        while not self.queue.empty():
            task = self.queue.get()
            if task[0] == "show_notification":
                self.handle_show_notification(*task[1:])
        self.app.after(100, self.check_queue)

    def place_notifications(self) -> None:
        for i, notification in enumerate(self.notifications):
            notification.update_idletasks()
            parent_width = self.parent.winfo_width()
            notification_width = notification.winfo_width()
            x = self.parent.winfo_rootx() + (parent_width - notification_width) // 2
            y = self.parent.winfo_rooty() + self.parent.winfo_height() - (i + 1) * (notification.winfo_height() + 10) - 50
            notification.geometry("+{}+{}".format(x, y))
            notification.deiconify()

    def close_notification(self, notification: Notification) -> None:
        if notification in self.notifications:
            self.notifications.remove(notification)
            notification.withdraw()
            self.place_notifications()

    def show_progress_bar_notification(self, total: int, text: str) -> ProgressBarNotification:
        progress_notification = ProgressBarNotification(self, total, text, fg_color="#333", corner_radius=10)
        self.notifications.append(progress_notification)
        self.place_notifications()
        return progress_notification

    def update_progress_bar_notification(self, notification: ProgressBarNotification, current: int) -> None:
        if notification in self.notifications:
            notification.update_progress(current)
        self.place_notifications()

    def on_parent_configure(self, event: Any) -> None:
        self.place_notifications()
