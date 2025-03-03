import tkinter as tk
from .base_page import BasePage


class FormulaGenerationPage(BasePage):
    def __init__(self, parent, event_bus):
        super().__init__(parent, event_bus, title="Formula Generation")