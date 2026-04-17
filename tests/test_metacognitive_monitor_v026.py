"""Tests for MetaCognitiveMonitor v0.2.6 enhancements (F12)."""
import pytest
from datetime import datetime, timezone
from core.meta_cognitive_monitor import MetaCognitiveMonitor


class TestConfidenceInterval:
    """Test confidence interval tracking."""
    
    def test_get_confidence_interval_returns_defaults(self, tmp_path, monkeypatch):
        """Should return default confidence interval for new topic."""
        import core.knowledge_graph_compat as kg
        original_file = kg.STATE_FILE
        temp_file = tmp_path / "state.json"
        monkeypatch.setattr(kg, 'STATE_FILE', str(temp_file))
        
        monitor = MetaCognitiveMonitor()
        low, high = monitor.get_confidence_interval("new_topic")
        
        assert low == 0.3
        assert high == 0.7
        
        monkeypatch.setattr(kg, 'STATE_FILE', original_file)
    
    def test_update_node_confidence_increases_low(self, tmp_path, monkeypatch):
        """Should increase confidence_low with evidence."""
        import core.knowledge_graph_compat as kg
        original_file = kg.STATE_FILE
        temp_file = tmp_path / "state.json"
        monkeypatch.setattr(kg, 'STATE_FILE', str(temp_file))
        
        monitor = MetaCognitiveMonitor()
        monitor.update_node_confidence("topic_x", delta_evidence=1)
        
        low, high = monitor.get_confidence_interval("topic_x")
        assert low == 0.4  # 0.3 + 0.1
        assert high == 0.7
        
        monkeypatch.setattr(kg, 'STATE_FILE', original_file)
    
    def test_update_node_confidence_decreases_high(self, tmp_path, monkeypatch):
        """Should decrease confidence_high with contradictions."""
        import core.knowledge_graph_compat as kg
        original_file = kg.STATE_FILE
        temp_file = tmp_path / "state.json"
        monkeypatch.setattr(kg, 'STATE_FILE', str(temp_file))
        
        monitor = MetaCognitiveMonitor()
        monitor.update_node_confidence("topic_contradiction", delta_contradiction=1)
        
        low, high = monitor.get_confidence_interval("topic_contradiction")
        assert low == 0.3
        assert round(high, 1) == 0.5  # 0.7 - 0.2
        
        monkeypatch.setattr(kg, 'STATE_FILE', original_file)


class TestFrontierDetection:
    """Test knowledge frontier detection."""
    
    def test_detect_frontier_finds_leaf_nodes(self, tmp_path, monkeypatch):
        """Should find known nodes with no children."""
        import core.knowledge_graph_compat as kg
        original_file = kg.STATE_FILE
        temp_file = tmp_path / "state.json"
        monkeypatch.setattr(kg, 'STATE_FILE', str(temp_file))
        
        # Setup: known node with no children
        kg.add_knowledge("leaf_node", depth=5, summary="Test", sources=[])
        state = kg.get_state()
        state["knowledge"]["topics"]["leaf_node"]["known"] = True
        state["knowledge"]["topics"]["leaf_node"]["children"] = []
        kg._save_state(state)
        
        monitor = MetaCognitiveMonitor()
        frontiers = monitor.detect_frontier()
        
        assert len(frontiers) >= 1
        assert any(f["from_node"] == "leaf_node" for f in frontiers)
        
        monkeypatch.setattr(kg, 'STATE_FILE', original_file)
    
    def test_recommend_exploration_from_frontier(self, tmp_path, monkeypatch):
        """Should recommend frontier topics."""
        import core.knowledge_graph_compat as kg
        original_file = kg.STATE_FILE
        temp_file = tmp_path / "state.json"
        monkeypatch.setattr(kg, 'STATE_FILE', str(temp_file))
        
        monitor = MetaCognitiveMonitor()
        recommendations = monitor.recommend_exploration_from_frontier()
        
        assert isinstance(recommendations, list)
        assert len(recommendations) <= 3
        
        monkeypatch.setattr(kg, 'STATE_FILE', original_file)


class TestCalibration:
    """Test calibration error calculation."""
    
    def test_get_calibration_error_no_predictions(self, tmp_path, monkeypatch):
        """Should return 0.0 when no predictions exist."""
        import core.knowledge_graph_compat as kg
        original_file = kg.STATE_FILE
        temp_file = tmp_path / "state.json"
        monkeypatch.setattr(kg, 'STATE_FILE', str(temp_file))
        
        monitor = MetaCognitiveMonitor()
        error = monitor.get_calibration_error()
        
        assert error == 0.0
        
        monkeypatch.setattr(kg, 'STATE_FILE', original_file)
    
    def test_get_topic_calibration_no_prediction(self, tmp_path, monkeypatch):
        """Should return no_prediction_recorded verdict."""
        import core.knowledge_graph_compat as kg
        original_file = kg.STATE_FILE
        temp_file = tmp_path / "state.json"
        monkeypatch.setattr(kg, 'STATE_FILE', str(temp_file))
        
        monitor = MetaCognitiveMonitor()
        result = monitor.get_topic_calibration("nonexistent_topic")
        
        assert result["verdict"] == "no_prediction_recorded"
        
        monkeypatch.setattr(kg, 'STATE_FILE', original_file)
