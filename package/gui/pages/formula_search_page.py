import tkinter as tk
from .base_page import BasePage


class FormulaSearchPage(BasePage):
    def __init__(self, parent, event_mgr):
        super().__init__(parent, event_mgr, title="Formula Search")
        label = tk.Label(self, text="这是Formula Search页面")
        label.pack(fill=tk.BOTH, expand=True)