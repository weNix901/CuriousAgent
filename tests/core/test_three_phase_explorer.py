import pytest
from unittest.mock import Mock
from core.three_phase_explorer import ThreePhaseExplorer


def test_phase1_monitor_high_confidence():
    mock_explorer = Mock()
    mock_monitor = Mock()
    mock_monitor._compute_user_relevance = Mock(return_value=0.9)
    
    explorer = ThreePhaseExplorer(mock_explorer, mock_monitor, Mock())
    result = explorer._phase1_monitor("test_topic")
    
    assert result["already_known"] is True
    assert result["confidence"] == 0.9


def test_phase1_monitor_low_confidence():
    mock_explorer = Mock()
    mock_monitor = Mock()
    mock_monitor._compute_user_relevance = Mock(return_value=0.5)
    
    mock_llm = Mock()
    mock_llm.chat = Mock(return_value='{"gaps": [{"type": "no_definition"}]}')
    
    explorer = ThreePhaseExplorer(mock_explorer, mock_monitor, mock_llm)
    result = explorer._phase1_monitor("test_topic")
    
    assert result["already_known"] is False
    assert "knowledge_gaps" in result


def test_phase2_generate_plans():
    explorer = ThreePhaseExplorer(Mock(), Mock(), Mock())
    
    gaps = [
        {"type": "no_empirical_results", "priority": 0.8},
        {"type": "no_applications", "priority": 0.5}
    ]
    
    plans = explorer._phase2_generate("topic", gaps, "medium")
    
    assert len(plans) == 2
    assert plans[0]["priority"] == 0.8
