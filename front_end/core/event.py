from collections import defaultdict
from threading import Lock
import logging

class Event:
    def __init__(self, event_type, data=None):
        self.event_type = event_type
        self.data = data


class EventBus:
    def __init__(self):
        self._listeners = defaultdict(list)
        self._lock = Lock()

    def subscribe(self, event_type, callback):
        self._listeners[event_type].append(callback)

    def publish(self, event):
        with self._lock:
            for listener in self._listeners[event.event_type]:
                listener(event)

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
            Event('LOG_MESSAGE', data=log_entry)
        )