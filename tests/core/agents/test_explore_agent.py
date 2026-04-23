"""Tests for ExploreAgent with ReAct loop."""
import pytest
from dataclasses import dataclass
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


class TestExploreAgentConfig:
    """Test ExploreAgentConfig dataclass."""

    def test_import_explore_agent_config(self):
        """ExploreAgentConfig should be importable from core.agents.explore_agent."""
        from core.agents.explore_agent import ExploreAgentConfig
        assert ExploreAgentConfig is not None

    def test_explore_agent_config_has_required_fields(self):
        """ExploreAgentConfig should have name, system_prompt, tools, max_iterations, model fields."""
        from core.agents.explore_agent import ExploreAgentConfig
        
        config = ExploreAgentConfig(
            name="explore_agent",
            system_prompt="You are an exploration agent",
            tools=["search_web", "query_kg", "add_to_queue"],
            max_iterations=10,
            model="doubao-pro"
        )
        
        assert config.name == "explore_agent"
        assert config.system_prompt == "You are an exploration agent"
        assert config.tools == ["search_web", "query_kg", "add_to_queue"]
        assert config.max_iterations == 10
        assert config.model == "doubao-pro"

    def test_explore_agent_config_default_values(self):
        """ExploreAgentConfig should have sensible defaults."""
        from core.agents.explore_agent import ExploreAgentConfig, DEFAULT_TOOLS
        
        config = ExploreAgentConfig(
            name="explore_agent",
            system_prompt="Explore knowledge"
        )
        
        assert config.tools == DEFAULT_TOOLS
        assert config.max_iterations == 10
        assert config.model == "doubao-pro"


class TestExploreAgent:
    """Test ExploreAgent class."""

    def test_import_explore_agent(self):
        """ExploreAgent should be importable from core.agents.explore_agent."""
        from core.agents.explore_agent import ExploreAgent
        assert ExploreAgent is not None

    def test_explore_agent_extends_ca_agent(self):
        """ExploreAgent should extend CAAgent."""
        from core.agents.explore_agent import ExploreAgent
        from core.agents.ca_agent import CAAgent
        
        assert issubclass(ExploreAgent, CAAgent)

    def test_explore_agent_init_requires_config_and_registry(self):
        """ExploreAgent __init__ should accept config and tool_registry."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(
            name="explore_agent",
            system_prompt="Explore knowledge"
        )
        registry = ToolRegistry()
        
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        assert agent is not None
        assert agent.config == config
        assert agent.tool_registry == registry

    def test_explore_agent_has_holder_id(self):
        """ExploreAgent should have a holder_id for queue operations."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt="Explore")
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        assert hasattr(agent, 'holder_id')
        assert agent.holder_id is not None

    def test_explore_agent_has_max_iterations_10(self):
        """ExploreAgent should use max_iterations of 10 for ReAct loop."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(
            name="explore_agent",
            system_prompt="Explore",
            max_iterations=10
        )
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        assert agent.config.max_iterations == 10

    def test_explore_agent_has_react_loop_method(self):
        """ExploreAgent should have _react_loop method for ReAct cycle."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt="Explore")
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        assert hasattr(agent, '_react_loop')

    def test_explore_agent_react_loop_returns_result(self):
        """ExploreAgent._react_loop should return a result after iterations."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt="Explore")
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        # Mock the LLM client to return a simple response
        with patch('core.agents.explore_agent.LLMClient') as mock_llm:
            mock_client = MagicMock()
            mock_client.chat.return_value = '{"thought": "Exploring", "action": "done", "action_input": {}}'
            mock_llm.return_value = mock_client
            
            import asyncio
            result = asyncio.run(agent._react_loop("Test topic"))
            
            assert result is not None
            assert isinstance(result, dict)

    def test_explore_agent_run_workflow_claim_explore_mark_done(self):
        """ExploreAgent.run should follow workflow: claim topic -> explore -> mark done."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        from core.agents.ca_agent import AgentResult
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt="Explore")
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        # Mock queue tools
        with patch.object(agent, '_claim_topic', new_callable=AsyncMock) as mock_claim, \
             patch.object(agent, '_react_loop', new_callable=AsyncMock) as mock_react, \
             patch.object(agent, '_mark_done', new_callable=AsyncMock) as mock_mark:
            
            mock_claim.return_value = {"success": True, "item_id": 1, "topic": "test_topic"}
            mock_react.return_value = {"content": "Exploration complete", "success": True, "iterations": 5}
            mock_mark.return_value = True
            
            import asyncio
            result = asyncio.run(agent.run("test_topic"))
            
            assert mock_claim.called
            assert mock_react.called
            assert mock_mark.called
            assert isinstance(result, AgentResult)

    def test_explore_agent_has_claim_topic_method(self):
        """ExploreAgent should have _claim_topic method."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt="Explore")
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        assert hasattr(agent, '_claim_topic')

    def test_explore_agent_has_mark_done_method(self):
        """ExploreAgent should have _mark_done method."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt="Explore")
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        assert hasattr(agent, '_mark_done')

    def test_explore_agent_system_prompt_is_exploration_focused(self):
        """ExploreAgent system prompt should be exploration-focused."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig, DEFAULT_SYSTEM_PROMPT
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt=DEFAULT_SYSTEM_PROMPT)
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        system_prompt = agent._build_system_prompt()
        
        assert "explore" in system_prompt.lower() or "knowledge" in system_prompt.lower()


class TestExploreAgentReActLoop:
    """Test ExploreAgent ReAct loop behavior."""

    def test_react_loop_thought_action_observation_pattern(self):
        """ReAct loop should follow Thought -> Action -> Observation pattern."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt="Explore")
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        # The ReAct loop should parse LLM response for thought, action, action_input
        with patch('core.agents.explore_agent.LLMClient') as mock_llm:
            mock_client = MagicMock()
            # Simulate a ReAct response
            mock_client.chat.return_value = '''
{
    "thought": "I need to search for information about this topic",
    "action": "search_web",
    "action_input": {"query": "test topic"}
}
'''
            mock_llm.return_value = mock_client
            
            import asyncio
            result = asyncio.run(agent._react_loop("test topic"))
            
            assert result is not None

    def test_react_loop_respects_max_iterations(self):
        """ReAct loop should stop after max_iterations."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(
            name="explore_agent",
            system_prompt="Explore",
            max_iterations=3
        )
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        call_count = 0
        
        def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return '{"thought": "thinking", "action": "done", "action_input": {}}'
        
        with patch('core.agents.explore_agent.LLMClient') as mock_llm:
            mock_client = MagicMock()
            mock_client.chat.side_effect = count_calls
            mock_llm.return_value = mock_client
            
            import asyncio
            asyncio.run(agent._react_loop("test topic"))
            
            # Should not exceed max_iterations
            assert call_count <= 3

    def test_react_loop_handles_done_action(self):
        """ReAct loop should terminate when action is 'done'."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt="Explore")
        registry = ToolRegistry()
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        with patch('core.agents.explore_agent.LLMClient') as mock_llm:
            mock_client = MagicMock()
            # Return done on first iteration
            mock_client.chat.return_value = '{"thought": "Done exploring", "action": "done", "action_input": {}}'
            mock_llm.return_value = mock_client
            
            import asyncio
            result = asyncio.run(agent._react_loop("test topic"))
            
            assert result is not None
            assert result.get('success', False) or result.get('content') is not None

    def test_react_loop_executes_tool_actions(self):
        """ReAct loop should execute tool actions when action is not 'done'."""
        from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
        from core.tools.registry import ToolRegistry
        from core.tools.base import Tool
        from typing import Any
        
        # Create a mock tool
        class MockTool(Tool):
            @property
            def name(self) -> str:
                return "mock_tool"
            
            @property
            def description(self) -> str:
                return "A mock tool"
            
            @property
            def parameters(self) -> dict[str, Any]:
                return {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input"}
                    },
                    "required": ["input"]
                }
            
            async def execute(self, **kwargs: Any) -> str:
                return f"Mock result for {kwargs.get('input')}"
        
        config = ExploreAgentConfig(name="explore_agent", system_prompt="Explore")
        registry = ToolRegistry()
        registry.register(MockTool())
        agent = ExploreAgent(config=config, tool_registry=registry)
        
        call_count = 0
        
        def mock_chat(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"thought": "Use mock tool", "action": "mock_tool", "action_input": {"input": "test"}}'
            else:
                return '{"thought": "Done", "action": "done", "action_input": {}}'
        
        with patch('core.agents.explore_agent.LLMClient') as mock_llm:
            mock_client = MagicMock()
            mock_client.chat.side_effect = mock_chat
            mock_llm.return_value = mock_client
            
            import asyncio
            result = asyncio.run(agent._react_loop("test topic"))
            
            assert call_count == 2  # Two iterations: one action, one done


