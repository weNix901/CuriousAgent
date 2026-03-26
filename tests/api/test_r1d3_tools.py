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


def test_curious_agent_inject_success():
    handler = R1D3ToolHandler()
    
    result = handler.curious_agent_inject(
        topic="MCP protocol",
        context="User asked about MCP",
        depth="medium"
    )
    
    assert result["status"] == "success"
    assert "queue_position" in result


def test_curious_agent_inject_priority():
    handler = R1D3ToolHandler()
    
    with patch.object(handler, '_get_config') as mock_config:
        mock_config.return_value = {
            "injection_priority": {
                "enabled": True,
                "priority_sources": ["r1d3"],
                "boost_score": 2.0
            }
        }
        
        result = handler.curious_agent_inject(
            topic="priority topic",
            source="r1d3"
        )
        
        assert result["priority"] is True
        assert result["boosted_score"] > 5.0
