"""Metrics collection for v0.2.6 agents."""
import threading
from datetime import datetime, timezone
from typing import Dict, Any


class AgentMetrics:
    """Simple metrics collection for agent monitoring."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            self._metrics = {
                "explorations": {"total": 0, "successful": 0, "failed": 0},
                "dreams": {"total": 0, "with_insight": 0, "without_insight": 0},
                "prunes": {"total": 0, "nodes_pruned": 0},
                "timings": {"exploration_times": [], "dream_times": []}
            }
            self._start_time = datetime.now(timezone.utc)
            self._initialized = True
    
    def record_exploration(self, topic: str, duration: float, success: bool = True):
        """Record exploration metric."""
        with self._lock:
            self._metrics["explorations"]["total"] += 1
            if success:
                self._metrics["explorations"]["successful"] += 1
            else:
                self._metrics["explorations"]["failed"] += 1
            
            self._metrics["timings"]["exploration_times"].append(duration)
            # Keep only last 100 timings
            if len(self._metrics["timings"]["exploration_times"]) > 100:
                self._metrics["timings"]["exploration_times"] = \
                    self._metrics["timings"]["exploration_times"][-100:]
    
    def record_dream(self, has_insight: bool, duration: float):
        """Record dream metric."""
        with self._lock:
            self._metrics["dreams"]["total"] += 1
            if has_insight:
                self._metrics["dreams"]["with_insight"] += 1
            else:
                self._metrics["dreams"]["without_insight"] += 1
            
            self._metrics["timings"]["dream_times"].append(duration)
            # Keep only last 100 timings
            if len(self._metrics["timings"]["dream_times"]) > 100:
                self._metrics["timings"]["dream_times"] = \
                    self._metrics["timings"]["dream_times"][-100:]
    
    def record_prune(self, nodes_pruned: int):
        """Record prune metric."""
        with self._lock:
            self._metrics["prunes"]["total"] += 1
            self._metrics["prunes"]["nodes_pruned"] += nodes_pruned
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics stats."""
        with self._lock:
            exploration_times = self._metrics["timings"]["exploration_times"]
            dream_times = self._metrics["timings"]["dream_times"]
            
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            
            return {
                "uptime_seconds": uptime,
                "explorations": self._metrics["explorations"].copy(),
                "dreams": self._metrics["dreams"].copy(),
                "prunes": self._metrics["prunes"].copy(),
                "avg_exploration_time": sum(exploration_times) / len(exploration_times) if exploration_times else 0,
                "avg_dream_time": sum(dream_times) / len(dream_times) if dream_times else 0,
                "exploration_rate": self._metrics["explorations"]["total"] / (uptime / 3600) if uptime > 0 else 0
            }
    
    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._metrics = {
                "explorations": {"total": 0, "successful": 0, "failed": 0},
                "dreams": {"total": 0, "with_insight": 0, "without_insight": 0},
                "prunes": {"total": 0, "nodes_pruned": 0},
                "timings": {"exploration_times": [], "dream_times": []}
            }
            self._start_time = datetime.now(timezone.utc)


# Global metrics instance
metrics = AgentMetrics()
