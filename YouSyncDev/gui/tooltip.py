from tkinter import Toplevel, Label, Widget, Event
from gui.style import WHITE_TEXT_COLOR, BUTTON_COLOR


class ToolTip:
    def __init__(self, widget: Widget, text: str) -> None:
        self.widget: Widget = widget
        self.text: str = text
        self.tipwindow: Toplevel | None = None
        self.id: int | None = None
        self.x:int = 0
        self.y:int = 0
        self.widget.bind("<Enter>", self.schedule_show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def schedule_show_tip(self, event: Event | None = None) -> None:
        self.unschedule()
        self.id = self.widget.after(600, self.show_tip)

    def unschedule(self) -> None:
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def show_tip(self, event: Event | None = None) -> None:
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tipwindow = Toplevel(self.widget)
        self.tipwindow.wm_overrideredirect(True)
        self.tipwindow.wm_geometry(f"+{x}+{y}")
        label = Label(self.tipwindow, text=self.text, background=BUTTON_COLOR, relief="solid", borderwidth=1, fg=WHITE_TEXT_COLOR)
        label.pack()

    def hide_tip(self, event: Event | None = None) -> None:
        self.unschedule()
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None
