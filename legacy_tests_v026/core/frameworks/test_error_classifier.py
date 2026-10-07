"""Tests for error_classifier module (copied from Hermes)."""
import pytest
from core.frameworks.error_classifier import FailoverReason, ClassifiedError


class TestFailoverReason:
    """Test FailoverReason enum."""

    def test_enum_has_required_values(self):
        """Test all required failover reasons exist."""
        required = [
            "auth", "auth_permanent", "billing", "rate_limit",
            "overloaded", "server_error", "timeout",
            "context_overflow", "payload_too_large",
            "model_not_found", "format_error", "unknown"
        ]
        for reason in required:
            assert hasattr(FailoverReason, reason), f"Missing FailoverReason.{reason}"

    def test_enum_values_are_strings(self):
        """Test enum values are string identifiers."""
        assert FailoverReason.auth.value == "auth"
        assert FailoverReason.rate_limit.value == "rate_limit"


class TestClassifiedError:
    """Test ClassifiedError dataclass."""

    def test_create_basic_error(self):
        """Test creating a basic classified error."""
        error = ClassifiedError(
            reason=FailoverReason.timeout,
            message="Connection timeout"
        )
        assert error.reason == FailoverReason.timeout
        assert error.message == "Connection timeout"
        assert error.retryable is True  # Default value

    def test_create_error_with_all_fields(self):
        """Test creating error with all fields."""
        error = ClassifiedError(
            reason=FailoverReason.rate_limit,
            status_code=429,
            provider="openai",
            model="gpt-4",
            message="Rate limit exceeded",
            retryable=True,
            should_rotate_credential=True,
        )
        assert error.status_code == 429
        assert error.provider == "openai"
        assert error.should_rotate_credential is True


class TestErrorClassification:
    """Test error classification logic."""

    def test_classify_timeout_error(self):
        """Test timeout error classification."""
        from core.frameworks.error_classifier import classify_api_error
        import asyncio
        error = asyncio.TimeoutError("Connection timeout after 30s")
        result = classify_api_error(error)
        assert result.reason == FailoverReason.timeout

    def test_classify_api_error_imports(self):
        """Test classify_api_error can be imported."""
        from core.frameworks.error_classifier import classify_api_error
        assert classify_api_error is not None