import tkinter as tk

class BasePage(tk.Frame):
    def __init__(self, parent, event_bus, title=""):
        super().__init__(parent)  # 父容器是 left_frame
        self.event_bus = event_bus
        self.title = title
        # 构建页面内容...