from collections import defaultdict
from threading import Lock
import logging
from ..config.AppUI_config import AppUIConfig
from ..config.event_config import EventType, EventPriority

class Event:
    def __init__(self, event_type, data=None, priority=EventPriority.LOW):
        self.event_type = event_type
        self.data = data
        self.priority = priority

class EventListener:
    def __init__(self, callback, priority=EventPriority.LOW, filter_func=None):
        self.callback = callback
        self.priority = priority
        self.filter = filter_func  # 过滤条件函数

class EventBus:
    def __init__(self):
        self._listeners = defaultdict(list)  # 存储 Listener 对象
        self._lock = Lock()

    def subscribe(
        self,
        event_type,
        callback,
        priority=EventPriority.LOW,
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
                    print(f"事件 {event.event_type} 处理失败: {e}")  # 简化错误处理

class EventManager:
    def __init__(self):
        self.bus = EventBus()

    def subscribe(self, event_type, callback, priority=EventPriority.NORMAL):
        """外部订阅事件的接口"""
        self.bus.subscribe(
            event_type.value,
            callback,
            priority=priority.value
        )

    def publish(self, event_type, data=None, priority=EventPriority.NORMAL):
        """外部发布事件的接口"""
        event = Event(
            event_type.value,
            data,
            priority=priority.value
        )
        self.bus.publish(event)