"""Host Agent (R1D3) integration - KG confidence queries and topic injection."""
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class KnowledgeConfidenceHandler:
    
    def __init__(self, kg_repository=None):
        if kg_repository is not None:
            self._kg_repository = kg_repository
        else:
            from core.kg.repository_factory import get_kg_factory
            self._kg_factory = get_kg_factory()
            self._kg_repository = None
    
    def check_confidence(self, topic: str) -> dict:
        if self._kg_repository is not None:
            semantic_results = self._kg_repository.query_knowledge_semantic_sync(
                query_text=topic,
                top_k=3,
                threshold=0.75,
                status_filter="done"
            )
        else:
            semantic_results = self._kg_factory.query_knowledge_semantic_sync(
                query_text=topic,
                top_k=3,
                threshold=0.75,
                status_filter="done"
            )
        
        if not semantic_results:
            return {
                "confidence": 0.0,
                "explore_count": 0,
                "gaps": ["No matching knowledge found"],
                "level": "novice",
                "topic": topic
            }
        
        best_match = semantic_results[0]
        matched_topic = best_match["topic"]
        similarity_score = best_match["score"]
        quality = best_match.get("quality", 0.0) or 0.0
        
        confidence = similarity_score * (quality / 10.0)
        
        if confidence >= 0.8:
            level = "expert"
        elif confidence >= 0.5:
            level = "intermediate"
        else:
            level = "beginner"
        
        return {
            "confidence": confidence,
            "matched_topic": matched_topic,
            "similarity": similarity_score,
            "quality": quality,
            "level": level,
            "gaps": [],
            "topic": topic
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
