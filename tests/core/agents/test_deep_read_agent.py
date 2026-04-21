"""Tests for DeepReadAgent (v0.3.3)."""
import pytest
from core.agents.deep_read_agent import DeepReadAgent, DeepReadAgentConfig, DEFAULT_TOOLS


class TestDeepReadAgentConfig:
    def test_import_deep_read_agent_config(self):
        """Test that DeepReadAgentConfig can be imported."""
        assert DeepReadAgentConfig is not None
    
    def test_deep_read_agent_config_has_required_fields(self):
        """Test that config has expected fields."""
        config = DeepReadAgentConfig()
        assert config.name == "deep_read_agent"
        assert config.max_iterations == 20
        assert config.model == "volcengine"
    
    def test_deep_read_agent_config_default_tools(self):
        """Test that config has default tools."""
        config = DeepReadAgentConfig()
        assert config.tools == DEFAULT_TOOLS
        assert "read_paper_text" in config.tools
        assert "add_to_kg" in config.tools


class TestDeepReadAgent:
    def test_import_deep_read_agent(self):
        """Test that DeepReadAgent can be imported."""
        assert DeepReadAgent is not None
    
    def test_deep_read_agent_extends_ca_agent(self):
        """Test that DeepReadAgent extends CAAgent."""
        from core.agents.ca_agent import CAAgent
        assert issubclass(DeepReadAgent, CAAgent)
    
    def test_deep_read_agent_init_requires_config_and_registry(self):
        """Test that DeepReadAgent requires config and tool_registry."""
        config = DeepReadAgentConfig()
        from core.tools.registry import ToolRegistry
        registry = ToolRegistry()
        agent = DeepReadAgent(config=config, tool_registry=registry)
        assert agent is not None
        assert agent.name == "deep_read_agent"
    
    def test_deep_read_agent_has_holder_id(self):
        """Test that DeepReadAgent has holder_id."""
        config = DeepReadAgentConfig()
        from core.tools.registry import ToolRegistry
        registry = ToolRegistry()
        agent = DeepReadAgent(config=config, tool_registry=registry)
        assert hasattr(agent, "holder_id")
    
    def test_deep_read_agent_has_run_method(self):
        """Test that DeepReadAgent has run method."""
        config = DeepReadAgentConfig()
        from core.tools.registry import ToolRegistry
        registry = ToolRegistry()
        agent = DeepReadAgent(config=config, tool_registry=registry)
        assert hasattr(agent, "run")
        assert callable(agent.run)
    
    def test_deep_read_agent_run_returns_no_items(self):
        """Test that run returns failure when no deep_read items."""
        import asyncio
        config = DeepReadAgentConfig()
        from core.tools.registry import ToolRegistry
        registry = ToolRegistry()
        agent = DeepReadAgent(config=config, tool_registry=registry)
        
        result = asyncio.run(agent.run())
        assert result.success is False
        assert "No deep_read items" in result.content