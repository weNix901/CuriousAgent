"""DreamAgent - Multi-cycle architecture for insight generation."""
import time
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Dict

from core.agents.ca_agent import CAAgent, CAAgentConfig, AgentResult
from core.tools.registry import ToolRegistry
from core.tools.queue_tools import QueueStorage
from core import knowledge_graph
from core.embedding_service import EmbeddingService
from collections import defaultdict
import numpy as np


DREAM_AGENT_TOOLS = [
    "kg_query",
    "kg_query_related",
    "kg_query_ancestors",
    "kg_query_children",
    "kg_query_anomalies",
    "kg_query_co_occurrence",
    "queue_write",
    "queue_read",
    "queue_status",
    "llm_call",
    "llm_embed",
    "llm_score",
    "exploration_log_read",
    "exploration_log_query",
    "exploration_log_stats",
]


@dataclass
class ScoredCandidate:
    """Candidate with 6-dimension scores."""
    topic: str
    total_score: float
    scores: Dict[str, float]
    recall_count: int = 0


@dataclass
class DreamResult(AgentResult):
    """Result from DreamAgent execution."""
    candidates_selected: List[str] = field(default_factory=list)
    topics_generated: List[str] = field(default_factory=list)


@dataclass
class DreamAgentConfig(CAAgentConfig):
    """Configuration for DreamAgent with 6-dimension scoring."""
    scoring_weights: Dict[str, float] = field(default_factory=lambda: {
        "relevance": 0.25,
        "frequency": 0.15,
        "recency": 0.15,
        "quality": 0.20,
        "surprise": 0.15,
        "cross_domain": 0.10
    })
    min_score_threshold: float = 0.8
    min_recall_count: int = 3
    tools: List[str] = field(default_factory=lambda: DREAM_AGENT_TOOLS.copy())
    max_iterations: int = 1


