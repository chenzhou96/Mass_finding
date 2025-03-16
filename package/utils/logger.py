import logging
import tkinter as tk
from ..config.config_temp import AppConfig
from ..core.event import EventLogHandler
from ..utils.widget_factory import WidgetFactory

class Logger:
    def __init__(self, event_bus, text_widget=None):
        self.text_widget = text_widget
        self.event_bus = event_bus
        self._configure_logging()  # 配置日志处理器
        self.event_bus.subscribe(AppConfig.EventName.log_message, self.log_to_ui)

    def _configure_logging(self):
        """配置日志处理器（事件总线和文件）"""
        # 1. 创建事件总线处理器
        event_handler = EventLogHandler(self.event_bus)
        event_handler.setFormatter(
            logging.Formatter(AppConfig.InteractiveZone.LoggerZone.LOG_FORMAT, datefmt=AppConfig.InteractiveZone.LoggerZone.DATE_FORMAT)
        )
        
        # 2. 创建文件处理器
        file_handler = logging.FileHandler(
            filename='app.log',
            mode='a',
            encoding='utf-8',
            delay=False
        )
        file_handler.setFormatter(
            logging.Formatter(AppConfig.InteractiveZone.LoggerZone.LOG_FORMAT, datefmt=AppConfig.InteractiveZone.LoggerZone.DATE_FORMAT)
        )

        # 3. 配置 root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)  # 全局日志级别
        
        # 清除默认处理器并添加新处理器
        root_logger.handlers = []
        root_logger.addHandler(event_handler)
        root_logger.addHandler(file_handler)

    def log_to_ui(self, event):
        """安全更新 UI 日志组件（在主线程执行）"""
        if self.text_widget and event.data:
            self.text_widget.after(0, lambda msg=event.data: self._append_log(msg))

    def _append_log(self, message):
        """在 Text 组件追加日志"""
        self.text_widget.config(state=tk.NORMAL)  # 必要时启用编辑
        self.text_widget.insert(tk.END, f"{message}\n")
        self.text_widget.see(tk.END)  # 自动滚动到底部
        self.text_widget.config(state=tk.DISABLED)  # 恢复只读状态

    def info(self, message):
        """记录 INFO 级别日志"""
        logging.getLogger().info(message)

    def debug(self, message):
        """记录 DEBUG 级别日志"""
        logging.getLogger().debug(message)

    def error(self, message):
        """记录 ERROR 级别日志"""
        logging.getLogger().error(message)