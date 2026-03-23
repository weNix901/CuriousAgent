import pytest
from core.exceptions import ClarificationNeeded


def test_clarification_needed():
    exc = ClarificationNeeded("agent")
    assert exc.topic == "agent"
    assert len(exc.alternatives) == 3
    assert "agent" in str(exc)


def test_clarification_needed_with_reason():
    exc = ClarificationNeeded("test", reason="no provider results")
    assert "no provider results" in str(exc)
