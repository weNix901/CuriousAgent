"""ExplorationHistory - Thread-safe recording of exploration events."""
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional
import core.knowledge_graph as kg


class ExplorationHistory:
    """Thread-safe exploration history tracker."""
    _lock = threading.Lock()
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _get_history(self) -> dict:
        """Read exploration_history from state."""
        state = kg._load_state()
        if "exploration_history" not in state:
            state["exploration_history"] = {
                "co_occurrence": {},
                "insight_generation": {},
                "predictions": {}
            }
        return state["exploration_history"]
    
    def _save_history(self, history: dict):
        """Save exploration_history to state."""
        state = kg._load_state()
        state["exploration_history"] = history
        kg._save_state(state)
    
    def _make_co_occurrence_key(self, topic_a: str, topic_b: str) -> str:
        """Create a sorted key for co-occurrence to ensure consistency."""
        return "|".join(sorted([topic_a, topic_b]))
    
    def record_exploration(self, topic: str, related_nodes: list, timestamp: datetime):
        """Record an exploration event with co-occurring topics."""
        with self._lock:
            history = self._get_history()
            
            for related in related_nodes:
                key = self._make_co_occurrence_key(topic, related)
                
                if key not in history["co_occurrence"]:
                    history["co_occurrence"][key] = {
                        "count": 0,
                        "last_time": None,
                        "timestamps": []
                    }
                
                entry = history["co_occurrence"][key]
                entry["count"] += 1
                entry["last_time"] = timestamp.isoformat()
                entry["timestamps"].append(timestamp.isoformat())
            
            self._save_history(history)
    
    def record_insight_generation(self, insight_node_id: str, source_pair: tuple, timestamp: datetime):
        """Record when an insight was generated."""
        with self._lock:
            history = self._get_history()
            
            history["insight_generation"][insight_node_id] = {
                "source_pair": source_pair,
                "timestamp": timestamp.isoformat(),
                "triggered": False
            }
            
            self._save_history(history)
    
    def co_occurred(self, topic_a: str, topic_b: str, within_hours: int) -> bool:
        """Check if two topics co-occurred within time window."""
        with self._lock:
            history = self._get_history()
            
            key = self._make_co_occurrence_key(topic_a, topic_b)
            
            if key not in history["co_occurrence"]:
                return False
            
            entry = history["co_occurrence"][key]
            last_time_str = entry.get("last_time")
            
            if not last_time_str:
                return False
            
            last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
            cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
            
            return last_time >= cutoff
    
    def was_insight_triggered(self, insight_node_id: str, within_days: int) -> bool:
        """Check if an insight triggered follow-up exploration."""
        with self._lock:
            history = self._get_history()
            
            if insight_node_id not in history["insight_generation"]:
                return False
            
            insight = history["insight_generation"][insight_node_id]
            
            if not insight.get("triggered", False):
                return False
            
            timestamp_str = insight.get("timestamp")
            if not timestamp_str:
                return False
            
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
            
            return timestamp >= cutoff
    
    def record_prediction(self, topic: str, predicted_confidence: float, is_hypothesis: bool):
        """Record a prediction for calibration tracking."""
        with self._lock:
            history = self._get_history()
            
            history["predictions"][topic] = {
                "predicted_confidence": predicted_confidence,
                "is_hypothesis": is_hypothesis,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actual_outcome": None
            }
            
            self._save_history(history)
    
    def record_outcome(self, topic: str, actual_correct: bool):
        """Record actual outcome for a prediction."""
        with self._lock:
            history = self._get_history()
            
            if topic in history["predictions"]:
                history["predictions"][topic]["actual_outcome"] = actual_correct
                self._save_history(history)
    
    def get_prediction(self, topic: str) -> Optional[dict]:
        """Get specific prediction."""
        with self._lock:
            history = self._get_history()
            
            if topic not in history["predictions"]:
                return None
            
            return history["predictions"][topic].copy()
    
    def get_all_predictions(self) -> list:
        """Get all predictions."""
        with self._lock:
            history = self._get_history()
            
            predictions = []
            for topic, data in history["predictions"].items():
                pred = data.copy()
                pred["topic"] = topic
                predictions.append(pred)
            
            return predictions
