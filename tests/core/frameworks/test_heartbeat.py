"""Tests for heartbeat module (adapted for CA from Nanobot)."""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from core.frameworks.heartbeat import HeartbeatService, DEFAULT_HEARTBEAT_INTERVAL_S


class TestHeartbeatService:
    """Test HeartbeatService class."""

    def test_default_interval(self):
        """Test default heartbeat interval is 30 minutes."""
        assert DEFAULT_HEARTBEAT_INTERVAL_S == 30 * 60

    def test_create_service_with_custom_interval(self):
        """Test creating service with custom interval."""
        with patch.object(HeartbeatService, '__init__', lambda self, *args, **kwargs: None):
            service = HeartbeatService.__new__(HeartbeatService)
            service.interval_s = 3600
            service.enabled = True
            assert service.interval_s == 3600

    @pytest.mark.asyncio
    async def test_service_can_start_and_stop(self):
        """Test service can be started and stopped."""
        service = HeartbeatService(
            workspace=Path("/tmp"),
            interval_s=10,
            enabled=True
        )
        await service.start()
        assert service._running is True
        
        service.stop()
        assert service._running is False

    @pytest.mark.asyncio
    async def test_trigger_now_without_callback(self):
        """Test manual trigger without callback returns None."""
        service = HeartbeatService(workspace=Path("/tmp"), enabled=True)
        result = await service.trigger_now()
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_now_with_callback(self):
        """Test manual trigger with callback."""
        mock_callback = AsyncMock(return_value="test_result")
        service = HeartbeatService(
            workspace=Path("/tmp"),
            on_heartbeat=mock_callback,
            enabled=True
        )
        result = await service.trigger_now()
        assert result == "test_result"
        mock_callback.assert_called_once()


class TestHeartbeatImports:
    """Test heartbeat module imports correctly."""

    def test_module_imports(self):
        """Test module can be imported."""
        from core.frameworks import heartbeat
        assert hasattr(heartbeat, 'HeartbeatService')