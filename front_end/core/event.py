from collections import defaultdict
from threading import Lock


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