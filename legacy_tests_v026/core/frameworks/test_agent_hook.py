"""Tests for agent_hook module."""
import pytest


class TestAgentHookCreation:
    def test_import_agent_hook(self):
        from core.frameworks.agent_hook import AgentHook, AgentHookContext
        assert AgentHook is not None
        assert AgentHookContext is not None

    def test_context_dataclass(self):
        from core.frameworks.agent_hook import AgentHookContext
        ctx = AgentHookContext(iteration=1)
        assert ctx.iteration == 1

    def test_context_default_values(self):
        from core.frameworks.agent_hook import AgentHookContext
        ctx = AgentHookContext()
        assert ctx.iteration == 0
        assert ctx.tool_calls == []
        assert ctx.errors == []


class TestAgentHookMethods:
    def test_hook_has_before_iteration(self):
        from core.frameworks.agent_hook import AgentHook
        assert hasattr(AgentHook, 'before_iteration')

    def test_hook_has_after_iteration(self):
        from core.frameworks.agent_hook import AgentHook
        assert hasattr(AgentHook, 'after_iteration')

    def test_hook_has_on_tool_call(self):
        from core.frameworks.agent_hook import AgentHook
        assert hasattr(AgentHook, 'on_tool_call')

    def test_hook_has_on_error(self):
        from core.frameworks.agent_hook import AgentHook
        assert hasattr(AgentHook, 'on_error')

    def test_hook_has_on_complete(self):
        from core.frameworks.agent_hook import AgentHook
        assert hasattr(AgentHook, 'on_complete')