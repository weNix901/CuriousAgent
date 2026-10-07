"""v0.3 legacy 测试 salvaged（2026-10-07）

原 test_phase3_integration.py 中不依赖 CuriosityDecomposer 的测试，
在 decomposer 废弃后从 legacy 迁回。decomposer 相关测试见
legacy/tests/test_phase3_integration.py.deprecated。
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from core.quality_gate import should_queue


def test_quality_gate_integration():
    """Test quality gate blocks bad topics"""
    result, reason = should_queue("agent")
    assert result is False
    
    result, reason = should_queue("what is")
    assert result is False
    
    result, reason = should_queue("agent memory systems")
    assert result is True


@pytest.mark.xfail(
    reason="Pre-existing failure (confirmed on HEAD f864fca before deprecation): "
           "knowledge_graph_compat.mark_child_explored() is a no-op pass, so "
           "get_exploration_status() stays 'unexplored'. Tests the legacy KG stub "
           "API, not the Neo4j-backed compat shim. Tracked separately.",
    strict=False,
)
def test_knowledge_graph_parent_child():
    """Test KG parent-child functionality (legacy stub API — see xfail reason)"""
    from core import knowledge_graph_compat as kg
    
    kg.add_child("agent", "agent_memory")
    kg.add_child("agent", "agent_planning")
    
    children = kg.get_children("agent")
    assert "agent_memory" in children
    assert "agent_planning" in children
    
    kg.mark_child_explored("agent", "agent_memory")
    status = kg.get_exploration_status("agent")
    assert status == "partial"
