import pytest
import tempfile
import os
from core.spider.checkpoint import SpiderCheckpoint
from core.spider.state import SpiderRuntimeState


class TestSpiderCheckpoint:
    @pytest.fixture
    def checkpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "checkpoint.json")
            checkpoint = SpiderCheckpoint(path)
            yield checkpoint
    
    def test_save_and_load(self, checkpoint):
        state = SpiderRuntimeState(
            current_node="attention",
            frontier=["transformer"],
            visited={"attention"},
            step_count=5,
        )
        
        checkpoint.save(state, "knowledge/state.json")
        loaded_state, kg_path = checkpoint.load()
        
        assert loaded_state.current_node == "attention"
        assert loaded_state.frontier == ["transformer"]
        assert loaded_state.visited == {"attention"}
        assert loaded_state.step_count == 5
        assert kg_path == "knowledge/state.json"
    
    def test_load_returns_none_when_missing(self):
        checkpoint = SpiderCheckpoint("/nonexistent/path.json")
        result = checkpoint.load()
        
        assert result is None
    
    def test_exists(self, checkpoint):
        assert not checkpoint.exists()
        
        state = SpiderRuntimeState()
        checkpoint.save(state, "test.json")
        
        assert checkpoint.exists()
    
    def test_clear(self, checkpoint):
        state = SpiderRuntimeState()
        checkpoint.save(state, "test.json")
        
        assert checkpoint.exists()
        checkpoint.clear()
        assert not checkpoint.exists()
