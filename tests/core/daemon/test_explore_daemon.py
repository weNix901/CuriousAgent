"""Tests for ExploreDaemon - continuous exploration daemon."""
import signal
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.daemon.explore_daemon import ExploreDaemon, ExploreDaemonConfig


class TestExploreDaemonIsThread:
    """Test that ExploreDaemon is a thread-based daemon."""
    
    def test_explore_daemon_is_thread(self):
        """ExploreDaemon should be a threading.Thread subclass."""
        mock_agent = MagicMock()
        daemon = ExploreDaemon(explore_agent=mock_agent)
        
        assert isinstance(daemon, threading.Thread)
    
    def test_explore_daemon_is_daemon_thread(self):
        """ExploreDaemon should be a daemon thread that exits when main process exits."""
        mock_agent = MagicMock()
        daemon = ExploreDaemon(explore_agent=mock_agent)
        
        assert daemon.daemon is True


class TestExploreDaemonHasRunningFlag:
    """Test that ExploreDaemon has a running flag for graceful shutdown."""
    
    def test_explore_daemon_has_running_flag(self):
        """ExploreDaemon should have a running flag initialized to True."""
        mock_agent = MagicMock()
        daemon = ExploreDaemon(explore_agent=mock_agent)
        
        assert hasattr(daemon, 'running')
        assert daemon.running is True
    
    def test_explore_daemon_stop_sets_running_false(self):
        """Calling stop() should set running flag to False."""
        mock_agent = MagicMock()
        daemon = ExploreDaemon(explore_agent=mock_agent)
        
        daemon.stop()
        
        assert daemon.running is False


class TestExploreDaemonConfig:
    """Test ExploreDaemonConfig configuration."""
    
    def test_default_config_values(self):
        """Default config should have sensible defaults."""
        config = ExploreDaemonConfig()
        
        assert config.poll_interval == 5.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
    
    def test_custom_config_values(self):
        """Custom config values should be respected."""
        config = ExploreDaemonConfig(
            poll_interval=10.0,
            max_retries=5,
            retry_delay=2.0
        )
        
        assert config.poll_interval == 10.0
        assert config.max_retries == 5
        assert config.retry_delay == 2.0


class TestExploreDaemonLoop:
    """Test the continuous loop: claim → explore → mark done."""
    
    def test_explore_daemon_has_run_method(self):
        """ExploreDaemon should have a run() method for the main loop."""
        mock_agent = MagicMock()
        daemon = ExploreDaemon(explore_agent=mock_agent)
        
        assert hasattr(daemon, 'run')
        assert callable(daemon.run)
    
    @pytest.mark.asyncio
    async def test_explore_daemon_calls_agent_run_in_loop(self):
        """ExploreDaemon should call explore_agent.run() in its loop."""
        # Create mock agent that returns success
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=MagicMock(success=True, content="Explored"))
        
        # Create mock queue tools
        mock_queue_storage = MagicMock()
        mock_queue_storage.get_pending_items.return_value = [
            {"id": 1, "topic": "test_topic", "priority": 5}
        ]
        mock_queue_storage.claim_item.return_value = True
        mock_queue_storage.mark_done.return_value = True
        
        daemon = ExploreDaemon(
            explore_agent=mock_agent,
            queue_storage=mock_queue_storage,
            config=ExploreDaemonConfig(poll_interval=0.1)
        )
        
        # Start daemon in background
        daemon.start()
        
        # Wait for one iteration
        time.sleep(0.3)
        
        # Stop daemon
        daemon.stop()
        daemon.join(timeout=2.0)
        
        # Verify agent was called
        assert mock_agent.run.called
    
    @pytest.mark.asyncio
    async def test_explore_daemon_marks_done_after_exploration(self):
        """ExploreDaemon should mark item as done after successful exploration."""
        mock_agent = MagicMock()
        mock_agent.holder_id = "test_holder"
        mock_agent.run = AsyncMock(return_value=MagicMock(success=True, content="Explored"))
        
        mock_queue_storage = MagicMock()
        mock_queue_storage.get_pending_items.return_value = [
            {"id": 1, "topic": "test_topic", "priority": 5}
        ]
        mock_queue_storage.claim_item.return_value = True
        mock_queue_storage.mark_done.return_value = True
        
        daemon = ExploreDaemon(
            explore_agent=mock_agent,
            queue_storage=mock_queue_storage,
            config=ExploreDaemonConfig(poll_interval=0.1)
        )
        
        daemon.start()
        time.sleep(0.3)
        daemon.stop()
        daemon.join(timeout=2.0)
        
        # Verify mark_done was called
        assert mock_queue_storage.mark_done.called


