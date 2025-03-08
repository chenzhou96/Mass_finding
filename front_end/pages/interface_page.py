from .base_page import BasePage
import tkinter as tk
from ..config import AppConfig

class InterfacePage(BasePage):
    def __init__(self, parent, event_bus):
        super().__init__(parent, event_bus, title="预留接口")
        tk.Label(
            self,
            text="功能暂未开放",
            **AppConfig.BaseElement.TEXT,
        ).pack(expand=True)