import pytest
from core.competence_tracker import CompetenceTracker
from core import knowledge_graph_compat as kg


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test"""
    state = kg.get_state()
    state["competence_state"] = {}
    kg._save_state(state)


def test_assess_competence_cold_start():
    tracker = CompetenceTracker()
    result = tracker.assess_competence("new_topic")
    
    assert result["confidence"] == 0.5
    assert result["explore_count"] == 0


def test_update_competence():
    tracker = CompetenceTracker()
    
    tracker.update_competence("test_topic", 8.0)
    
    competence = tracker.assess_competence("test_topic")
    assert competence["explore_count"] == 1


def test_quality_trend_computation():
    tracker = CompetenceTracker()
    
    trend = tracker._compute_quality_trend([5.0, 6.0, 7.0, 8.0])
    assert trend > 0
    
    trend = tracker._compute_quality_trend([8.0, 7.0, 6.0, 5.0])
    assert trend < 0


def test_score_to_level():
    tracker = CompetenceTracker()
    
    assert tracker._score_to_level(0.2) == "novice"
    assert tracker._score_to_level(0.5) == "competent"
    assert tracker._score_to_level(0.7) == "proficient"
    assert tracker._score_to_level(0.9) == "expert"
