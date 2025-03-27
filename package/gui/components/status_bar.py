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
            text="done",
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
            EventType.STATUS_UPDATE, 
            self.on_status_update, 
            priority=EventPriority.NORMAL
        )

    def on_status_update(self, event):
        self.set_status_text(event.data.get('status_text', ''))