import logging
import tkinter as tk
from ..config import AppConfig
from ..core.event import EventLogHandler
from ..utils.widget_factory import WidgetFactory

class Logger:
    def __init__(self, event_bus, text_widget=None):
        self.text_widget = text_widget
        self.event_bus = event_bus
        self.widget_factory = WidgetFactory()  # 创建 WidgetFactory 实例
        self._configure_logging()

        # 订阅日志事件
        self.event_bus.subscribe('LOG_MESSAGE', self.log_to_ui)

    def _configure_logging(self):
        # 创建事件总线处理器
        event_handler = EventLogHandler(self.event_bus)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(
            filename='app.log',
            mode='a',
            encoding='utf-8',
            delay=False
        )
        file_handler.setFormatter(logging.Formatter(AppConfig.LogWindow.LOG_FORMAT))

        # 配置 root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)  # 设置全局日志级别

        root_logger.handlers = []
        
        # 添加所有处理器
        root_logger.addHandler(event_handler)
        root_logger.addHandler(file_handler)

    def log_to_ui(self, event):
        """在主线程安全地更新日志Text组件"""
        if self.text_widget and event.data:
            self.text_widget.after(0, lambda msg=event.data: self._append_log(msg))

    def _append_log(self, message):
        self.text_widget.insert(tk.END, f"{message}\n")
        self.text_widget.see(tk.END)  # 自动滚动到底部