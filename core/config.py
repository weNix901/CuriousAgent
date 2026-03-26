import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MetaCognitiveThresholds:
    max_explore_count: int = 3
    min_marginal_return: float = 0.3
    high_quality_threshold: float = 7.0


@dataclass
class ModelEntry:
    model: str
    weight: int = 1
    capabilities: list = field(default_factory=list)
    max_tokens: int = 2000
    temperature: float = 0.7


@dataclass
class LLMProvider:
    name: str
    api_url: str
    models: list = field(default_factory=list)
    api_key: Optional[str] = None
    timeout: int = 60
    enabled: bool = True

    def get_model(self, task_type: str = "general") -> ModelEntry:
        for m in self.models:
            if task_type in m.capabilities:
                return m
        return self.models[0] if self.models else ModelEntry(model="")


# ===== T-8: 新增配置结构 =====
@dataclass
class InjectionPriorityConfig:
    enabled: bool = True
    priority_sources: list = field(default_factory=list)
    boost_score: float = 2.0
    trigger_immediate: bool = True


@dataclass
class ExplorationConfig:
    mode: str = "daemon"  # daemon | api_only | hybrid
    daemon_interval_minutes: int = 60
    daemon_explore_per_round: int = 1
    injection_priority: InjectionPriorityConfig = field(default_factory=InjectionPriorityConfig)


@dataclass
class Config:
    thresholds: MetaCognitiveThresholds
    user_interests: list = field(default_factory=list)
    notification: dict = field(default_factory=dict)
    llm_providers: list = field(default_factory=list)
    default_llm_provider: str = "volcengine"
    exploration: ExplorationConfig = field(default_factory=ExplorationConfig)


def load_config() -> Config:
    config_path = Path(__file__).parent.parent / "config.json"
    raw = {}

    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Config] Error loading config.json: {e}")

    _load_env_file()

    mc = raw.get("meta_cognitive", {})
    thresholds = MetaCognitiveThresholds(
        max_explore_count=mc.get("max_explore_count", 3),
        min_marginal_return=mc.get("min_marginal_return", 0.3),
        high_quality_threshold=mc.get("high_quality_threshold", 7.0)
    )

    llm_providers = []
    llm_config = raw.get("llm", {})

    for name, cfg in llm_config.get("providers", {}).items():
        api_key = os.environ.get(f"{name.upper()}_API_KEY") or cfg.get("api_key")

        models = []
        for m_cfg in cfg.get("models", []):
            models.append(ModelEntry(
                model=m_cfg.get("model", ""),
                weight=m_cfg.get("weight", 1),
                capabilities=m_cfg.get("capabilities", ["general"]),
                max_tokens=m_cfg.get("max_tokens", 2000),
                temperature=m_cfg.get("temperature", 0.7)
            ))

        if "model" in cfg and not models:
            models.append(ModelEntry(
                model=cfg["model"],
                weight=cfg.get("weight", 1),
                capabilities=cfg.get("capabilities", ["general"])
            ))

        llm_providers.append(LLMProvider(
            name=name,
            api_url=cfg.get("api_url", ""),
            models=models,
            api_key=api_key,
            timeout=cfg.get("timeout", 60),
            enabled=cfg.get("enabled", True)
        ))

    # T-8: Parse exploration config
    exp_raw = raw.get("exploration", {})
    inj_raw = exp_raw.get("injection_priority", {})
    inj_cfg = InjectionPriorityConfig(
        enabled=inj_raw.get("enabled", True),
        priority_sources=inj_raw.get("priority_sources", ["r1d3"]),
        boost_score=inj_raw.get("boost_score", 2.0),
        trigger_immediate=inj_raw.get("trigger_immediate", True)
    )
    daemon_raw = exp_raw.get("daemon", {})
    exploration = ExplorationConfig(
        mode=exp_raw.get("mode", "daemon"),
        daemon_interval_minutes=daemon_raw.get("interval_minutes", 60),
        daemon_explore_per_round=daemon_raw.get("explore_per_round", 1),
        injection_priority=inj_cfg
    )

    return Config(
        thresholds=thresholds,
        user_interests=raw.get("user_interests", []),
        notification=raw.get("notification", {}),
        llm_providers=llm_providers,
        default_llm_provider=llm_config.get("default_provider", "volcengine"),
        exploration=exploration
    )


def _load_env_file():
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Config:
    global _config
    _config = load_config()
    return _config
