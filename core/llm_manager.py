"""
Multi-provider + multi-model LLM manager
Supports two-tier routing: provider layer + model layer
"""
import os
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelEntry:
    """Configuration entry for a single model"""
    model: str
    weight: int = 1
    capabilities: list = field(default_factory=list)
    max_tokens: int = 2000
    temperature: float = 0.7


@dataclass
class LLMProvider:
    """LLM Provider configuration"""
    name: str
    api_url: str
    api_key: str
    models: list[ModelEntry] = field(default_factory=list)
    timeout: int = 60
    default_model: str = ""
    enabled: bool = True

    def get_model(self, task_type: str = "general") -> ModelEntry:
        """Select appropriate model within this provider based on task_type"""
        for m in self.models:
            if task_type in m.capabilities:
                return m
        return self.models[0] if self.models else ModelEntry(model=self.default_model)


class LLMManager:
    """
    Multi-provider + multi-model LLM manager
    
    Core capabilities:
    1. Multi-provider support (volcengine/openai/anthropic/...)
    2. Multi-model support per provider (select by task_type)
    3. Two-tier routing: Provider layer + Model layer
    4. Concurrent request support
    """
    
    _instance: Optional["LLMManager"] = None
    
    def __init__(self, config: dict = None):
        config = config or {}
        self.providers: list[LLMProvider] = []
        self._init_providers(config.get("providers", {}))
        self.strategy = config.get("selection_strategy", "capability")
    
    @classmethod
    def get_instance(cls, config: dict = None) -> "LLMManager":
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)"""
        cls._instance = None
    
    def _init_providers(self, providers_config: dict):
        """Initialize all providers and their models"""
        for provider_name, cfg in providers_config.items():
            api_key = os.environ.get(f"{provider_name.upper()}_API_KEY") or cfg.get("api_key")
            if not api_key:
                print(f"[LLMManager] Skipping {provider_name}: no API key")
                continue
            
            models = []
            raw_models = cfg.get("models", [])
            
            # Backward compatibility: single model field
            if "model" in cfg and not raw_models:
                raw_models = [{"model": cfg["model"], "weight": cfg.get("weight", 1),
                               "capabilities": cfg.get("capabilities", ["general"])}]
            
            for m_cfg in raw_models:
                models.append(ModelEntry(
                    model=m_cfg.get("model", ""),
                    weight=m_cfg.get("weight", 1),
                    capabilities=m_cfg.get("capabilities", ["general"]),
                    max_tokens=m_cfg.get("max_tokens", 2000),
                    temperature=m_cfg.get("temperature", 0.7),
                ))
            
            provider = LLMProvider(
                name=provider_name,
                api_url=cfg.get("api_url", ""),
                api_key=api_key,
                models=models,
                timeout=cfg.get("timeout", 60),
                default_model=models[0].model if models else "",
                enabled=cfg.get("enabled", True),
            )
            self.providers.append(provider)
        
        if not self.providers:
            print("[LLMManager] Warning: No LLM providers configured")
    
    def select(self, task_type: str = "general") -> tuple[LLMProvider, ModelEntry]:
        """Select (provider, model) based on strategy"""
        if len(self.providers) == 1 and len(self.providers[0].models) == 1:
            p = self.providers[0]
            return p, p.models[0]
        
        if self.strategy == "capability":
            return self._capability_based(task_type)
        else:
            return self._weighted_rr(task_type)
    
    def _capability_based(self, task_type: str) -> tuple[LLMProvider, ModelEntry]:
        """Capability-based selection"""
        for p in self.providers:
            if not p.enabled:
                continue
            model = p.get_model(task_type)
            if model and task_type in model.capabilities:
                return p, model
        return self._weighted_rr(task_type)
    
    def _weighted_rr(self, task_type: str = "general") -> tuple[LLMProvider, ModelEntry]:
        """Weighted round-robin"""
        candidates = []
        for p in self.providers:
            if not p.enabled:
                continue
            for m in p.models:
                weight = self._get_provider_weight(p.name) * m.weight
                candidates.append((p, m, weight))
        
        if not candidates:
            raise ValueError("No available LLM providers")
        
        total_weight = sum(c[2] for c in candidates)
        r = random.randint(1, total_weight)
        cumsum = 0
        for p, m, w in candidates:
            cumsum += w
            if r <= cumsum:
                return p, m
        return candidates[-1][:2]
    
    def _get_provider_weight(self, provider_name: str) -> int:
        """Get provider weight"""
        for p in self.providers:
            if p.name == provider_name:
                return sum(m.weight for m in p.models) if p.models else 1
        return 1
    
    def chat(self, prompt: str, task_type: str = "general",
             model_override: str = None, provider_override: str = None,
             **kwargs) -> str:
        """Send request to selected provider + model"""
        if provider_override:
            provider = next((p for p in self.providers if p.name == provider_override), None)
            if not provider:
                raise ValueError(f"Provider {provider_override} not found")
            if model_override:
                model = next((m for m in provider.models if m.model == model_override), None)
                if not model:
                    raise ValueError(f"Model {model_override} not found in {provider_override}")
            else:
                model = provider.get_model(task_type)
        else:
            provider, model = self.select(task_type)
            if model_override:
                model = next((m for m in provider.models if m.model == model_override), model)
        
        temperature = kwargs.pop("temperature", model.temperature)
        max_tokens = kwargs.pop("max_tokens", model.max_tokens)
        
        import requests
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        response = requests.post(
            provider.api_url,
            headers=headers,
            json=payload,
            timeout=provider.timeout
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    
    def chat_batch(self, prompts: list, task_type: str = "general",
                   max_workers: int = 3, **kwargs) -> list:
        """Send multiple LLM requests concurrently"""
        import concurrent.futures
        
        results = [None] * len(prompts)
        assignments = self._assign_to_providers(len(prompts), task_type)
        
        def send_request(idx: int, provider_name: str, model_name: str, prompt: str):
            return idx, self.chat(prompt, provider_override=provider_name,
                                  model_override=model_name, **kwargs)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for idx, (p_name, m_name) in enumerate(assignments):
                futures.append(executor.submit(send_request, idx, p_name, m_name, prompts[idx]))
            
            for future in concurrent.futures.as_completed(futures):
                idx, result = future.result()
                results[idx] = result
        
        return results
    
    def _assign_to_providers(self, count: int, task_type: str) -> list:
        """Distribute N requests across different (provider, model) pairs"""
        assignments = []
        available = []
        
        for p in self.providers:
            if not p.enabled:
                continue
            for m in p.models:
                available.append((p.name, m.model, self._get_provider_weight(p.name) * m.weight))
        
        if not available:
            raise ValueError("No available LLM models")
        
        expanded = []
        for p_name, m_name, w in available:
            expanded.extend([(p_name, m_name)] * w)
        
        random.shuffle(expanded)
        
        for i in range(count):
            assignments.append(expanded[i % len(expanded)])
        
        return assignments
    
    def list_capabilities(self) -> dict:
        """List all provider and model capabilities"""
        result = {}
        for p in self.providers:
            result[p.name] = {
                "api_url": p.api_url,
                "models": {}
            }
            for m in p.models:
                result[p.name]["models"][m.model] = {
                    "capabilities": m.capabilities,
                    "weight": m.weight
                }
        return result