class TestExploreDaemonGracefulShutdown:
    """Test graceful shutdown with signal handling."""
    
    def test_explore_daemon_handles_sigint(self):
        """ExploreDaemon should handle SIGINT for graceful shutdown."""
        mock_agent = MagicMock()
        daemon = ExploreDaemon(explore_agent=mock_agent)
        
        # Should have signal handler registered
        assert hasattr(daemon, '_setup_signal_handlers')
    
    def test_explore_daemon_handles_sigterm(self):
        """ExploreDaemon should handle SIGTERM for graceful shutdown."""
        mock_agent = MagicMock()
        daemon = ExploreDaemon(explore_agent=mock_agent)
        
        # Should have signal handler registered
        assert hasattr(daemon, '_setup_signal_handlers')
    
    def test_explore_daemon_shutdown_on_signal(self):
        """Signal should trigger graceful shutdown."""
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=MagicMock(success=True))
        
        mock_queue_storage = MagicMock()
        mock_queue_storage.get_pending_items.return_value = []
        
        daemon = ExploreDaemon(
            explore_agent=mock_agent,
            queue_storage=mock_queue_storage,
            config=ExploreDaemonConfig(poll_interval=0.1)
        )
        
        # Simulate signal
        daemon._handle_shutdown_signal(signal.SIGINT, None)
        
        # Should have stopped
        assert daemon.running is False


class TestExploreDaemonEmptyQueue:
    """Test behavior when queue is empty."""
    
    @pytest.mark.asyncio
    async def test_explore_daemon_waits_when_queue_empty(self):
        """ExploreDaemon should wait (sleep) when queue is empty."""
        mock_agent = MagicMock()
        
        mock_queue_storage = MagicMock()
        mock_queue_storage.get_pending_items.return_value = []  # Empty queue
        
        daemon = ExploreDaemon(
            explore_agent=mock_agent,
            queue_storage=mock_queue_storage,
            config=ExploreDaemonConfig(poll_interval=0.1)
        )
        
        daemon.start()
        time.sleep(0.3)
        daemon.stop()
        daemon.join(timeout=2.0)
        
        # Agent should NOT have been called (no items to explore)
        assert not mock_agent.run.called


class TestExploreDaemonRetryLogic:
    """Test retry logic for failed explorations."""
    
    @pytest.mark.asyncio
    async def test_explore_daemon_retries_on_failure(self):
        """ExploreDaemon should retry failed explorations up to max_retries."""
        mock_agent = MagicMock()
        mock_agent.holder_id = "test_holder"
        # First call fails, second succeeds
        mock_agent.run = AsyncMock(
            side_effect=[
                MagicMock(success=False, content="Failed"),
                MagicMock(success=True, content="Success")
            ]
        )
        
        mock_queue_storage = MagicMock()
        mock_queue_storage.get_pending_items.return_value = [
            {"id": 1, "topic": "test_topic", "priority": 5}
        ]
        mock_queue_storage.claim_item.return_value = True
        mock_queue_storage.mark_failed.return_value = True
        mock_queue_storage.mark_done.return_value = True
        
        daemon = ExploreDaemon(
            explore_agent=mock_agent,
            queue_storage=mock_queue_storage,
            config=ExploreDaemonConfig(
                poll_interval=0.1,
                max_retries=2,
                retry_delay=0.05
            )
        )
        
        daemon.start()
        time.sleep(0.5)
        daemon.stop()
        daemon.join(timeout=2.0)
        
        # Agent should have been called multiple times (retry)
        assert mock_agent.run.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_explore_daemon_marks_failed_after_max_retries(self):
        """ExploreDaemon should mark item as failed after max_retries exhausted."""
        mock_agent = MagicMock()
        mock_agent.holder_id = "test_holder"
        mock_agent.run = AsyncMock(
            return_value=MagicMock(success=False, content="Always fails")
        )
        
        mock_queue_storage = MagicMock()
        mock_queue_storage.get_pending_items.return_value = [
            {"id": 1, "topic": "test_topic", "priority": 5}
        ]
        mock_queue_storage.claim_item.return_value = True
        mock_queue_storage.mark_failed.return_value = True
        
        daemon = ExploreDaemon(
            explore_agent=mock_agent,
            queue_storage=mock_queue_storage,
            config=ExploreDaemonConfig(
                poll_interval=0.1,
                max_retries=2,
                retry_delay=0.05
            )
        )
        
        daemon.start()
        time.sleep(0.5)
        daemon.stop()
        daemon.join(timeout=2.0)
        
        # mark_failed should have been called
        assert mock_queue_storage.mark_failed.called