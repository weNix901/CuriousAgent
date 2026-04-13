"""Tests for LLM providers configuration."""
import pytest
from unittest.mock import patch


class TestProviderConfig:
    """Tests for ProviderConfig."""

    def test_import_provider_config(self):
        from core.configs.llm_providers import ProviderConfig
        assert ProviderConfig is not None

    def test_provider_config_has_name(self):
        from core.configs.llm_providers import ProviderConfig
        provider = ProviderConfig(name="test", api_url="http://test", api_key_env="TEST_KEY")
        assert provider.name == "test"

    def test_provider_config_get_api_key(self):
        from core.configs.llm_providers import ProviderConfig
        provider = ProviderConfig(name="test", api_url="http://test", api_key_env="TEST_KEY")
        with patch.dict('os.environ', {'TEST_KEY': 'secret'}):
            assert provider.get_api_key() == 'secret'

    def test_provider_config_missing_api_key(self):
        from core.configs.llm_providers import ProviderConfig
        provider = ProviderConfig(name="test", api_url="http://test", api_key_env="MISSING_KEY")
        assert provider.get_api_key() is None


class TestLLMProvidersConfig:
    """Tests for LLMProvidersConfig."""

    def test_import_llm_providers_config(self):
        from core.configs.llm_providers import LLMProvidersConfig
        assert LLMProvidersConfig is not None

    def test_llm_config_has_default_providers(self):
        from core.configs.llm_providers import LLMProvidersConfig
        config = LLMProvidersConfig()
        assert len(config.providers) >= 2

    def test_get_provider_by_priority(self):
        from core.configs.llm_providers import LLMProvidersConfig, ProviderConfig
        providers = [
            ProviderConfig(name="low", api_url="http://low", api_key_env="LOW_KEY", priority=2),
            ProviderConfig(name="high", api_url="http://high", api_key_env="HIGH_KEY", priority=1),
        ]
        config = LLMProvidersConfig(providers)
        with patch.dict('os.environ', {'LOW_KEY': 'key1', 'HIGH_KEY': 'key2'}):
            result = config.get_provider_by_priority()
            assert result.name == "high"

    def test_get_provider_by_name(self):
        from core.configs.llm_providers import LLMProvidersConfig
        config = LLMProvidersConfig()
        result = config.get_provider_by_name("volcengine")
        assert result is not None
        assert result.name == "volcengine"

    def test_get_fallback_provider(self):
        from core.configs.llm_providers import LLMProvidersConfig, ProviderConfig
        providers = [
            ProviderConfig(name="primary", api_url="http://p", api_key_env="P_KEY", priority=1),
            ProviderConfig(name="fallback", api_url="http://f", api_key_env="F_KEY", priority=2),
        ]
        config = LLMProvidersConfig(providers)
        with patch.dict('os.environ', {'P_KEY': 'key1', 'F_KEY': 'key2'}):
            result = config.get_fallback_provider("primary")
            assert result.name == "fallback"

    def test_volcengine_is_primary(self):
        from core.configs.llm_providers import LLMProvidersConfig
        config = LLMProvidersConfig()
        volcengine = config.get_provider_by_name("volcengine")
        assert volcengine.priority == 1