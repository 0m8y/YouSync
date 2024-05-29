import tkinter as tk
from PIL import Image, ImageTk, ImageOps
import os

class AnimatedSyncButton:
    def __init__(self, master, image_path, duration=5000):
        self.master = master
        self.image_path = image_path
        self.duration = duration
        self.angle = 0

        self.canvas = tk.Canvas(master, width=100, height=100, bg='grey', highlightthickness=0)
        self.canvas.pack()

        # Load the image
        self.original_image = Image.open(self.image_path)
        self.original_image = self.original_image.resize((50, 50), Image.ANTIALIAS)
        self.tk_image = ImageTk.PhotoImage(self.original_image)
        self.image_on_canvas = self.canvas.create_image(50, 50, image=self.tk_image)

        # Button to start the animation
        self.start_button = tk.Button(master, text="Sync", command=self.start_animation)
        self.start_button.pack()

    def start_animation(self):
        self.animate()

    def animate(self):
        if self.angle < 360:
            self.angle += 10
        else:
            self.angle = 0

        rotated_image = self.original_image.rotate(self.angle)
        self.tk_image = ImageTk.PhotoImage(rotated_image)
        self.canvas.itemconfig(self.image_on_canvas, image=self.tk_image)

        # Schedule the next rotation
        self.master.after(50, self.animate)