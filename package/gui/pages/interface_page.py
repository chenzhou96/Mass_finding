from .base_page import BasePage
import tkinter as tk
from ...config.AppUI_config import AppUIConfig

class InterfacePage(BasePage):
    def __init__(self, parent, event_mgr):
        super().__init__(parent, event_mgr, title="预留接口")
        tk.Label(
            self,
            text="功能暂未开放",
        ).pack(expand=True)