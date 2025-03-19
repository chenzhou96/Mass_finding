import logging
import tkinter as tk
import datetime
import os
from ..config.AppUI_config import AppUIConfig
from ..core.event import Event, EventPriority, EventType
from ..config.path_config import PathManager

class Logger:
    def __init__(self, event_bus, text_widget=None):
        self.text_widget = text_widget
        self.event_bus = event_bus
        self._configure_logging()  # 配置文件处理器

        # 订阅日志事件
        self.event_bus.subscribe(
            EventType.LOG_MESSAGE.value,
            self.log_to_ui,
            priority=EventPriority.NORMAL.value
        )

    def _configure_logging(self):
        """仅配置文件处理器"""
        # 1. 创建文件处理器
        timestamp = datetime.datetime.now().strftime("%Y%m%d")
        path_manager = PathManager()
        path_manager.get_mass_finding_cache_path()
        logfile_path = os.path.join(path_manager.get_logger_cache_path(), f"{timestamp}_app.log")
        file_handler = logging.FileHandler(
            filename=str(logfile_path),
            mode='a',
            encoding='utf-8',
            delay=False
        )
        file_formatter = logging.Formatter(
            AppUIConfig.InteractiveZone.LoggerZone.LOG_FORMAT,
            datefmt=AppUIConfig.InteractiveZone.LoggerZone.DATE_FORMAT
        )
        file_handler.setFormatter(file_formatter)

        # 2. 配置 root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers = []
        root_logger.addHandler(file_handler)

    def log_to_ui(self, event):
        if self.text_widget and event.data:
            self.text_widget.after(0, lambda msg=event.data: self._append_log(msg))

    def _append_log(self, message):
        """在 Text 组件追加日志"""
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, f"{message}\n")
        self.text_widget.see(tk.END)
        self.text_widget.config(state=tk.DISABLED)

    def info(self, message):
        """通过事件总线发布日志消息"""
        logging.getLogger().info(message)
        formatted_message = f"[INFO] {message}"
        self.event_bus.publish(
            Event(
                EventType.LOG_MESSAGE.value,
                data=formatted_message,
                priority=EventPriority.NORMAL.value
            )
        )

    def debug(self, message):
        logging.getLogger().debug(message)
        formatted_message = f"[DEBUG] {message}"
        self.event_bus.publish(
            Event(
                EventType.LOG_MESSAGE.value,
                data=formatted_message,
                priority=EventPriority.LOW.value
            )
        )

    def warning(self, message):
        logging.getLogger().warning(message)
        formatted_message = f"[WARNING] {message}"
        self.event_bus.publish(
            Event(
                EventType.LOG_MESSAGE.value,
                data=formatted_message,
                priority=EventPriority.HIGH.value
            )
        )

    def error(self, message):
        logging.getLogger().error(message)
        formatted_message = f"[ERROR] {message}"
        self.event_bus.publish(
            Event(
                EventType.LOG_MESSAGE.value,
                data=formatted_message,
                priority=EventPriority.CRITICAL.value
            )
        )

class EventLogHandler(logging.Handler):
    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus

    def emit(self, record):
        log_message = self.format(record)
        # 将日志消息发布到事件总线
        self.event_bus.publish(
            EventType.LOG_MESSAGE,
            data=log_message,
            priority=EventPriority.NORMAL
        )