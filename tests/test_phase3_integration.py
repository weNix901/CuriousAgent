"""Phase 3 End-to-End Integration Test"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from core.curiosity_decomposer import CuriosityDecomposer
from core.provider_registry import ProviderRegistry
from core.exceptions import ClarificationNeeded
from core.quality_gate import should_queue


@pytest.mark.asyncio
async def test_full_decomposition_flow():
    """Test complete decomposition flow"""
    mock_llm = Mock()
    mock_llm.chat = Mock(return_value="""- agent_memory - AI memory systems
- agent_planning - Task planning
- agent_tools - Tool usage""")
    
    registry = ProviderRegistry()
    registry.reset()
    
    # Register two providers for 2-provider validation
    mock_provider1 = Mock()
    mock_provider1.name = "bocha"
    mock_provider1.search = AsyncMock(return_value={
        "result_count": 50,
        "results": []
    })
    registry.register(mock_provider1)
    
    mock_provider2 = Mock()
    mock_provider2.name = "serper"
    mock_provider2.search = AsyncMock(return_value={
        "result_count": 60,
        "results": []
    })
    registry.register(mock_provider2)
    
    mock_kg = {"topics": {}}
    
    decomposer = CuriosityDecomposer(mock_llm, registry, mock_kg)
    
    result = await decomposer.decompose("agent")
    
    assert len(result) > 0
    # Check for 'candidate' key since sub_topic might not be set in test environment
    topics = [r.get("sub_topic") or r.get("candidate") for r in result]
    assert "agent_memory" in topics


def test_quality_gate_integration():
    """Test quality gate blocks bad topics"""
    result, reason = should_queue("agent")
    assert result is False
    
    result, reason = should_queue("what is")
    assert result is False
    
    result, reason = should_queue("agent memory systems")
    assert result is True


def test_knowledge_graph_parent_child():
    """Test KG parent-child functionality"""
    from core import knowledge_graph as kg
    
    kg.add_child("agent", "agent_memory")
    kg.add_child("agent", "agent_planning")
    
    children = kg.get_children("agent")
    assert "agent_memory" in children
    assert "agent_planning" in children
    
    kg.mark_child_explored("agent", "agent_memory")
    status = kg.get_exploration_status("agent")
    assert status == "partial"
