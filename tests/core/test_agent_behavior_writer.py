import pytest
from unittest.mock import Mock, patch
from core.agent_behavior_writer import AgentBehaviorWriter, QUALITY_THRESHOLD


def test_quality_threshold_check():
    writer = AgentBehaviorWriter()
    
    # Below threshold
    result = writer.process("topic", {}, 6.0, [])
    assert result["applied"] is False
    assert "threshold" in result["reason"]
    
    # Above threshold
    with patch.object(writer, '_classify_discovery', return_value="tool_discovery"):
        with patch.object(writer, '_append_to_file', return_value=True):
            result = writer.process("topic", {"summary": "test"}, 8.0, ["http://example.com"])
            assert result["applied"] is True


def test_blacklist_check():
    writer = AgentBehaviorWriter()
    
    result = writer.process("stock market news", {"summary": "test"}, 8.0, [])
    assert result["applied"] is False
    assert "blacklist" in result["reason"]


def test_classify_metacognition():
    writer = AgentBehaviorWriter()
    
    result = writer._classify_discovery("metacognition strategies", {"summary": ""})
    assert result == "metacognition_strategy"


def test_classify_tool():
    writer = AgentBehaviorWriter()
    
    findings = {"summary": "Install with pip install tool"}
    result = writer._classify_discovery("new framework", findings)
    assert result == "tool_discovery"


def test_classify_none():
    writer = AgentBehaviorWriter()
    
    result = writer._classify_discovery("random topic", {"summary": ""})
    assert result is None


def test_generate_rule():
    writer = AgentBehaviorWriter()
    
    rule = writer._generate_behavior_rule(
        "Test Topic",
        {"summary": "This is a test discovery"},
        ["http://example.com"],
        "tool_discovery"
    )
    
    assert "Test Topic" in rule
    assert "behavior-rule" not in rule  # Tags are in memory sync, not rule
