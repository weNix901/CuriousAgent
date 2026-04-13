"""Tests for retry_utils module (copied from Hermes)."""
import pytest
from core.frameworks.retry_utils import jittered_backoff


class TestJitteredBackoff:
    """Test jittered exponential backoff."""

    def test_first_attempt_returns_base_delay(self):
        """Test attempt 1 returns approximately base delay."""
        delay = jittered_backoff(1, base_delay=5.0)
        # With jitter, delay should be around base_delay
        assert 2.5 <= delay <= 7.5  # base_delay ± jitter_ratio * base_delay

    def test_delay_increases_with_attempts(self):
        """Test delay increases exponentially with attempts."""
        delays = [jittered_backoff(i, base_delay=1.0) for i in range(1, 6)]
        # Later attempts should generally have larger delays
        # Note: jitter makes this probabilistic, so we check trend
        avg_delay_1 = sum(delays[:2]) / 2
        avg_delay_5 = sum(delays[4:]) / 2
        assert avg_delay_5 > avg_delay_1

    def test_delay_capped_at_max_with_jitter(self):
        """Test delay is capped at max_delay plus jitter."""
        delay = jittered_backoff(100, base_delay=1.0, max_delay=60.0, jitter_ratio=0.5)
        assert delay <= 90.0  # max_delay + jitter_ratio * max_delay

    def test_jitter_ratio_effect(self):
        """Test jitter_ratio affects randomness."""
        # No jitter - should be deterministic
        delays_no_jitter = [
            jittered_backoff(1, base_delay=5.0, jitter_ratio=0.0)
            for _ in range(10)
        ]
        assert all(d == delays_no_jitter[0] for d in delays_no_jitter)

        # High jitter - should vary
        delays_high_jitter = [
            jittered_backoff(1, base_delay=5.0, jitter_ratio=0.5)
            for _ in range(10)
        ]
        # At least some should differ
        assert len(set(delays_high_jitter)) > 1


class TestRetryUtilsImports:
    """Test retry_utils module imports correctly."""

    def test_module_imports(self):
        """Test module can be imported."""
        from core.frameworks import retry_utils
        assert hasattr(retry_utils, 'jittered_backoff')