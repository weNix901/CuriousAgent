import pytest
from core.provider_registry import ProviderRegistry, get_provider_registry
from core.providers.bocha_provider import BochaSearchProvider


def test_singleton():
    r1 = get_provider_registry()
    r2 = get_provider_registry()
    assert r1 is r2


def test_register_and_get():
    registry = ProviderRegistry()
    registry.reset()
    
    provider = BochaSearchProvider(api_key="test")
    registry.register(provider)
    
    assert registry.get("bocha") is provider
    assert len(registry.get_all()) == 1
