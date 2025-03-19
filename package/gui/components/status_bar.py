import tkinter as tk
from ...config.AppUI_config import AppUIConfig
from ...config.event_config import EventType, EventPriority

class StatusBar(tk.Frame):
    def __init__(self, frame, widget_factory, event_mgr):
        super().__init__(frame, **AppUIConfig.StatusBar.frame)
        if not event_mgr:
            raise ValueError("必须传入有效的Event Manager实例")
        self.event_mgr = event_mgr
        self.status_label = widget_factory.create_label(
            self,
            text="初始化中···",
            **AppUIConfig.StatusBar.label
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        self._subscribe_events()
        
    def set_status_text(self, new_text: str):
        """更新状态栏显示文本"""
        if not isinstance(new_text, str):
            raise TypeError("文本内容必须为字符串类型")
        self.status_label.config(text=new_text)

    def _subscribe_events(self):
        self.event_mgr.subscribe(
            EventType.PAGE_SWITCH,
            self.on_page_switch,
            priority=EventPriority.NORMAL
        )

    def on_page_switch(self, event):
        new_page_name = event.data.get('new_page', '未知页面')
        self.set_status_text(f"当前页面: {new_page_name}")