"""Tests for Explorer layer dispatch architecture"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.explorer import Explorer


class TestExplorerLayerDispatch:
    """Test suite for layer dispatch in Explorer"""

    def test_explorer_accepts_exploration_depth_parameter(self):
        """Test that Explorer.__init__ accepts exploration_depth parameter"""
        explorer = Explorer(exploration_depth="shallow")
        assert explorer.exploration_depth == "shallow"

    def test_explorer_default_depth_is_medium(self):
        """Test that default exploration_depth is 'medium'"""
        explorer = Explorer()
        assert explorer.exploration_depth == "medium"

    def test_explorer_rejects_invalid_depth(self):
        """Test that invalid depth raises ValueError"""
        with pytest.raises(ValueError, match="Invalid exploration_depth"):
            Explorer(exploration_depth="invalid")

    def test_explore_calls_explore_layers(self):
        """Test that explore() calls _explore_layers()"""
        explorer = Explorer(exploration_depth="shallow")
        
        # Mock the layer methods to avoid actual API calls
        explorer._layer1_search = MagicMock(return_value={"findings": "layer1", "sources": []})
        explorer._layer2_arxiv = MagicMock(return_value={"findings": "layer2", "sources": []})
        explorer._layer3_insights = MagicMock(return_value={"findings": "layer3", "sources": []})
        
        # Mock knowledge graph operations
        with patch('core.explorer.kg') as mock_kg:
            mock_kg.update_curiosity_status = MagicMock()
            mock_kg.add_knowledge = MagicMock()
            mock_kg.log_exploration = MagicMock()
            mock_kg.DEFAULT_STATE = {"config": {"notification_threshold": 7.0}}
            
            curiosity_item = {"topic": "test topic", "score": 5.0, "depth": 5}
            result = explorer.explore(curiosity_item)
        
        # Verify _explore_layers was called (via layer methods being called)
        assert result is not None
        assert "topic" in result

    def test_shallow_depth_calls_only_layer1(self):
        """Test that shallow depth only calls Layer 1 (web search)"""
        explorer = Explorer(exploration_depth="shallow")
        
        explorer._layer1_search = MagicMock(return_value={"findings": "layer1 results", "sources": ["url1"]})
        explorer._layer2_arxiv = MagicMock(return_value={"findings": "layer2 results", "sources": []})
        explorer._layer3_insights = MagicMock(return_value={"findings": "layer3 results", "sources": []})
        
        with patch('core.explorer.kg') as mock_kg:
            mock_kg.update_curiosity_status = MagicMock()
            mock_kg.add_knowledge = MagicMock()
            mock_kg.log_exploration = MagicMock()
            mock_kg.DEFAULT_STATE = {"config": {"notification_threshold": 7.0}}
            
            curiosity_item = {"topic": "test topic", "score": 5.0, "depth": 5}
            explorer.explore(curiosity_item)
        
        # Layer 1 should be called
        explorer._layer1_search.assert_called_once()
        # Layer 2 and 3 should NOT be called for shallow
        explorer._layer2_arxiv.assert_not_called()
        explorer._layer3_insights.assert_not_called()

    def test_medium_depth_calls_layer1_and_layer2(self):
        """Test that medium depth calls Layer 1 and Layer 2"""
        explorer = Explorer(exploration_depth="medium")
        
        explorer._layer1_search = MagicMock(return_value={
            "findings": "layer1 results", 
            "sources": ["url1"],
            "arxiv_links": ["https://arxiv.org/abs/2401.02009"]
        })
        explorer._layer2_arxiv = MagicMock(return_value={
            "findings": "layer2 results", 
            "sources": [],
            "papers": []
        })
        explorer._layer3_insights = MagicMock(return_value={"findings": "layer3 results", "sources": []})
        
        with patch('core.explorer.kg') as mock_kg:
            mock_kg.update_curiosity_status = MagicMock()
            mock_kg.add_knowledge = MagicMock()
            mock_kg.log_exploration = MagicMock()
            mock_kg.DEFAULT_STATE = {"config": {"notification_threshold": 7.0}}
            
            curiosity_item = {"topic": "test topic", "score": 5.0, "depth": 5}
            explorer.explore(curiosity_item)
        
        # Layer 1 and 2 should be called
        explorer._layer1_search.assert_called_once()
        explorer._layer2_arxiv.assert_called_once()
        # Layer 3 should NOT be called for medium
        explorer._layer3_insights.assert_not_called()

    def test_deep_depth_calls_all_layers(self):
        """Test that deep depth calls all three layers"""
        explorer = Explorer(exploration_depth="deep")
        
        explorer._layer1_search = MagicMock(return_value={
            "findings": "layer1 results", 
            "sources": ["url1"],
            "arxiv_links": ["https://arxiv.org/abs/2401.02009"]
        })
        explorer._layer2_arxiv = MagicMock(return_value={
            "findings": "layer2 results", 
            "sources": [],
            "papers": [
                {"title": "Paper 1", "relevance_score": 0.8, "key_findings": ["f1"]},
                {"title": "Paper 2", "relevance_score": 0.7, "key_findings": ["f2"]}
            ]
        })
        explorer._layer3_insights = MagicMock(return_value={"findings": "layer3 results", "sources": []})
        
        with patch('core.explorer.kg') as mock_kg:
            mock_kg.update_curiosity_status = MagicMock()
            mock_kg.add_knowledge = MagicMock()
            mock_kg.log_exploration = MagicMock()
            mock_kg.DEFAULT_STATE = {"config": {"notification_threshold": 7.0}}
            
            curiosity_item = {"topic": "test topic", "score": 5.0, "depth": 5}
            explorer.explore(curiosity_item)
        
        # All layers should be called
        explorer._layer1_search.assert_called_once()
        explorer._layer2_arxiv.assert_called_once()
        explorer._layer3_insights.assert_called_once()

    def test_explore_layers_returns_combined_results(self):
        """Test that _explore_layers returns combined results from all layers"""
        explorer = Explorer(exploration_depth="deep")
        
        explorer._layer1_search = MagicMock(return_value={
            "findings": "L1: web search", 
            "sources": ["url1"],
            "arxiv_links": ["https://arxiv.org/abs/2401.02009"]
        })
        explorer._layer2_arxiv = MagicMock(return_value={
            "findings": "L2: arxiv", 
            "sources": ["url2"],
            "papers": [
                {"title": "Paper 1", "relevance_score": 0.8, "key_findings": ["f1"]},
                {"title": "Paper 2", "relevance_score": 0.7, "key_findings": ["f2"]}
            ]
        })
        explorer._layer3_insights = MagicMock(return_value={"findings": "L3: insights", "sources": []})
        
        result = explorer._explore_layers("test topic")
        
        assert "findings" in result
        assert "sources" in result
        # Findings should contain content from all layers
        assert "L1" in result["findings"]
        assert "L2" in result["findings"]
        assert "L3" in result["findings"]
        # Sources should be combined
        assert "url1" in result["sources"]
        assert "url2" in result["sources"]
