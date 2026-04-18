import logging
import tkinter as tk
import datetime
import os
from queue import Empty, Queue
from ..config.AppUI_config import AppUIConfig
from ..core.event import Event, EventPriority, EventType
from ..config.path_config import PathManager

class Logger:
    def __init__(self, event_bus, text_widget=None):
        self.text_widget = text_widget
        self.event_bus = event_bus
        self._pending_messages = Queue()
        self._ui_poll_interval_ms = 80
        self._ui_poll_job = None
        self._configure_logging()  # 配置文件处理器

        # 订阅日志事件
        self.event_bus.subscribe(
            EventType.LOG_MESSAGE.value,
            self.log_to_ui,
            priority=EventPriority.NORMAL.value
        )

        if self.text_widget:
            self.set_text_widget(self.text_widget)

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

    def set_text_widget(self, text_widget):
        self.text_widget = text_widget
        self._configure_text_tags()
        self.text_widget.config(state=tk.DISABLED)
        self._ensure_ui_polling()

    def _configure_text_tags(self):
        if not self.text_widget:
            return

        for tag_name, style in AppUIConfig.InteractiveZone.LoggerZone.TAG_STYLES.items():
            self.text_widget.tag_configure(tag_name, **style)

    def _ensure_ui_polling(self):
        if not self.text_widget or self._ui_poll_job is not None:
            return
        try:
            self._ui_poll_job = self.text_widget.after(self._ui_poll_interval_ms, self._drain_pending_logs)
        except Exception:
            self._ui_poll_job = None

    def _drain_pending_logs(self):
        self._ui_poll_job = None
        if not self.text_widget:
            return

        try:
            if hasattr(self.text_widget, 'winfo_exists') and not self.text_widget.winfo_exists():
                return
        except Exception:
            return

        while True:
            try:
                payload = self._pending_messages.get_nowait()
            except Empty:
                break

            try:
                self._append_log(payload)
            except Exception:
                continue

        self._ensure_ui_polling()

    def log_to_ui(self, event):
        if event and event.data:
            self._pending_messages.put(event.data)

    def _normalize_message(self, payload):
        if isinstance(payload, dict):
            level = str(payload.get('level', 'DEFAULT')).upper()
            message = str(payload.get('message', ''))
            return level, message

        return 'DEFAULT', str(payload)

    def _append_log(self, payload):
        """在 Text 组件追加日志"""
        if not self.text_widget:
            return

        level, message = self._normalize_message(payload)
        tag_name = level if level in AppUIConfig.InteractiveZone.LoggerZone.TAG_STYLES else 'DEFAULT'
        formatted_message = f"{message.rstrip()}\n"

        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, formatted_message, (tag_name,))
        self.text_widget.see(tk.END)
        self.text_widget.config(state=tk.DISABLED)

    def info(self, message):
        """通过事件总线发布日志消息"""
        logging.getLogger().info(message)

    def debug(self, message):
        logging.getLogger().debug(message)

    def warning(self, message):
        logging.getLogger().warning(message)

    def error(self, message):
        logging.getLogger().error(message)

class EventLogHandler(logging.Handler):
    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus
        self.setFormatter(
            logging.Formatter(
                AppUIConfig.InteractiveZone.LoggerZone.LOG_FORMAT,
                datefmt=AppUIConfig.InteractiveZone.LoggerZone.DATE_FORMAT
            )
        )

    @staticmethod
    def _map_priority(levelno):
        if levelno >= logging.ERROR:
            return EventPriority.CRITICAL
        if levelno >= logging.WARNING:
            return EventPriority.HIGH
        if levelno >= logging.INFO:
            return EventPriority.NORMAL
        return EventPriority.LOW

    def emit(self, record):
        log_message = self.format(record)
        # 将日志消息发布到事件总线
        self.event_bus.publish(
            EventType.LOG_MESSAGE,
            data={
                'level': record.levelname,
                'message': log_message,
            },
            priority=self._map_priority(record.levelno)
        )