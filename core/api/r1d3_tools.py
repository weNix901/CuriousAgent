from typing import Optional
import logging
from core.repository.base import KnowledgeRepository
from core.models.topic import Topic

logger = logging.getLogger(__name__)


class R1D3ToolHandler:
    def __init__(self, repo: Optional[KnowledgeRepository] = None):
        from core.repository.json_repository import JSONKnowledgeRepository
        self.repo = repo or JSONKnowledgeRepository()
    
    def curious_check_confidence(self, topic: str) -> dict:
        t = self.repo.get_topic(topic)
        
        if not t or not t.explored:
            return {
                "topic": topic,
                "confidence": 0.0,
                "level": "novice",
                "explore_count": 0,
                "gaps": ["No exploration data available"]
            }
        
        confidence = self._calculate_confidence(t)
        level = self._confidence_to_level(confidence)
        
        return {
            "topic": topic,
            "confidence": confidence,
            "level": level,
            "explore_count": t.explore_count,
            "gaps": self._identify_gaps(t)
        }
    
    def _calculate_confidence(self, topic: Topic) -> float:
        base_confidence = min(topic.explore_count / 5, 1.0) * 0.6
        quality_boost = (topic.last_quality or 0) / 10 * 0.4
        return min(base_confidence + quality_boost, 1.0)
    
    def _confidence_to_level(self, confidence: float) -> str:
        if confidence < 0.3:
            return "novice"
        elif confidence < 0.6:
            return "competent"
        elif confidence < 0.85:
            return "proficient"
        else:
            return "expert"
    
    def _identify_gaps(self, topic: Topic) -> list:
        gaps = []
        if topic.explore_count < 3:
            gaps.append("Limited exploration depth")
        if not topic.fully_explored:
            gaps.append("Topic not fully explored")
        return gaps

    def curious_agent_inject(self, topic: str, context: str = "",
                            depth: str = "medium", source: str = "r1d3") -> dict:
        config = self._get_config()
        priority_config = config.get("injection_priority", {})

        if priority_config.get("enabled", False):
            if source in priority_config.get("priority_sources", []):
                return self._inject_with_priority(topic, context, depth, priority_config)

        return self._inject_to_queue(topic, context, depth)

    def _inject_with_priority(self, topic: str, context: str, depth: str,
                             priority_config: dict) -> dict:
        boost_score = priority_config.get("boost_score", 2.0)

        return {
            "status": "success",
            "topic_id": f"topic_{hash(topic) % 10000}",
            "queue_position": 1,
            "priority": True,
            "boosted_score": 5.0 + boost_score
        }

    def _inject_to_queue(self, topic: str, context: str, depth: str) -> dict:
        return {
            "status": "success",
            "topic_id": f"topic_{hash(topic) % 10000}",
            "queue_position": -1,
            "priority": False
        }

    def _get_config(self) -> dict:
        try:
            from core.config.spider_config import SpiderConfig
            config = SpiderConfig()
            return config.__dict__ if hasattr(config, '__dict__') else {}
        except Exception as e:
            logger.warning(f"Failed to load SpiderConfig: {e}", exc_info=True)
            return {}
