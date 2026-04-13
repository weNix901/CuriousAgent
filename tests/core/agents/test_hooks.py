"""Tests for Agent Hooks (ExploreHook and DreamHook)."""
import pytest
from unittest.mock import MagicMock, patch
from core.frameworks.agent_hook import AgentHookContext


class TestExploreHookImport:
    """Test ExploreHook import and basic structure."""

    def test_explore_hook_importable(self):
        """ExploreHook should be importable from core.agents.hooks.explore_hook."""
        from core.agents.hooks.explore_hook import ExploreHook
        assert ExploreHook is not None

    def test_explore_hook_inherits_from_agent_hook(self):
        """ExploreHook should inherit from AgentHook."""
        from core.agents.hooks.explore_hook import ExploreHook
        from core.frameworks.agent_hook import AgentHook
        
        assert issubclass(ExploreHook, AgentHook)


class TestExploreHookBeforeIteration:
    """Test ExploreHook.before_iteration method."""

    def test_before_iteration_logs_exploration_start(self):
        """before_iteration should log exploration start with iteration number."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        context = AgentHookContext(iteration=1)
        
        with patch('core.agents.hooks.explore_hook.logger') as mock_logger:
            hook.before_iteration(context)
            mock_logger.info.assert_called()
            # Should log iteration number
            call_args = mock_logger.info.call_args[0][0]
            assert 'iteration' in call_args.lower() or 'exploration' in call_args.lower()

    def test_before_iteration_accepts_context(self):
        """before_iteration should accept AgentHookContext."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        context = AgentHookContext(iteration=5, metadata={'topic': 'test_topic'})
        
        # Should not raise
        hook.before_iteration(context)


class TestExploreHookAfterIteration:
    """Test ExploreHook.after_iteration method."""

    def test_after_iteration_logs_progress(self):
        """after_iteration should log exploration progress."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        context = AgentHookContext(
            iteration=2,
            tool_calls=[{'name': 'search', 'params': {}}]
        )
        
        with patch('core.agents.hooks.explore_hook.logger') as mock_logger:
            hook.after_iteration(context)
            mock_logger.info.assert_called()

    def test_after_iteration_quality_check(self):
        """after_iteration should perform quality check on context."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        context = AgentHookContext(
            iteration=3,
            result={'quality': 8.5},
            metadata={'quality_score': 8.5}
        )
        
        # Should not raise
        hook.after_iteration(context)


class TestExploreHookOnToolCall:
    """Test ExploreHook.on_tool_call method."""

    def test_on_tool_call_tracks_tool_usage(self):
        """on_tool_call should track tool usage."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        
        with patch('core.agents.hooks.explore_hook.logger') as mock_logger:
            hook.on_tool_call('search', {'query': 'test'})
            mock_logger.debug.assert_called()

    def test_on_tool_call_accepts_tool_name_and_params(self):
        """on_tool_call should accept tool_name and params."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        
        # Should not raise
        hook.on_tool_call('read', {'path': '/test/file.py'})


class TestExploreHookOnError:
    """Test ExploreHook.on_error method."""

    def test_on_error_handles_exploration_errors(self):
        """on_error should handle exploration errors."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        error = Exception("Exploration failed")
        
        with patch('core.agents.hooks.explore_hook.logger') as mock_logger:
            hook.on_error(error)
            mock_logger.error.assert_called()

    def test_on_error_accepts_exception(self):
        """on_error should accept Exception."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        error = ValueError("Invalid query")
        
        # Should not raise
        hook.on_error(error)


class TestExploreHookOnComplete:
    """Test ExploreHook.on_complete method."""

    def test_on_complete_performs_quality_assessment(self):
        """on_complete should perform final quality assessment."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        result = {'quality': 8.5, 'findings': ['finding1', 'finding2']}
        
        with patch('core.agents.hooks.explore_hook.logger') as mock_logger:
            hook.on_complete(result)
            mock_logger.info.assert_called()

    def test_on_complete_accepts_result(self):
        """on_complete should accept result."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        result = {'topic': 'agent memory', 'quality': 7.5}
        
        # Should not raise
        hook.on_complete(result)


class TestDreamHookImport:
    """Test DreamHook import and basic structure."""

    def test_dream_hook_importable(self):
        """DreamHook should be importable from core.agents.hooks.dream_hook."""
        from core.agents.hooks.dream_hook import DreamHook
        assert DreamHook is not None

    def test_dream_hook_inherits_from_agent_hook(self):
        """DreamHook should inherit from AgentHook."""
        from core.agents.hooks.dream_hook import DreamHook
        from core.frameworks.agent_hook import AgentHook
        
        assert issubclass(DreamHook, AgentHook)


