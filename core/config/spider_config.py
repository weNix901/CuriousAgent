from dataclasses import dataclass


@dataclass
class SpiderConfig:
    loop_interval: int = 30
    max_consecutive_low_gain: int = 3
    min_marginal_return: float = 0.3
    high_quality_threshold: float = 7.0
    default_exploration_depth: str = "medium"
    frontier_strategy: str = "high_degree"
    kg_storage_path: str = "knowledge/state.json"
    checkpoint_path: str = "state/spider_state.json"
