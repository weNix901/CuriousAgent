from typing import Callable


class EventBus:
    _subscribers: dict[str, list[Callable]] = {}

    @classmethod
    def subscribe(cls, event_type: str, handler: Callable):
        if event_type not in cls._subscribers:
            cls._subscribers[event_type] = []
        cls._subscribers[event_type].append(handler)

    @classmethod
    def emit(cls, event_type: str, payload: dict):
        for handler in cls._subscribers.get(event_type, []):
            try:
                handler(payload)
            except Exception as e:
                print(f"[EventBus] Handler error: {e}")

    @classmethod
    def unsubscribe(cls, event_type: str, handler: Callable):
        if event_type in cls._subscribers:
            if handler in cls._subscribers[event_type]:
                cls._subscribers[event_type].remove(handler)

    @classmethod
    def clear(cls, event_type: str = None):
        if event_type:
            cls._subscribers.pop(event_type, None)
        else:
            cls._subscribers.clear()

    @classmethod
    def list_subscribers(cls) -> dict:
        return {
            event_type: len(handlers)
            for event_type, handlers in cls._subscribers.items()
        }
