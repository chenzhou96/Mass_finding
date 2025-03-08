from ..config import AppConfig
import tkinter as tk

class WidgetFactory:
    def __init__(self):
        self.button_style = AppConfig.BaseElement.BUTTON
        self.label_style = AppConfig.BaseElement.TEXT

    def create_button(self, parent, text, command=None, **kwargs):
        """创建标准按钮"""
        button_style = self.button_style.copy()
        button_style.update(kwargs)
        return tk.Button(parent, text=text, command=command, **button_style)

    def create_label(self, parent, text, **kwargs):
        """创建标准标签"""
        label_style = self.label_style.copy()
        label_style.update(kwargs)
        return tk.Label(parent, text=text, **label_style)

    def create_scrollable_text(self, parent):
        """创建带滚动条的文本框"""
        text_widget = tk.Text(
            parent,
            wrap=tk.CHAR,
            **AppConfig.LogWindow.TEXT
        )
        scrollbar = tk.Scrollbar(parent, command=text_widget.yview)
        text_widget.config(yscrollcommand=scrollbar.set)
        return {
            "text": text_widget,
            "scrollbar": scrollbar
        }

    def create_status_label(self, parent, text):
        """创建状态栏标签"""
        return self.create_label(
            parent,
            text,
            **AppConfig.StatusBar.TEXT
        )