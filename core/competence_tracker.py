"""Competence Tracker - Track agent competence across topics"""
from datetime import datetime, timezone
from core import knowledge_graph_compat as kg


class CompetenceTracker:
    """
    Track agent's exploration competence across topics
    Drive exploration by competence gaps
    """
    
    LEVEL_NOVICE = 0.3
    LEVEL_COMPETENT = 0.6
    LEVEL_EXPERT = 0.85
    
    def __init__(self):
        self.kg = kg
    
    def assess_competence(self, topic: str) -> dict:
        """
        Assess agent's competence on a topic
        """
        state = self.kg.get_state()
        competence_state = state.get("competence_state", {})
        topic_competence = competence_state.get(topic, {})
        
        confidence = topic_competence.get("confidence", 0.5)
        quality_history = topic_competence.get("quality_history", [])
        explore_count = len(quality_history)
        
        quality_trend = self._compute_quality_trend(quality_history)
        
        score = (
            confidence * 0.40 +
            min(1.0, explore_count / 5) * 0.20 +
            (quality_trend + 1) / 2 * 0.20 +
            confidence * 0.20
        )
        
        return {
            "score": round(score, 2),
            "level": self._score_to_level(score),
            "confidence": confidence,
            "explore_count": explore_count,
            "quality_trend": round(quality_trend, 2),
            "reason": f"confidence={confidence:.2f}, explores={explore_count}, trend={quality_trend:+.2f}"
        }
    
    def should_explore_due_to_low_competence(self, topic: str) -> tuple[bool, str]:
        """Determine if exploration should be triggered due to low competence"""
        competence = self.assess_competence(topic)
        
        if competence["level"] == "novice":
            return True, f"Low competence level: {competence['level']}"
        
        if competence["level"] == "competent" and competence["quality_trend"] < -0.5:
            return True, f"Declining competence trend: {competence['quality_trend']:.2f}"
        
        return False, f"Competence sufficient: {competence['level']}"
    
    def update_competence(self, topic: str, quality: float):
        """Update competence after exploration using EMA"""
        state = self.kg.get_state()
        
        if "competence_state" not in state:
            state["competence_state"] = {}
        
        competence_state = state["competence_state"]
        
        if topic not in competence_state:
            competence_state[topic] = {
                "confidence": 0.5,
                "quality_history": [],
                "explore_count": 0,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
        
        current = competence_state[topic]
        
        prev_confidence = current.get("confidence", 0.5)
        new_confidence = 0.7 * prev_confidence + 0.3 * (quality / 10.0)
        
        quality_history = current.get("quality_history", [])
        quality_history.append(quality)
        quality_history = quality_history[-5:]
        
        competence_state[topic].update({
            "confidence": round(new_confidence, 3),
            "quality_history": quality_history,
            "explore_count": current.get("explore_count", 0) + 1,
            "last_updated": datetime.now(timezone.utc).isoformat()
        })
        
        self.kg._save_state(state)
    
    def _compute_quality_trend(self, quality_history: list) -> float:
        """Compute quality trend using linear regression slope"""
        if len(quality_history) < 2:
            return 0.0
        
        qualities = quality_history[-5:]
        n = len(qualities)
        
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(qualities) / n
        
        numerator = sum((x[i] - x_mean) * (qualities[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        return max(-1.0, min(1.0, slope / 2.0))
    
    def _score_to_level(self, score: float) -> str:
        """Convert score to competence level"""
        if score < self.LEVEL_NOVICE:
            return "novice"
        elif score < self.LEVEL_COMPETENT:
            return "competent"
        elif score < self.LEVEL_EXPERT:
            return "proficient"
        else:
            return "expert"
