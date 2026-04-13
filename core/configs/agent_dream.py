"""DreamAgent configuration."""
from dataclasses import dataclass, field
from typing import List, Dict


DREAM_SYSTEM_PROMPT = """You are a dream agent that generates creative insights during sleep cycles.

Your multi-cycle architecture:
- L1 Light Sleep: Select candidate topics from exploration history
- L2 Deep Sleep: Score candidates on 6 dimensions
- L3 Filtering: Apply threshold gating (minScore >= 0.8)
- L4 REM Sleep: Generate queue topics (NO KG writes)

Scoring dimensions:
- Relevance: How related to user interests?
- Frequency: How often mentioned in exploration?
- Recency: How recently explored?
- Quality: What was the exploration quality?
- Surprise: How unexpected was the finding?
- CrossDomain: Does it connect multiple domains?

Output: Generate topics for the exploration queue, not direct KG writes."""


DREAM_TOOLS = [
    "query_kg",
    "query_kg_by_status",
    "query_kg_by_heat",
    "get_node_relations",
    "add_to_queue",
    "claim_queue",
    "get_queue",
    "mark_done",
    "mark_failed",
    "search_web",
    "fetch_page",
    "llm_analyze",
    "llm_summarize",
]


DEFAULT_SCORING_WEIGHTS = {
    "relevance": 0.25,
    "frequency": 0.15,
    "recency": 0.10,
    "quality": 0.20,
    "surprise": 0.15,
    "cross_domain": 0.15,
}


@dataclass
class DreamAgentConfig:
    """Configuration for DreamAgent."""
    name: str = "DreamAgent"
    system_prompt: str = DREAM_SYSTEM_PROMPT
    tools: List[str] = field(default_factory=lambda: DREAM_TOOLS)
    max_iterations: int = 4
    model: str = "doubao-pro"
    scoring_weights: Dict[str, float] = field(default_factory=lambda: DEFAULT_SCORING_WEIGHTS)
    min_score_threshold: float = 0.8
    min_recall_count: int = 3