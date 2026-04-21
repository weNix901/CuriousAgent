"""Tests for DeepReadDaemon (v0.3.3)."""
import pytest
from core.daemon.deep_read_daemon import DeepReadDaemon, DeepReadDaemonConfig


class TestDeepReadDaemonConfig:
    def test_default_config(self):
        """Test default daemon configuration."""
        config = DeepReadDaemonConfig()
        assert config.poll_interval_seconds == 1800.0
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 15.0
        assert config.enabled is True
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = DeepReadDaemonConfig(
            poll_interval_seconds=3600,
            enabled=False
        )
        assert config.poll_interval_seconds == 3600
        assert config.enabled is False


class TestDeepReadDaemon:
    def test_daemon_inherits_thread(self):
        """Test that DeepReadDaemon inherits threading.Thread."""
        import threading
        assert issubclass(DeepReadDaemon, threading.Thread)
    
    def test_daemon_has_required_methods(self):
        """Test that DeepReadDaemon has required methods."""
        config = DeepReadDaemonConfig()
        daemon = DeepReadDaemon(deep_read_agent=None, config=config)
        assert hasattr(daemon, 'stop')
        assert hasattr(daemon, 'run')
        assert hasattr(daemon, '_tick')
        assert callable(daemon.stop)
    
    def test_daemon_stop_sets_running_false(self):
        """Test that stop sets running to False."""
        config = DeepReadDaemonConfig()
        daemon = DeepReadDaemon(deep_read_agent=None, config=config)
        assert daemon.running is True
        daemon.stop()
        assert daemon.running is False
    
    def test_daemon_name(self):
        """Test daemon thread name."""
        config = DeepReadDaemonConfig()
        daemon = DeepReadDaemon(deep_read_agent=None, config=config)
        assert daemon.name == "deep_read_daemon"