class TestDreamHookBeforeIteration:
    """Test DreamHook.before_iteration method."""

    def test_before_iteration_logs_phase(self):
        """before_iteration should log dream phase."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        context = AgentHookContext(iteration=1, metadata={'phase': 'association'})
        
        with patch('core.agents.hooks.dream_hook.logger') as mock_logger:
            hook.before_iteration(context)
            mock_logger.info.assert_called()
            # Should log phase
            call_args = mock_logger.info.call_args[0][0]
            assert 'phase' in call_args.lower() or 'dream' in call_args.lower()

    def test_before_iteration_accepts_context(self):
        """before_iteration should accept AgentHookContext."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        context = AgentHookContext(iteration=2, metadata={'phase': 'insight'})
        
        # Should not raise
        hook.before_iteration(context)


class TestDreamHookAfterIteration:
    """Test DreamHook.after_iteration method."""

    def test_after_iteration_checks_queue_persistence(self):
        """after_iteration should check queue persistence."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        context = AgentHookContext(
            iteration=1,
            metadata={'queue_size': 5}
        )
        
        with patch('core.agents.hooks.dream_hook.logger') as mock_logger:
            hook.after_iteration(context)
            mock_logger.debug.assert_called()

    def test_after_iteration_accepts_context(self):
        """after_iteration should accept AgentHookContext."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        context = AgentHookContext(iteration=3)
        
        # Should not raise
        hook.after_iteration(context)


class TestDreamHookOnToolCall:
    """Test DreamHook.on_tool_call method."""

    def test_on_tool_call_tracks_llm_calls(self):
        """on_tool_call should track LLM calls."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        
        with patch('core.agents.hooks.dream_hook.logger') as mock_logger:
            hook.on_tool_call('llm_generate', {'prompt': 'test'})
            mock_logger.debug.assert_called()

    def test_on_tool_call_accepts_tool_name_and_params(self):
        """on_tool_call should accept tool_name and params."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        
        # Should not raise
        hook.on_tool_call('associate', {'nodes': ['a', 'b']})


class TestDreamHookOnError:
    """Test DreamHook.on_error method."""

    def test_on_error_handles_phase_failures(self):
        """on_error should handle phase failures."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        error = Exception("Dream phase failed")
        
        with patch('core.agents.hooks.dream_hook.logger') as mock_logger:
            hook.on_error(error)
            mock_logger.error.assert_called()

    def test_on_error_accepts_exception(self):
        """on_error should accept Exception."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        error = RuntimeError("LLM timeout")
        
        # Should not raise
        hook.on_error(error)


class TestDreamHookOnComplete:
    """Test DreamHook.on_complete method."""

    def test_on_complete_logs_generated_topics(self):
        """on_complete should log generated topics."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        result = {'topics': ['topic1', 'topic2'], 'insights': ['insight1']}
        
        with patch('core.agents.hooks.dream_hook.logger') as mock_logger:
            hook.on_complete(result)
            mock_logger.info.assert_called()

    def test_on_complete_accepts_result(self):
        """on_complete should accept result."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        result = {'insights': ['cross-domain insight']}
        
        # Should not raise
        hook.on_complete(result)


class TestHookContextIntegration:
    """Test hooks with AgentHookContext integration."""

    def test_explore_hook_full_cycle(self):
        """ExploreHook should work through full cycle."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        context = AgentHookContext(iteration=1)
        
        # Full cycle
        hook.before_iteration(context)
        hook.on_tool_call('search', {'query': 'test'})
        hook.after_iteration(context)
        hook.on_complete({'quality': 8.0})
        
        # Should not raise

    def test_dream_hook_full_cycle(self):
        """DreamHook should work through full cycle."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        context = AgentHookContext(iteration=1)
        
        # Full cycle
        hook.before_iteration(context)
        hook.on_tool_call('associate', {'nodes': ['a', 'b']})
        hook.after_iteration(context)
        hook.on_complete({'topics': ['new_topic']})
        
        # Should not raise

    def test_explore_hook_error_handling_in_cycle(self):
        """ExploreHook should handle errors in cycle."""
        from core.agents.hooks.explore_hook import ExploreHook
        
        hook = ExploreHook()
        context = AgentHookContext(iteration=1)
        
        hook.before_iteration(context)
        hook.on_tool_call('search', {'query': 'test'})
        hook.on_error(Exception("Search failed"))
        hook.after_iteration(context)
        
        # Should not raise

    def test_dream_hook_error_handling_in_cycle(self):
        """DreamHook should handle errors in cycle."""
        from core.agents.hooks.dream_hook import DreamHook
        
        hook = DreamHook()
        context = AgentHookContext(iteration=1)
        
        hook.before_iteration(context)
        hook.on_error(RuntimeError("LLM timeout"))
        hook.after_iteration(context)
        
        # Should not raise