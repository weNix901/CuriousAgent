"""Tests for agent_runner module."""
import pytest
from core.frameworks.agent_runner import AgentRunSpec, AgentRunResult


class TestAgentRunSpec:
    def test_create_with_content(self):
        spec = AgentRunSpec(content="test prompt")
        assert spec.content == "test prompt"
        assert spec.session_key == "default"
        assert spec.max_iterations == 20

    def test_create_with_custom_iterations(self):
        spec = AgentRunSpec(content="test", max_iterations=5)
        assert spec.max_iterations == 5

    def test_create_with_model(self):
        spec = AgentRunSpec(content="test", model="doubao-pro")
        assert spec.model == "doubao-pro"


class TestAgentRunResult:
    def test_create_success_result(self):
        result = AgentRunResult(
            content="response",
            session_key="test",
            iterations_used=3,
            success=True
        )
        assert result.success is True
        assert result.error is None

    def test_create_failure_result(self):
        result = AgentRunResult(
            content="",
            session_key="test",
            iterations_used=10,
            success=False,
            error="Max iterations exceeded"
        )
        assert result.success is False
        assert result.error == "Max iterations exceeded"


class TestImports:
    def test_module_imports(self):
        from core.frameworks import agent_runner
        assert hasattr(agent_runner, 'AgentRunSpec')
        assert hasattr(agent_runner, 'AgentRunResult')