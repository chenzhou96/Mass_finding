import tkinter as tk
from .base_page import BasePage


class FormulaGenerationPage(BasePage):
    def __init__(self, parent, event_bus):
        super().__init__(parent, event_bus, title="Formula Generation")
        label = tk.Label(self, text="这是Formula Generation页面")
        label.pack(fill=tk.BOTH, expand=True)