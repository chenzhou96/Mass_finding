# blank_page.py
import tkinter as tk
from .base_page import BasePage


class BlankPage(BasePage):
    def __init__(self, parent, event_mgr, logger):
        super().__init__(parent, event_mgr, logger, title="Blank Page")
        label = tk.Label(self, text="这是 Blank 页面")
        label.pack(fill=tk.BOTH, expand=True)