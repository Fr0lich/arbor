import threading
from typing import Optional, Dict, Any, Callable, List

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_type: str, callback: Callable):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        with self._lock:
            if event_type in self._subscribers:
                if callback in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(callback)

    def publish(self, event_type: str, *args, **kwargs):
        with self._lock:
            callbacks = self._subscribers.get(event_type, []).copy()

        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"Error in event {event_type} handler: {e}")

# Global Event Bus instance
app_bus = EventBus()
