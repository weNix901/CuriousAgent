"""Tests for DreamDaemon - heartbeat-triggered DreamAgent execution."""
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import will fail until DreamDaemon is implemented - this is expected in RED phase
from core.daemon.dream_daemon import DreamDaemon, DreamDaemonConfig
from core.frameworks.heartbeat import HeartbeatService


class TestDreamDaemonConfig:
    """Tests for DreamDaemonConfig dataclass."""

    def test_default_interval_is_6_hours(self):
        """Default heartbeat interval should be 6 hours (21600 seconds)."""
        config = DreamDaemonConfig()
        assert config.interval_seconds == 6 * 60 * 60

    def test_custom_interval_can_be_set(self):
        """Custom interval can be configured."""
        config = DreamDaemonConfig(interval_seconds=3600)
        assert config.interval_seconds == 3600

    def test_enabled_by_default(self):
        """Daemon should be enabled by default."""
        config = DreamDaemonConfig()
        assert config.enabled is True

    def test_can_be_disabled(self):
        """Daemon can be disabled via config."""
        config = DreamDaemonConfig(enabled=False)
        assert config.enabled is False


class TestDreamDaemonInit:
    """Tests for DreamDaemon initialization."""

    def test_creates_heartbeat_service(self):
        """DreamDaemon should create HeartbeatService with correct interval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig(interval_seconds=3600)
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            assert daemon.heartbeat is not None
            assert isinstance(daemon.heartbeat, HeartbeatService)
            assert daemon.heartbeat.interval_s == 3600

    def test_creates_dream_agent(self):
        """DreamDaemon should create DreamAgent instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig()
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            assert daemon.agent is not None

    def test_uses_workspace_path(self):
        """DreamDaemon should use provided workspace path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig()
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            assert daemon.workspace == workspace


class TestDreamDaemonLifecycle:
    """Tests for DreamDaemon start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_begins_heartbeat(self):
        """Starting daemon should start heartbeat service."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig(interval_seconds=60)  # Short interval for testing
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            # Mock the heartbeat start to avoid actual async loop
            with patch.object(daemon.heartbeat, 'start', new_callable=AsyncMock) as mock_start:
                await daemon.start()
                mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_stops_heartbeat(self):
        """Stopping daemon should stop heartbeat service."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig()
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            # Mock heartbeat
            daemon.heartbeat.stop = MagicMock()
            
            daemon.stop()
            
            daemon.heartbeat.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_disabled_daemon_does_not_start_heartbeat(self):
        """Disabled daemon should not start heartbeat."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig(enabled=False)
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            with patch.object(daemon.heartbeat, 'start', new_callable=AsyncMock) as mock_start:
                await daemon.start()
                mock_start.assert_not_called()


class TestDreamDaemonHeartbeatCallback:
    """Tests for DreamDaemon heartbeat callback behavior."""

    @pytest.mark.asyncio
    async def test_heartbeat_triggers_dream_agent_run(self):
        """Heartbeat callback should trigger DreamAgent.run()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig()
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            # Mock DreamAgent.run
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.topics_generated = ["topic1", "topic2"]
            
            with patch.object(daemon.agent, 'run', return_value=mock_result) as mock_run:
                result = await daemon._on_heartbeat("test prompt")
                
                mock_run.assert_called_once()
                assert result is not None

    @pytest.mark.asyncio
    async def test_heartbeat_returns_result_content(self):
        """Heartbeat callback should return result content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig()
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            mock_result = MagicMock()
            mock_result.content = "DreamAgent generated 2 topics"
            mock_result.success = True
            
            with patch.object(daemon.agent, 'run', return_value=mock_result):
                result = await daemon._on_heartbeat("test prompt")
                
                assert result == "DreamAgent generated 2 topics"


class TestDreamDaemonGracefulShutdown:
    """Tests for graceful shutdown behavior."""

    def test_stop_is_graceful(self):
        """Stop should be graceful (no forceful termination)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig()
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            # Should not raise any exceptions
            daemon.stop()
            
            assert not daemon._running

    @pytest.mark.asyncio
    async def test_can_restart_after_stop(self):
        """Daemon can be restarted after being stopped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            config = DreamDaemonConfig(interval_seconds=60)
            
            daemon = DreamDaemon(workspace=workspace, config=config)
            
            # Start and stop
            with patch.object(daemon.heartbeat, 'start', new_callable=AsyncMock):
                await daemon.start()
            daemon.stop()
            
            # Should be able to restart
            with patch.object(daemon.heartbeat, 'start', new_callable=AsyncMock) as mock_start:
                await daemon.start()
                mock_start.assert_called_once()