import pytest
import tempfile
import os
import json
from datetime import datetime
from core.event_bus_persistent import PersistentEventBus, Event


class TestPersistentEventBus:
    @pytest.fixture
    def temp_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            path = f.name
        yield path
        if os.path.exists(path):
            os.remove(path)
    
    def test_event_creation(self):
        event = Event(type="test", data={"key": "value"})
        assert event.type == "test"
        assert event.data["key"] == "value"
        assert event.timestamp is not None
    
    def test_publish_and_subscribe(self, temp_file):
        bus = PersistentEventBus(temp_file)
        received = []
        
        def handler(event):
            received.append(event)
        
        bus.subscribe("test_event", handler)
        bus.publish(Event(type="test_event", data={"key": "value"}))
        
        assert len(received) == 1
        assert received[0].type == "test_event"
    
    def test_persistence(self, temp_file):
        bus1 = PersistentEventBus(temp_file)
        bus1.publish(Event(type="test", data={"id": 1}))
        bus1.publish(Event(type="test", data={"id": 2}))
        
        bus2 = PersistentEventBus(temp_file)
        received = []
        bus2.subscribe("test", lambda e: received.append(e))
        bus2.replay_history()
        
        assert len(received) == 2
        assert received[0].data["id"] == 1
        assert received[1].data["id"] == 2
    
    def test_is_connected(self, temp_file):
        bus = PersistentEventBus()
        assert not bus.is_connected()
        
        bus.enable_persistence(temp_file)
        assert bus.is_connected()
    
    def test_filter_by_type(self, temp_file):
        bus = PersistentEventBus(temp_file)
        bus.publish(Event(type="type_a", data={}))
        bus.publish(Event(type="type_b", data={}))
        bus.publish(Event(type="type_a", data={}))
        
        events = bus.get_events_by_type("type_a")
        assert len(events) == 2
