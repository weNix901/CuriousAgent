import pytest
from core.quality_gate import should_queue, _is_similar


def test_should_accept_valid_topic():
    result, reason = should_queue("agent memory systems")
    assert result is True
    assert reason == "ok"


def test_reject_too_short():
    result, reason = should_queue("agent")
    assert result is False
    assert reason == "too_short"


def test_reject_blacklist():
    result, reason = should_queue("what is")
    assert result is False
    assert "blacklist" in reason


def test_is_similar():
    assert _is_similar("agent memory", "agent memory systems") is True
    assert _is_similar("agent memory", "agent planning") is False


def test_reject_similar():
    existing = {"agent memory systems"}
    result, reason = should_queue("agent memory", existing)
    assert result is False
    assert reason == "similar_to_existing"
