import tkinter as tk

class BasePage(tk.Frame):
    def __init__(self, parent, event_bus, title=""):
        super().__init__(parent)
        self.title = title