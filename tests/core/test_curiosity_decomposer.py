import pytest
from unittest.mock import Mock, AsyncMock

from core.curiosity_decomposer import CuriosityDecomposer
from core.exceptions import ClarificationNeeded


@pytest.fixture
def mock_llm():
    return Mock()


@pytest.fixture
def mock_registry():
    registry = Mock()
    registry.get_enabled = Mock(return_value=[])
    return registry


@pytest.fixture
def mock_kg():
    return {"topics": {}}


@pytest.fixture
def decomposer(mock_llm, mock_registry, mock_kg):
    return CuriosityDecomposer(mock_llm, mock_registry, mock_kg)


@pytest.mark.asyncio
async def test_parse_candidates(decomposer):
    response = """- agent_memory - AI memory systems
- agent_planning - Task planning for agents
- agent_tools - Tool usage"""
    
    result = decomposer._parse_candidates(response)
    assert len(result) == 3
    assert "agent_memory" in result


def test_classify_signal(decomposer):
    assert decomposer._classify_signal(3, 150) == "strong"
    assert decomposer._classify_signal(2, 50) == "medium"
    assert decomposer._classify_signal(1, 5) == "weak"


@pytest.mark.asyncio
async def test_decompose_raises_clarification_when_no_candidates(decomposer, mock_llm):
    mock_llm.chat = Mock(return_value="")  # Empty response
    
    with pytest.raises(ClarificationNeeded):
        await decomposer.decompose("agent")


def test_default_config():
    """Test default configuration values"""
    decomp = CuriosityDecomposer(None, None, {})
    assert decomp.config["max_candidates"] == 7
    assert decomp.config["min_candidates"] == 5
    assert decomp.config["max_depth"] == 2
    assert decomp.config["verification_threshold"] == 2


def test_custom_config():
    """Test custom configuration overrides defaults"""
    custom = {"max_candidates": 5, "verification_threshold": 1}
    decomp = CuriosityDecomposer(None, None, {}, config=custom)
    assert decomp.config["max_candidates"] == 5
    assert decomp.config["verification_threshold"] == 1
    # Unchanged defaults
    assert decomp.config["min_candidates"] == 5
