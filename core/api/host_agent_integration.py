"""Host Agent (R1D3) integration - KG confidence queries and topic injection."""
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class KnowledgeConfidenceHandler:
    
    def __init__(self):
        from core.kg.repository_factory import get_kg_factory
        self._kg_factory = get_kg_factory()
    
    def check_confidence(self, topic: str) -> dict:
        from core.knowledge_graph_compat import get_topic_explore_count, get_state
        
        state = get_state()
        topics = state.get("knowledge", {}).get("topics", {})
        topic_data = topics.get(topic, {})
        
        if not topic_data or not topic_data.get("known"):
            return {
                "topic": topic,
                "confidence": 0.0,
                "level": "novice",
                "explore_count": 0,
                "gaps": ["No exploration data available"]
            }
        
        explore_count = get_topic_explore_count(topic)
        quality = topic_data.get("quality", 0)
        
        base_confidence = min(explore_count / 5, 1.0) * 0.6
        quality_boost = quality / 10 * 0.4
        confidence = min(base_confidence + quality_boost, 1.0)
        
        level = self._confidence_to_level(confidence)
        
        return {
            "topic": topic,
            "confidence": confidence,
            "level": level,
            "explore_count": explore_count,
            "gaps": self._identify_gaps(explore_count, topic_data)
        }
    
    def _confidence_to_level(self, confidence: float) -> str:
        if confidence < 0.3:
            return "novice"
        elif confidence < 0.6:
            return "competent"
        elif confidence < 0.85:
            return "proficient"
        else:
            return "expert"
    
    def _identify_gaps(self, explore_count: int, topic_data: dict) -> list:
        gaps = []
        if explore_count < 3:
            gaps.append("Limited exploration depth")
        status = topic_data.get("status", "partial")
        if status != "complete":
            gaps.append("Topic not fully explored")
        return gaps

    def inject_topic(self, topic: str, context: str = "",
                    depth: str = "medium", source: str = "host_agent") -> dict:
        from core.knowledge_graph_compat import add_curiosity
        
        add_curiosity(topic, reason=f"Host agent injection ({source})", relevance=8.0, depth=7.0)
        
        return {
            "status": "success",
            "topic_id": f"topic_{abs(hash(topic)) % 10000}",
            "queue_position": 0,
            "priority": source == "r1d3"
        }

    def _inject_with_priority(self, topic: str, context: str, depth: str,
                             priority_config: dict) -> dict:
        boost_score = priority_config.get("boost_score", 2.0)
        
        return {
            "status": "success",
            "topic_id": f"topic_{abs(hash(topic)) % 10000}",
            "queue_position": 1,
            "priority": True,
            "boosted_score": 5.0 + boost_score
        }

    def _inject_to_queue(self, topic: str, context: str, depth: str) -> dict:
        return {
            "status": "success",
            "topic_id": f"topic_{abs(hash(topic)) % 10000}",
            "queue_position": -1,
            "priority": False
        }

    def _get_config(self) -> dict:
        try:
            from core.config import get_config
            config = get_config()
            return config.__dict__ if hasattr(config, '__dict__') else {}
        except Exception as e:
            logger.warning(f"Failed to load config: {e}", exc_info=True)
            return {}
