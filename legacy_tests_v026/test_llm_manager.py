# tests/test_llm_manager.py
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.llm_manager import ModelEntry, LLMProvider, LLMManager


class TestModelEntry:
    def test_model_entry_defaults(self):
        entry = ModelEntry(model="test-model")
        assert entry.model == "test-model"
        assert entry.weight == 1
        assert entry.capabilities == []
        assert entry.max_tokens == 2000
        assert entry.temperature == 0.7
    
    def test_model_entry_custom(self):
        entry = ModelEntry(
            model="gpt-4",
            weight=3,
            capabilities=["fast", "keywords"],
            max_tokens=4000,
            temperature=0.5
        )
        assert entry.weight == 3
        assert entry.capabilities == ["fast", "keywords"]


class TestLLMProvider:
    def test_provider_get_model_by_capability(self):
        models = [
            ModelEntry(model="fast-model", capabilities=["fast", "keywords"]),
            ModelEntry(model="slow-model", capabilities=["reasoning"]),
        ]
        provider = LLMProvider(
            name="test",
            api_url="http://test.com",
            api_key="test-key",
            models=models
        )
        
        # Should find by capability
        model = provider.get_model("keywords")
        assert model.model == "fast-model"
        
        # Should fallback to first
        model = provider.get_model("unknown")
        assert model.model == "fast-model"


class TestLLMManager:
    def test_singleton_pattern(self):
        LLMManager.reset_instance()
        m1 = LLMManager.get_instance()
        m2 = LLMManager.get_instance()
        assert m1 is m2
    
    def test_list_capabilities_empty(self):
        LLMManager.reset_instance()
        manager = LLMManager.get_instance({})
        caps = manager.list_capabilities()
        assert caps == {}
    
    def test_select_with_single_provider(self):
        LLMManager.reset_instance()
        config = {
            "providers": {
                "test": {
                    "api_url": "http://test.com",
                    "api_key": "test-key",
                    "models": [{"model": "test-model", "weight": 1}]
                }
            }
        }
        manager = LLMManager.get_instance(config)
        provider, model = manager.select("general")
        assert provider.name == "test"
        assert model.model == "test-model"
