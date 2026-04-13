"""LLM providers configuration."""
from dataclasses import dataclass, field
from typing import List, Optional
import os


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    name: str
    api_url: str
    api_key_env: str
    models: List[str] = field(default_factory=list)
    priority: int = 1
    timeout: int = 60
    enabled: bool = True

    def get_api_key(self) -> Optional[str]:
        """Get API key from environment variable."""
        return os.environ.get(self.api_key_env)


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    model: str
    weight: int = 1
    max_tokens: int = 2000
    capabilities: List[str] = field(default_factory=list)


DEFAULT_PROVIDERS = [
    ProviderConfig(
        name="volcengine",
        api_url="https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
        api_key_env="VOLCENGINE_API_KEY",
        models=["ark-code-latest"],
        priority=1,
        enabled=True,
    ),
    ProviderConfig(
        name="minimax",
        api_url="https://api.minimax.chat/v1/chat/completions",
        api_key_env="MINIMAX_API_KEY",
        models=["abab6.5-chat"],
        priority=2,
        enabled=True,
    ),
]


class LLMProvidersConfig:
    """Configuration for multiple LLM providers."""

    def __init__(self, providers: List[ProviderConfig] = None):
        self.providers = providers or DEFAULT_PROVIDERS

    def get_provider_by_priority(self) -> Optional[ProviderConfig]:
        """Get the highest priority enabled provider."""
        enabled = [p for p in self.providers if p.enabled and p.get_api_key()]
        if not enabled:
            return None
        return min(enabled, key=lambda p: p.priority)

    def get_provider_by_name(self, name: str) -> Optional[ProviderConfig]:
        """Get provider by name."""
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None

    def get_fallback_provider(self, exclude_name: str) -> Optional[ProviderConfig]:
        """Get fallback provider excluding the given name."""
        enabled = [
            p for p in self.providers
            if p.enabled and p.name != exclude_name and p.get_api_key()
        ]
        if not enabled:
            return None
        return min(enabled, key=lambda p: p.priority)