import tkinter as tk
from ..config import AppConfig


class NavigationBar(tk.Frame):
    def __init__(self, parent, page_factory):
        super().__init__(parent)
        self.buttons = {
            'Formula Generation': self._create_nav_button('分子式生成'),
            'Formula Search': self._create_nav_button('分子式检索')
        }

    def _create_nav_button(self, text):
        return tk.Button(self, text=text, **AppConfig.BUTTON_STYLE)