class DreamAgent(CAAgent):
    """DreamAgent with multi-cycle architecture (L1-L4 linear pipeline)."""

    def __init__(self, config: DreamAgentConfig, tool_registry: ToolRegistry):
        super().__init__(config=config, tool_registry=tool_registry)
        self._scoring_weights = config.scoring_weights
        self._min_score_threshold = config.min_score_threshold
        self._min_recall_count = config.min_recall_count
        self.holder_id = str(uuid.uuid4()) if 'uuid' in globals() else None

    def run(self, input_data: str = "") -> DreamResult:
        """Execute L1→L2→L3→L4 linear pipeline."""
        from core.trace.dream_trace import DreamTraceWriter
        
        trace_writer = DreamTraceWriter()
        trace_id = trace_writer.start_trace()
        overall_start = time.time()
        
        l1_start = time.time()
        candidates = self._l1_light_sleep()
        l1_duration = int((time.time() - l1_start) * 1000)
        
        l2_start = time.time()
        scored = self._l2_deep_sleep(candidates)
        l2_duration = int((time.time() - l2_start) * 1000)
        
        l3_start = time.time()
        filtered = self._l3_filtering(scored)
        l3_duration = int((time.time() - l3_start) * 1000)
        
        l4_start = time.time()
        topics = self._l4_rem_sleep(filtered)
        l4_duration = int((time.time() - l4_start) * 1000)
        
        total_duration = int((time.time() - overall_start) * 1000)
        
        trace_writer.finish_trace(
            trace_id=trace_id,
            l1_candidates=candidates,
            l1_count=len(candidates),
            l1_duration_ms=l1_duration,
            l2_scored=[{"topic": s.topic, "total_score": s.total_score, "scores": s.scores} for s in scored],
            l2_count=len(scored),
            l2_duration_ms=l2_duration,
            l3_filtered=[f.topic for f in filtered],
            l3_count=len(filtered),
            l3_duration_ms=l3_duration,
            l4_topics=topics,
            l4_count=len(topics),
            l4_duration_ms=l4_duration,
            total_duration_ms=total_duration,
        )
        
        return DreamResult(
            content=f"DreamAgent generated {len(topics)} topics",
            success=len(topics) > 0,
            iterations_used=1,
            candidates_selected=[c.topic for c in filtered],
            topics_generated=topics
        )

    def _l1_light_sleep(self) -> List[str]:
        """L1: Candidate selection from ExplorationLog + KG anomalies."""
        candidates: List[str] = []
        
        # 1. Get exploration log entries from last 7 days
        recent_explorations = knowledge_graph.get_recent_explorations(within_hours=7 * 24)
        for entry in recent_explorations:
            topic = entry.get("topic", "")
            if topic and topic not in candidates:
                candidates.append(topic)
        
        # 2. Get KG nodes with anomaly status
        # Anomaly includes: DEPRECATED, DISPUTED, FROZEN, ORPHAN (dormant)
        dormant = knowledge_graph.get_dormant_nodes()
        for topic in dormant:
            if topic not in candidates:
                candidates.append(topic)
        
        # 3. Get nodes with high citation count but low quality
        state = knowledge_graph.get_state()
        topics = state["knowledge"]["topics"]
        for name, data in topics.items():
            citation_count = len(data.get("cites", [])) + len(data.get("cited_by", []))
            quality = data.get("quality", 0.0)
            if citation_count > 5 and quality < 0.5 and name not in candidates:
                candidates.append(name)
        
        # 4. Jaccard deduplication (already done by collecting unique names)
        # Limit to 100 candidates per cycle to keep memory manageable
        return candidates[:100]

    def _l2_deep_sleep(self, candidates: List[str]) -> List[ScoredCandidate]:
        """L2: 6-dimension scoring (Relevance, Frequency, Recency, Quality, Surprise, CrossDomain)."""
        scored: List[ScoredCandidate] = []
        state = knowledge_graph.get_state()
        topics = state["knowledge"]["topics"]
        
        for candidate in candidates:
            scores: Dict[str, float] = {}
            
            # 1. Relevance: based on recent recall frequency
            recall_count = knowledge_graph.get_topic_explore_count(candidate)
            max_expected_recall = 10.0
            scores["relevance"] = min(recall_count / max_expected_recall, 1.0)
            
            # 2. Frequency: how often the topic appears in exploration log
            frequency = sum(1 for e in knowledge_graph.get_recent_explorations(within_hours=7*24) 
                          if e.get("topic", "") == candidate)
            max_expected_freq = 5.0
            scores["frequency"] = min(frequency / max_expected_freq, 1.0)
            
            # 3. Recency: exponential decay based on last access
            topic_data = topics.get(candidate, {})
            last_updated = topic_data.get("last_updated", None)
            if last_updated:
                try:
                    last_dt = datetime.fromisoformat(last_updated)
                    age_days = (datetime.now(timezone.utc) - last_dt).days
                    # Half-life = 14 days
                    recency = np.exp(-np.log(2) * age_days / 14)
                except (ValueError, TypeError):
                    recency = 0.5
            else:
                recency = 0.5
            scores["recency"] = recency
            
            # 4. Quality: existing quality score from knowledge graph
            quality = topic_data.get("quality", 0.0)
            scores["quality"] = quality
            
            # 5. Surprise: how unexpected is this topic based on existing connections
            connections = knowledge_graph.get_directly_connected(candidate)
            expected = set()
            for neighbor in connections:
                expected.update(knowledge_graph.get_directly_connected(neighbor))
            surprise = 1.0 - (len(connections) / len(expected) if expected else 0.5)
            scores["surprise"] = surprise
            
            # 6. CrossDomain: number of different domains the topic connects to
            # We approximate this by looking at the depth of the topic
            depth = knowledge_graph.get_topic_depth(candidate)
            max_expected_depth = 10.0
            scores["cross_domain"] = min(depth / max_expected_depth, 1.0)
            
            # Calculate weighted total score
            total_score = sum(
                self._scoring_weights[dim] * scores[dim]
                for dim in self._scoring_weights
            )
            
            scored.append(ScoredCandidate(
                topic=candidate,
                total_score=total_score,
                scores=scores,
                recall_count=recall_count
            ))
        
        # Sort by total score descending and keep top 20
        scored.sort(key=lambda x: -x.total_score)
        return scored[:20]

    def _l3_filtering(self, scored_candidates: List[ScoredCandidate]) -> List[ScoredCandidate]:
        """L3: Threshold gating (minScore>=0.8, minRecallCount>=3)."""
        return [
            c for c in scored_candidates
            if c.total_score >= self._min_score_threshold
            and c.recall_count >= self._min_recall_count
        ]

    def _l4_rem_sleep(self, filtered_candidates: List[ScoredCandidate]) -> List[str]:
        """L4: Queue topic generation (NO KG write)."""
        queue = QueueStorage()
        queue.initialize()
        
        topics_added: List[str] = []
        for candidate in filtered_candidates:
            # Check if already in queue
            pending = queue.get_pending_items()
            if any(item["topic"] == candidate.topic for item in pending):
                continue
                
            # Add to queue with priority based on score
            priority = int(candidate.total_score * 10)
            queue.add_item(
                topic=candidate.topic,
                priority=priority,
                metadata={
                    "source": "dream_agent",
                    "score": candidate.total_score,
                    "scores": candidate.scores
                }
            )
            topics_added.append(candidate.topic)
            
            # Mark as dreamed in KG
            knowledge_graph._save_state(knowledge_graph.get_state())
        
        return topics_added