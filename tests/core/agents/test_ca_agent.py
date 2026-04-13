"""Tests for CAAgent unified class."""
import pytest
from dataclasses import dataclass
from typing import List


class TestCAAgentConfig:
    """Test CAAgentConfig dataclass."""

    def test_import_ca_agent_config(self):
        """CAAgentConfig should be importable from core.agents.ca_agent."""
        from core.agents.ca_agent import CAAgentConfig
        assert CAAgentConfig is not None

    def test_ca_agent_config_has_required_fields(self):
        """CAAgentConfig should have name, system_prompt, tools, max_iterations, model fields."""
        from core.agents.ca_agent import CAAgentConfig
        
        config = CAAgentConfig(
            name="test_agent",
            system_prompt="You are a test agent",
            tools=["search", "read"],
            max_iterations=10,
            model="doubao-pro"
        )
        
        assert config.name == "test_agent"
        assert config.system_prompt == "You are a test agent"
        assert config.tools == ["search", "read"]
        assert config.max_iterations == 10
        assert config.model == "doubao-pro"

    def test_ca_agent_config_default_values(self):
        """CAAgentConfig should have sensible defaults."""
        from core.agents.ca_agent import CAAgentConfig
        
        config = CAAgentConfig(
            name="default_agent",
            system_prompt="Default prompt"
        )
        
        assert config.tools == []
        assert config.max_iterations == 20
        assert config.model == "doubao-pro"


class TestCAAgent:
    """Test CAAgent class."""

    def test_import_ca_agent(self):
        """CAAgent should be importable from core.agents.ca_agent."""
        from core.agents.ca_agent import CAAgent
        assert CAAgent is not None

    def test_ca_agent_init_requires_config_and_registry(self):
        """CAAgent __init__ should accept config and tool_registry."""
        from core.agents.ca_agent import CAAgent, CAAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = CAAgentConfig(
            name="test_agent",
            system_prompt="Test prompt"
        )
        registry = ToolRegistry()
        
        agent = CAAgent(config=config, tool_registry=registry)
        
        assert agent is not None
        assert agent.config == config
        assert agent.tool_registry == registry

    def test_ca_agent_has_run_method(self):
        """CAAgent should have a run method that accepts input_data."""
        from core.agents.ca_agent import CAAgent, CAAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = CAAgentConfig(name="test", system_prompt="test")
        agent = CAAgent(config=config, tool_registry=ToolRegistry())
        
        assert hasattr(agent, 'run')

    def test_ca_agent_run_returns_agent_result(self):
        """CAAgent.run should return an AgentResult with content, success, iterations_used."""
        from core.agents.ca_agent import CAAgent, CAAgentConfig, AgentResult
        from core.tools.registry import ToolRegistry
        
        config = CAAgentConfig(name="test", system_prompt="test")
        agent = CAAgent(config=config, tool_registry=ToolRegistry())
        
        # Run with empty input
        result = agent.run(input_data="test input")
        
        assert isinstance(result, AgentResult)
        assert hasattr(result, 'content')
        assert hasattr(result, 'success')
        assert hasattr(result, 'iterations_used')

    def test_ca_agent_has_build_system_prompt_method(self):
        """CAAgent should have _build_system_prompt method."""
        from core.agents.ca_agent import CAAgent, CAAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = CAAgentConfig(
            name="test_agent",
            system_prompt="Custom system prompt"
        )
        agent = CAAgent(config=config, tool_registry=ToolRegistry())
        
        assert hasattr(agent, '_build_system_prompt')

    def test_ca_agent_build_system_prompt_returns_config_prompt(self):
        """CAgent._build_system_prompt should return the system_prompt from config."""
        from core.agents.ca_agent import CAAgent, CAAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = CAAgentConfig(
            name="test_agent",
            system_prompt="You are a helpful assistant"
        )
        agent = CAAgent(config=config, tool_registry=ToolRegistry())
        
        system_prompt = agent._build_system_prompt()
        
        assert system_prompt == "You are a helpful assistant"

    def test_ca_agent_has_get_tool_schemas_method(self):
        """CAAgent should have _get_tool_schemas method."""
        from core.agents.ca_agent import CAAgent, CAAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = CAAgentConfig(name="test", system_prompt="test")
        agent = CAAgent(config=config, tool_registry=ToolRegistry())
        
        assert hasattr(agent, '_get_tool_schemas')

    def test_ca_agent_get_tool_schemas_returns_list(self):
        """CAgent._get_tool_schemas should return a list of tool schemas."""
        from core.agents.ca_agent import CAAgent, CAAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = CAAgentConfig(name="test", system_prompt="test")
        registry = ToolRegistry()
        agent = CAAgent(config=config, tool_registry=registry)
        
        schemas = agent._get_tool_schemas()
        
        assert isinstance(schemas, list)


class TestAgentResult:
    """Test AgentResult dataclass."""

    def test_import_agent_result(self):
        """AgentResult should be importable from core.agents.ca_agent."""
        from core.agents.ca_agent import AgentResult
        assert AgentResult is not None

    def test_agent_result_has_required_fields(self):
        """AgentResult should have content, success, iterations_used fields."""
        from core.agents.ca_agent import AgentResult
        
        result = AgentResult(
            content="Test response",
            success=True,
            iterations_used=3
        )
        
        assert result.content == "Test response"
        assert result.success is True
        assert result.iterations_used == 3

    def test_agent_result_failure_case(self):
        """AgentResult should support failure cases."""
        from core.agents.ca_agent import AgentResult
        
        result = AgentResult(
            content="Error occurred",
            success=False,
            iterations_used=10
        )
        
        assert result.success is False
        assert result.iterations_used == 10
