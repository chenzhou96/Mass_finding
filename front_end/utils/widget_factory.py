from ..config import AppConfig
import tkinter as tk

class WidgetFactory:
    def __init__(self):
        self.button_style = AppConfig.BUTTON_STYLE
        self.label_style = {
            'font': (AppConfig.DEFAULT_FONT, 10),
            'bg': AppConfig.PRIMARY_BG,
            'fg': AppConfig.COLOR_TEXT
        }

    def create_button(self, parent, text, command=None, is_disabled=False):
        """创建标准按钮"""
        style = self.button_style.copy()
        if is_disabled:
            style.update(AppConfig.DISABLED_BUTTON_STYLE)
            style['state'] = tk.DISABLED
        return tk.Button(parent, text=text, command=command, **style)

    def create_label(self, parent, text, **kwargs):
        """创建标准标签"""
        label_style = self.label_style.copy()
        label_style.update(kwargs)
        return tk.Label(parent, text=text, **label_style)

    def create_scrollable_text(self, parent):
        """创建带滚动条的文本框"""
        text_widget = tk.Text(
            parent,
            bg=AppConfig.COLOR_PRIMARY,
            fg=AppConfig.COLOR_TEXT,
            font=(AppConfig.DEFAULT_FONT, 10),
            wrap=tk.CHAR
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
            font=(AppConfig.DEFAULT_FONT, 10),
            bg=AppConfig.COLOR_PRIMARY,
            fg=AppConfig.COLOR_TEXT
        )