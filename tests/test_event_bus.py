import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.event_bus import EventBus


class TestEventBus:
    def setup_method(self):
        EventBus.clear()

    def test_subscribe_and_emit(self):
        received = []
        def handler(payload):
            received.append(payload)
        
        EventBus.subscribe("test.event", handler)
        EventBus.emit("test.event", {"data": "hello"})
        
        assert len(received) == 1
        assert received[0]["data"] == "hello"

    def test_multiple_handlers(self):
        count = [0]
        def handler1(_):
            count[0] += 1
        def handler2(_):
            count[0] += 1
        
        EventBus.subscribe("test.event", handler1)
        EventBus.subscribe("test.event", handler2)
        EventBus.emit("test.event", {})
        
        assert count[0] == 2

    def test_unsubscribe(self):
        received = []
        def handler(payload):
            received.append(payload)
        
        EventBus.subscribe("test.event", handler)
        EventBus.unsubscribe("test.event", handler)
        EventBus.emit("test.event", {"data": "hello"})
        
        assert len(received) == 0

    def test_handler_exception(self):
        def bad_handler(_):
            raise ValueError("Test error")
        
        EventBus.subscribe("test.event", bad_handler)
        EventBus.emit("test.event", {})

    def test_clear(self):
        def handler(_):
            pass
        
        EventBus.subscribe("test.event", handler)
        EventBus.clear()
        subscribers = EventBus.list_subscribers()
        assert subscribers == {}

    def test_list_subscribers(self):
        def handler(_):
            pass
        
        EventBus.subscribe("event1", handler)
        EventBus.subscribe("event2", handler)
        subscribers = EventBus.list_subscribers()
        
        assert subscribers["event1"] == 1
        assert subscribers["event2"] == 1
