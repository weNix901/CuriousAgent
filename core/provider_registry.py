"""Provider Registry - Singleton pattern for managing search providers"""
import os
from typing import Optional

from core.search_provider import SearchProvider
from core.providers import BochaSearchProvider, SerperProvider


class ProviderRegistry:
    """Singleton registry for search providers"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers: dict[str, SearchProvider] = {}
        return cls._instance
    
    def register(self, provider: SearchProvider) -> None:
        """Register a provider"""
        self._providers[provider.name] = provider
    
    def get(self, name: str) -> Optional[SearchProvider]:
        """Get provider by name"""
        return self._providers.get(name)
    
    def get_all(self) -> list[SearchProvider]:
        """Get all registered providers"""
        return list(self._providers.values())
    
    def get_enabled(self) -> list[SearchProvider]:
        """Get enabled providers based on configuration"""
        enabled = []
        config = self._load_config()
        
        for name, provider in self._providers.items():
            if config.get(name, {}).get("enabled", False):
                enabled.append(provider)
        
        return enabled
    
    def _load_config(self) -> dict:
        """Load provider configuration"""
        # Simple env-based config for now
        return {
            "bocha": {"enabled": bool(os.environ.get("BOCHA_API_KEY"))},
            "serper": {"enabled": bool(os.environ.get("SERPER_API_KEY"))},
        }
    
    def reset(self) -> None:
        """Reset registry (for testing)"""
        self._providers.clear()


# Global registry instance
def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry()


def init_default_providers() -> ProviderRegistry:
    """Initialize registry with default providers (Bocha + Serper)"""
    registry = get_provider_registry()
    registry.reset()
    
    # Register Bocha if API key available
    bocha_key = os.environ.get("BOCHA_API_KEY")
    if bocha_key:
        registry.register(BochaSearchProvider(bocha_key))
    
    # Register Serper if API key available
    serper_key = os.environ.get("SERPER_API_KEY")
    if serper_key:
        registry.register(SerperProvider(serper_key))
    
    return registry
