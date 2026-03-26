import pytest
from core.spider.state import SpiderRuntimeState


class TestSpiderRuntimeState:
    def test_default_values(self):
        state = SpiderRuntimeState()
        
        assert state.current_node is None
        assert state.frontier == []
        assert state.visited == set()
        assert state.consecutive_low_gain == 0
        assert state.step_count == 0
    
    def test_to_dict(self):
        state = SpiderRuntimeState(
            current_node="attention",
            frontier=["transformer", "bert"],
            visited={"attention"},
            consecutive_low_gain=2,
            step_count=10,
        )
        
        data = state.to_dict()
        
        assert data["current_node"] == "attention"
        assert data["frontier"] == ["transformer", "bert"]
        assert data["visited"] == ["attention"]
        assert data["consecutive_low_gain"] == 2
        assert data["step_count"] == 10
    
    def test_from_dict(self):
        data = {
            "current_node": "attention",
            "frontier": ["transformer", "bert"],
            "visited": ["attention", "gpt"],
            "consecutive_low_gain": 3,
            "step_count": 15,
        }
        
        state = SpiderRuntimeState.from_dict(data)
        
        assert state.current_node == "attention"
        assert state.frontier == ["transformer", "bert"]
        assert state.visited == {"attention", "gpt"}
        assert state.consecutive_low_gain == 3
        assert state.step_count == 15
