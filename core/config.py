"""Curious Agent Configuration - v0.2.9"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# LLM Configuration
# ============================================================

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
    models: list[ModelEntry] = field(default_factory=list)
    api_key: Optional[str] = None
    timeout: int = 60
    enabled: bool = True

    def get_model(self, task_type: str = "general") -> ModelEntry:
        for m in self.models:
            if task_type in m.capabilities:
                return m
        return self.models[0] if self.models else ModelEntry(model="")


# ============================================================
# Agent Configuration
# ============================================================

@dataclass
class ExploreAgentConfig:
    """ExploreAgent (ReAct loop) configuration."""
    max_iterations: int = 10
    model: str = "doubao-pro"
    tools: list[str] = field(default_factory=list)


@dataclass
class DreamAgentScoringWeights:
    """DreamAgent 6-dimension scoring weights."""
    relevance: float = 0.25
    frequency: float = 0.15
    recency: float = 0.15
    quality: float = 0.20
    surprise: float = 0.15
    cross_domain: float = 0.10


@dataclass
class DreamAgentConfig:
    """DreamAgent (multi-cycle) configuration."""
    scoring_weights: DreamAgentScoringWeights = field(default_factory=DreamAgentScoringWeights)
    min_score_threshold: float = 0.8
    min_recall_count: int = 3
    max_candidates: int = 100
    max_scored: int = 20


# ============================================================
# Daemon Configuration
# ============================================================

@dataclass
class ExploreDaemonConfig:
    """ExploreDaemon process configuration."""
    poll_interval_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: int = 15


@dataclass
class DreamDaemonConfig:
    """DreamDaemon process configuration."""
    interval_seconds: int = 21600


# ============================================================
# Knowledge Configuration
# ============================================================

@dataclass
class SearchDailyQuotaConfig:
    """Daily search API quota configuration."""
    enabled: bool = True
    serper: int = 100      # Serper daily limit
    bocha: int = 50        # Bocha daily limit
    reset_hour: int = 0    # Reset at midnight (UTC)


@dataclass
class KnowledgeSearchConfig:
    """Search provider configuration."""
    primary: str = "bocha"
    fallback: str = "serper"
    bocha_fallback_mode: str = "serper_empty"
    bocha_fallback: str = "serper_empty"  # When to use Bocha fallback (v0.2.8 legacy: always, never, serper_empty)
    query_variants: int = 1  # Number of query variants to generate (v0.2.8 legacy)
    early_stop_results: int = 5  # Early stop when this many results found (v0.2.8 legacy)
    daily_quota: SearchDailyQuotaConfig = field(default_factory=SearchDailyQuotaConfig)


@dataclass
class KnowledgeEmbeddingConfig:
    """Embedding service configuration."""
    provider: str = "siliconflow"
    model: str = "BAAI/bge-large-zh-v1.5"
    dimension: int = 1024
    api_key_env: str = "SILICONFLOW_API_KEY"
    fallback_chain: list[str] = field(default_factory=lambda: ["siliconflow", "llm"])
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    cache_size: int = 1000  # Embedding cache size


@dataclass
class KnowledgeGraphConfig:
    """Knowledge Graph storage configuration."""
    enabled: bool = False
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password_env: str = "NEO4J_PASSWORD"
    fallback_to_json: bool = True


# ============================================================
# Behavior Configuration
# ============================================================

@dataclass
class CuriosityBehaviorConfig:
    """Curiosity engine behavior configuration."""
    max_explore_count: int = 3
    min_marginal_return: float = 0.3
    high_quality_threshold: float = 7.0


@dataclass
class InjectionBehaviorConfig:
    """Topic injection behavior configuration."""
    enabled: bool = True
    priority_sources: list[str] = field(default_factory=list)
    boost_score: float = 2.0
    trigger_immediate: bool = True


@dataclass
class NotificationBehaviorConfig:
    """Notification behavior configuration."""
    enabled: bool = True
    min_quality: float = 7.0


@dataclass
class BehaviorConfig:
    """Root behavior configuration."""
    curiosity: CuriosityBehaviorConfig = field(default_factory=CuriosityBehaviorConfig)
    injection: InjectionBehaviorConfig = field(default_factory=InjectionBehaviorConfig)
    notification: NotificationBehaviorConfig = field(default_factory=NotificationBehaviorConfig)
    user_interests: list[str] = field(default_factory=list)


# ============================================================
# Root Config
# ============================================================

@dataclass
class Config:
    """Root configuration for Curious Agent."""
    agents: dict = field(default_factory=dict)
    daemon: dict = field(default_factory=dict)
    knowledge: dict = field(default_factory=dict)
    behavior: dict = field(default_factory=dict)
    llm: dict = field(default_factory=dict)


def _load_env_file():
    """Load environment variables from .env file.
    
    Always uses .env values to ensure config.json API keys take precedence
    over inherited shell environment variables.
    """
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    value = value.strip().strip('"').strip("'")
                    # Always use .env value (don't check if already exists)
                    os.environ[key.strip()] = value


# Alias for backward compatibility
EmbeddingConfig = KnowledgeEmbeddingConfig


def load_config() -> Config:
    """Load configuration from config.json."""
    config_path = Path(__file__).parent.parent / "config.json"
    raw = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Config] Error loading config.json: {e}")

    _load_env_file()

    # Parse agents.explore
    explore_raw = raw.get("agents", {}).get("explore", {})
    explore_cfg = ExploreAgentConfig(
        max_iterations=explore_raw.get("max_iterations", 10),
        model=explore_raw.get("model", "doubao-pro"),
        tools=explore_raw.get("tools", [])
    )

    # Parse agents.dream
    dream_raw = raw.get("agents", {}).get("dream", {})
    weights_raw = dream_raw.get("scoring_weights", {})
    weights = DreamAgentScoringWeights(
        relevance=weights_raw.get("relevance", 0.25),
        frequency=weights_raw.get("frequency", 0.15),
        recency=weights_raw.get("recency", 0.15),
        quality=weights_raw.get("quality", 0.20),
        surprise=weights_raw.get("surprise", 0.15),
        cross_domain=weights_raw.get("cross_domain", 0.10)
    )
    dream_cfg = DreamAgentConfig(
        scoring_weights=weights,
        min_score_threshold=dream_raw.get("min_score_threshold", 0.8),
        min_recall_count=dream_raw.get("min_recall_count", 3),
        max_candidates=dream_raw.get("max_candidates", 100),
        max_scored=dream_raw.get("max_scored", 20)
    )

    # Parse daemon
    daemon_raw = raw.get("daemon", {})
    explore_daemon_raw = daemon_raw.get("explore", {})
    explore_daemon_cfg = ExploreDaemonConfig(
        poll_interval_seconds=explore_daemon_raw.get("poll_interval_seconds", 300),
        max_retries=explore_daemon_raw.get("max_retries", 3),
        retry_delay_seconds=explore_daemon_raw.get("retry_delay_seconds", 15)
    )
    dream_daemon_raw = daemon_raw.get("dream", {})
    dream_daemon_cfg = DreamDaemonConfig(
        interval_seconds=dream_daemon_raw.get("interval_seconds", 21600)
    )

    # Parse knowledge
    knowledge_raw = raw.get("knowledge", {})
    search_raw = knowledge_raw.get("search", {})
    quota_raw = search_raw.get("daily_quota", {})
    quota_cfg = SearchDailyQuotaConfig(
        enabled=quota_raw.get("enabled", True),
        serper=quota_raw.get("serper", 100),
        bocha=quota_raw.get("bocha", 50),
        reset_hour=quota_raw.get("reset_hour", 0)
    )
    search_cfg = KnowledgeSearchConfig(
        primary=search_raw.get("primary", "bocha"),
        fallback=search_raw.get("fallback", "serper"),
        bocha_fallback_mode=search_raw.get("bocha_fallback_mode", "serper_empty"),
        bocha_fallback=search_raw.get("bocha_fallback", "serper_empty"),
        query_variants=search_raw.get("query_variants", 1),
        early_stop_results=search_raw.get("early_stop_results", 5),
        daily_quota=quota_cfg
    )
    embedding_raw = knowledge_raw.get("embedding", {})
    embedding_cfg = KnowledgeEmbeddingConfig(
        provider=embedding_raw.get("provider", "siliconflow"),
        model=embedding_raw.get("model", "BAAI/bge-large-zh-v1.5"),
        dimension=embedding_raw.get("dimension", 1024),
        api_key_env=embedding_raw.get("api_key_env", "SILICONFLOW_API_KEY"),
        fallback_chain=embedding_raw.get("fallback_chain", ["siliconflow", "llm"]),
        siliconflow_base_url=embedding_raw.get("siliconflow_base_url", "https://api.siliconflow.cn/v1")
    )
    kg_raw = knowledge_raw.get("kg", {})
    kg_cfg = KnowledgeGraphConfig(
        enabled=kg_raw.get("enabled", False),
        uri=kg_raw.get("uri", "bolt://localhost:7687"),
        username=kg_raw.get("username", "neo4j"),
        password_env=kg_raw.get("password_env", "NEO4J_PASSWORD"),
        fallback_to_json=kg_raw.get("fallback_to_json", True)
    )

    # Parse behavior
    behavior_raw = raw.get("behavior", {})
    curiosity_raw = behavior_raw.get("curiosity", {})
    curiosity_cfg = CuriosityBehaviorConfig(
        max_explore_count=curiosity_raw.get("max_explore_count", 3),
        min_marginal_return=curiosity_raw.get("min_marginal_return", 0.3),
        high_quality_threshold=curiosity_raw.get("high_quality_threshold", 7.0)
    )
    injection_raw = behavior_raw.get("injection", {})
    injection_cfg = InjectionBehaviorConfig(
        enabled=injection_raw.get("enabled", True),
        priority_sources=injection_raw.get("priority_sources", ["r1d3"]),
        boost_score=injection_raw.get("boost_score", 2.0),
        trigger_immediate=injection_raw.get("trigger_immediate", True)
    )
    notification_raw = behavior_raw.get("notification", {})
    notification_cfg = NotificationBehaviorConfig(
        enabled=notification_raw.get("enabled", True),
        min_quality=notification_raw.get("min_quality", 7.0)
    )
    user_interests = behavior_raw.get("user_interests", [])

    # Parse LLM
    llm_raw = raw.get("llm", {})
    llm_providers = []
    for name, cfg in llm_raw.get("providers", {}).items():
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

    return Config(
        agents={
            "explore": explore_cfg,
            "dream": dream_cfg
        },
        daemon={
            "explore": explore_daemon_cfg,
            "dream": dream_daemon_cfg
        },
        knowledge={
            "search": search_cfg,
            "embedding": embedding_cfg,
            "kg": kg_cfg,
            "root_seeds": knowledge_raw.get("root_seeds", [])
        },
        behavior={
            "curiosity": curiosity_cfg,
            "injection": injection_cfg,
            "notification": notification_cfg,
            "user_interests": user_interests
        },
        llm={
            "providers": llm_providers,
            "default_provider": llm_raw.get("default_provider", "volcengine"),
            "selection_strategy": llm_raw.get("selection_strategy", "capability")
        }
    )


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
