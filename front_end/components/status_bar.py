import tkinter as tk
from ..config import AppConfig
from ..utils.widget_factory import WidgetFactory
from ..core.event import Event

class StatusBar(tk.Frame):
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, bg=AppConfig.COLOR_PRIMARY)
        self.event_bus = event_bus
        self.widget_factory = WidgetFactory()  # 创建 WidgetFactory 实例
        self.status_label = self.widget_factory.create_status_label(self, "就绪")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self._subscribe_events()

    def _subscribe_events(self):
        if self.event_bus:
            self.event_bus.subscribe('PAGE_SWITCH', self.on_page_switch)
        else:
            raise ValueError("event_bus 未正确传入")

    def on_page_switch(self, event):
        """更新状态栏文本"""
        if 'new_page' in event.data:
            new_page_name = event.data['new_page']
            self.status_label.config(text=f"当前页面: {new_page_name}")