import tkinter as tk
from ..config import AppConfig
from ..core.event import Event  # 确保导入Event类（可能需要路径调整）

class StatusBar(tk.Frame):
    def __init__(self, parent, event_bus=None):
        super().__init__(parent, bg=AppConfig.COLOR_PRIMARY)
        self.event_bus = event_bus  # 直接存储传入的 event_bus
        self.status_label = tk.Label(
            self,
            text="就绪",
            bg=AppConfig.COLOR_PRIMARY,
            fg=AppConfig.COLOR_TEXT,
            font=('微软雅黑', 10)
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self._subscribe_events()

    def _subscribe_events(self):
        # 直接使用传入的 event_bus
        if self.event_bus:
            self.event_bus.subscribe('PAGE_SWITCH', self.on_page_switch)
        else:
            raise ValueError("event_bus 未正确传入")

    def on_page_switch(self, event):
        """更新状态栏文本"""
        if 'new_page' in event.data:
            new_page_name = event.data['new_page']
            self.status_label.config(
                text=f"当前页面: {new_page_name}"
            )