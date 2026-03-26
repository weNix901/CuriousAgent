import pytest
from unittest.mock import Mock, patch
from core.api.r1d3_tools import R1D3ToolHandler


def test_curious_check_confidence_novice():
    handler = R1D3ToolHandler()
    
    mock_repo = Mock()
    mock_repo.get_topic.return_value = None
    handler.repo = mock_repo
    
    result = handler.curious_check_confidence("new_topic")
    
    assert result["topic"] == "new_topic"
    assert result["confidence"] == 0.0
    assert result["level"] == "novice"


def test_curious_check_confidence_expert():
    handler = R1D3ToolHandler()
    
    mock_topic = Mock()
    mock_topic.explored = True
    mock_topic.explore_count = 5
    mock_topic.last_quality = 8.5
    
    mock_repo = Mock()
    mock_repo.get_topic.return_value = mock_topic
    handler.repo = mock_repo
    
    result = handler.curious_check_confidence("expert_topic")
    
    assert result["confidence"] > 0.85
    assert result["level"] == "expert"