class TestExploreAgentToolSubset:
    """Test ExploreAgent uses correct tool subset."""

    def test_explore_agent_uses_14_tools(self):
        """ExploreAgent should be configured with 14 tools (KG write + Queue + Search + LLM)."""
        from core.agents.explore_agent import ExploreAgentConfig, DEFAULT_TOOLS
        
        # DEFAULT_TOOLS should contain exactly 14 tools
        assert len(DEFAULT_TOOLS) == 14

    def test_explore_agent_has_kg_write_tools(self):
        """ExploreAgent should have KG write tools."""
        from core.agents.explore_agent import DEFAULT_TOOLS
        
        # Should have add_to_kg for writing to KG
        assert "add_to_kg" in DEFAULT_TOOLS

    def test_explore_agent_has_queue_tools(self):
        """ExploreAgent should have Queue tools for claim/mark_done."""
        from core.agents.explore_agent import DEFAULT_TOOLS
        
        # Should have queue management tools
        assert "claim_queue" in DEFAULT_TOOLS
        assert "mark_done" in DEFAULT_TOOLS
        assert "get_queue" in DEFAULT_TOOLS

    def test_explore_agent_has_search_tools(self):
        """ExploreAgent should have Search tools."""
        from core.agents.explore_agent import DEFAULT_TOOLS
        
        # Should have search capabilities
        assert "search_web" in DEFAULT_TOOLS

    def test_explore_agent_has_llm_tools(self):
        """ExploreAgent should have LLM tools."""
        from core.agents.explore_agent import DEFAULT_TOOLS
        
        # Should have LLM analysis capabilities
        assert "llm_analyze" in DEFAULT_TOOLS or "llm_extract_knowledge" in DEFAULT_TOOLS
