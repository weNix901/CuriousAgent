import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

# v0.2.5 root tracing events
EVENT_ROOT_CANDIDATE_ELEVATED = "root_candidate_elevated"


@dataclass
class Event:
    type: str
    data: dict
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        return cls(
            type=data["type"],
            data=data["data"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", ""),
        )


class PersistentEventBus:
    def __init__(self, storage_path: Optional[str] = None):
        self._subscribers: dict[str, list[Callable[[Event], None]]] = {}
        self._storage_path = storage_path
        self._connected = False
        
        if storage_path:
            self.enable_persistence(storage_path)
    
    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def publish(self, event: Event) -> None:
        if self._storage_path:
            self._persist_event(event)
        
        for handler in self._subscribers.get(event.type, []):
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus] Handler error: {e}")
    
    def enable_persistence(self, path: str) -> None:
        self._storage_path = path
        self._connected = True
        os.makedirs(os.path.dirname(path), exist_ok=True)
    
    def is_connected(self) -> bool:
        return self._connected
    
    def _persist_event(self, event: Event) -> None:
        with open(self._storage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
    
    def replay_history(self, event_type: Optional[str] = None) -> None:
        if not self._storage_path or not os.path.exists(self._storage_path):
            return
        
        with open(self._storage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    event = Event.from_dict(data)
                    
                    if event_type is None or event.type == event_type:
                        for handler in self._subscribers.get(event.type, []):
                            try:
                                handler(event)
                            except Exception as e:
                                print(f"[EventBus] Replay handler error: {e}")
                except json.JSONDecodeError:
                    continue
    
    def get_events_by_type(self, event_type: str) -> list[Event]:
        events = []
        
        if not self._storage_path or not os.path.exists(self._storage_path):
            return events
        
        with open(self._storage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == event_type:
                        events.append(Event.from_dict(data))
                except json.JSONDecodeError:
                    continue
        
        return events
