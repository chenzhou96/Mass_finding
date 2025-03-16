from collections import defaultdict
from threading import Lock
import logging
from ..config.config_temp import AppConfig

class Event:
    def __init__(self, event_type, data=None, priority=AppConfig.EventPriority.low):
        self.event_type = event_type
        self.data = data
        self.priority = priority


class EventListener:
    def __init__(self, callback, priority=AppConfig.EventPriority.low, filter_func=None):
        self.callback = callback
        self.priority = priority
        self.filter = filter_func  # 过滤条件函数

class EventBus:
    def __init__(self, logger):
        self._listeners = defaultdict(list)  # 存储 Listener 对象
        self._lock = Lock()
        self.logger = logger

    def subscribe(
        self,
        event_type,
        callback,
        priority=AppConfig.EventPriority.low,
        filter_func=None
    ):
        listener = EventListener(callback, priority, filter_func)
        self._listeners[event_type].append(listener)

    def publish(self, event):
        with self._lock:
            listeners = self._listeners.get(event.event_type, [])
            # 按优先级排序（高优先级优先）
            listeners.sort(key=lambda l: l.priority, reverse=True)
            for listener in listeners:
                # 过滤条件检查
                if listener.filter and not listener.filter(event):
                    continue
                try:
                    listener.callback(event)
                except Exception as e:
                    self.logger.error(f"事件 {event.event_type} 处理失败: {e}")

class EventRegistry:
    def __init__(self, event_bus):
        self.event_bus = event_bus

class EventLogHandler(logging.Handler):
    def __init__(self, event_bus):
        super().__init__()
        self.event_bus = event_bus

    def emit(self, record):
        log_entry = self.format(record)
        # 将日志消息发布到事件总线
        self.event_bus.publish(
            Event(AppConfig.EventName.log_message, data=log_entry)
        )