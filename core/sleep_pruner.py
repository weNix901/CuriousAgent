"""SleepPruner - Periodic pruning agent with adaptive intervals."""
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from core.base_agent import BaseAgent
from core import knowledge_graph as kg
from core.node_lock_registry import NodeLockRegistry


class SleepPruner(BaseAgent):
    """
    Periodic pruning agent that marks dormant nodes to optimize KG.
    
    Features:
    - Adaptive intervals: starts at 4h, doubles when no pruning, max 24h
    - Resets to initial interval when pruning occurs
    - 5 dormancy criteria (all must be true)
    - Thread-safe operations via NodeLockRegistry
    
    Dormancy Criteria (all must be true):
    1. Status is "complete" (fully explored)
    2. No recent dreams (within dream_window_days)
    3. No recent consolidations (within consolidation_window_days)
    4. Quality score below quality_threshold
    5. No pending children (all children explored or dormant)
    """
    
    # Interval constants (in minutes)
    INITIAL_INTERVAL_MINUTES = 240  # 4 hours
    MAX_INTERVAL_MINUTES = 1440     # 24 hours
    
    # Default thresholds
    DEFAULT_DREAM_WINDOW_DAYS = 7
    DEFAULT_CONSOLIDATION_WINDOW_DAYS = 14
    DEFAULT_QUALITY_THRESHOLD = 5.0
    
    def __init__(
        self,
        name: str = "SleepPruner",
        initial_interval_minutes: Optional[float] = None,
        max_interval_minutes: Optional[float] = None,
        dream_window_days: int = DEFAULT_DREAM_WINDOW_DAYS,
        consolidation_window_days: int = DEFAULT_CONSOLIDATION_WINDOW_DAYS,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD
    ):
        """
        Initialize SleepPruner.
        
        Args:
            name: Thread name for debugging
            initial_interval_minutes: Initial pruning interval (default 240 = 4h)
            max_interval_minutes: Maximum pruning interval (default 1440 = 24h)
            dream_window_days: Days to check for recent dreams
            consolidation_window_days: Days to check for recent consolidations
            quality_threshold: Quality score threshold for dormancy
        """
        super().__init__(name=name)
        
        self._initial_interval_minutes = initial_interval_minutes or self.INITIAL_INTERVAL_MINUTES
        self._max_interval_minutes = max_interval_minutes or self.MAX_INTERVAL_MINUTES
        self._current_interval_minutes = self._initial_interval_minutes
        
        self._dream_window_days = dream_window_days
        self._consolidation_window_days = consolidation_window_days
        self._quality_threshold = quality_threshold
        
        self._last_prune_time: Optional[datetime] = None
        self._pruned_count: int = 0
        self._total_pruned: int = 0
    
    @property
    def current_interval_minutes(self) -> float:
        """Get current pruning interval in minutes."""
        return self._current_interval_minutes
    
    @property
    def last_prune_time(self) -> Optional[datetime]:
        """Get timestamp of last prune operation."""
        return self._last_prune_time
    
    @property
    def pruned_count(self) -> int:
        """Get count of nodes pruned in last cycle."""
        return self._pruned_count
    
    @property
    def total_pruned(self) -> int:
        """Get total count of nodes pruned since start."""
        return self._total_pruned
    
    def run(self):
        """
        Main loop: periodic pruning with adaptive intervals.
        
        Loop continues until running flag is set to False via stop().
        """
        while self.running:
            try:
                self._prune_cycle()
            except Exception as e:
                print(f"[SleepPruner] Error in prune cycle: {e}")
            
            # Sleep for current interval (convert minutes to seconds)
            sleep_seconds = self._current_interval_minutes * 60
            
            # Sleep in small increments to allow quick shutdown
            sleep_increment = 1.0
            elapsed = 0.0
            while elapsed < sleep_seconds and self.running:
                time.sleep(sleep_increment)
                elapsed += sleep_increment
    
    def _prune_cycle(self):
        """
        Execute one pruning cycle.
        
        - Find candidates meeting all dormancy criteria
        - Mark them as dormant
        - Adapt interval based on results
        """
        candidates = self._find_dormancy_candidates()
        
        if candidates:
            self._mark_dormant_batch(candidates)
            self._pruned_count = len(candidates)
            self._total_pruned += self._pruned_count
            self._reset_interval()
        else:
            self._pruned_count = 0
            self._double_interval()
        
        self._last_prune_time = datetime.now(timezone.utc)
    
    def _find_dormancy_candidates(self) -> list[str]:
        """
        Find all nodes meeting all 5 dormancy criteria.
        
        Returns:
            List of topic names that should be marked dormant
        """
        candidates = []
        
        with NodeLockRegistry.global_write_lock():
            state = kg._load_state()
            topics = state["knowledge"]["topics"]
            
            for topic_name, topic_data in topics.items():
                # Skip already dormant nodes
                if topic_data.get("status") == "dormant":
                    continue
                
                # Skip nodes in root pool (never prune root technologies)
                if topic_name in kg.get_root_pool_names():
                    continue
                
                if self._meets_all_dormancy_criteria(topic_name, topic_data, topics):
                    candidates.append(topic_name)
        
        return candidates
    
    def _meets_all_dormancy_criteria(
        self,
        topic_name: str,
        topic_data: dict,
        all_topics: dict
    ) -> bool:
        """
        Check if a node meets all 5 dormancy criteria.
        
        All 5 must be true:
        1. Status is "complete"
        2. No recent dreams
        3. No recent consolidations
        4. Quality below threshold
        5. No pending children
        
        Args:
            topic_name: Name of the topic to check
            topic_data: Topic data dictionary
            all_topics: All topics in knowledge graph
            
        Returns:
            True if all criteria are met
        """
        # Criterion 1: Status is "complete" or "no_content" (stub nodes)
        status = topic_data.get("status")
        if status not in ("complete", "no_content"):
            return False

        # For "no_content" (stub/failed) nodes, skip dream/consolidation checks
        # They should be pruned without waiting 7 days
        if status == "no_content":
            # Criterion 4: Quality below threshold
            if not self._is_low_quality(topic_data):
                return False
            # Criterion 5: No pending children
            if self._has_pending_children(topic_name, topic_data, all_topics):
                return False
            return True

        # For "complete" nodes, apply full criteria
        # Criterion 2: No recent dreams
        if self._has_recent_dreams(topic_data):
            return False

        # Criterion 3: No recent consolidations
        if self._has_recent_consolidation(topic_data):
            return False

        # Criterion 4: Quality below threshold
        if not self._is_low_quality(topic_data):
            return False
        
        # Criterion 5: No pending children
        if self._has_pending_children(topic_name, topic_data, all_topics):
            return False
        
        return True
    
    def _has_recent_dreams(self, topic_data: dict) -> bool:
        """Check if topic has been dreamed within dream_window_days."""
        dreamed_at_str = topic_data.get("dreamed_at")
        if not dreamed_at_str:
            return False
        
        try:
            dreamed_at = datetime.fromisoformat(dreamed_at_str)
            age = datetime.now(timezone.utc) - dreamed_at
            return age.days < self._dream_window_days
        except (ValueError, TypeError):
            return False
    
    def _has_recent_consolidation(self, topic_data: dict) -> bool:
        """Check if topic has been consolidated within consolidation_window_days."""
        consolidated_str = topic_data.get("last_consolidated")
        if not consolidated_str:
            return False
        
        try:
            consolidated_at = datetime.fromisoformat(consolidated_str)
            age = datetime.now(timezone.utc) - consolidated_at
            return age.days < self._consolidation_window_days
        except (ValueError, TypeError):
            return False
    
    def _is_low_quality(self, topic_data: dict) -> bool:
        """Check if topic quality is below threshold."""
        quality = topic_data.get("quality", 0.0)
        return quality < self._quality_threshold
    
    def _has_pending_children(
        self,
        topic_name: str,
        topic_data: dict,
        all_topics: dict
    ) -> bool:
        """
        Check if topic has pending (non-dormant, non-complete) children.
        
        Returns True if there are pending children (should NOT be dormant).
        Returns False if all children are explored or dormant (CAN be dormant).
        """
        children = topic_data.get("children", [])
        
        if not children:
            return False
        
        for child_name in children:
            if child_name not in all_topics:
                continue
            
            child_data = all_topics[child_name]
            child_status = child_data.get("status", "unexplored")
            
            # If child is not complete and not dormant, it's pending
            if child_status not in ("complete", "dormant"):
                return True
        
        return False
    
    def _mark_dormant_batch(self, topics: list[str]):
        """
        Mark multiple topics as dormant in a single operation.
        
        Args:
            topics: List of topic names to mark dormant
        """
        with NodeLockRegistry.global_write_lock():
            state = kg._load_state()
            
            for topic in topics:
                if topic in state["knowledge"]["topics"]:
                    state["knowledge"]["topics"][topic]["status"] = "dormant"
            
            kg._save_state(state)
    
    def _reset_interval(self):
        """Reset interval to initial value after successful pruning."""
        self._current_interval_minutes = self._initial_interval_minutes
    
    def _double_interval(self):
        """Double interval when no pruning occurred, up to max."""
        self._current_interval_minutes = min(
            self._current_interval_minutes * 2,
            self._max_interval_minutes
        )
    
    def force_prune(self) -> int:
        """
        Force an immediate prune cycle (for testing or manual trigger).
        
        Returns:
            Number of nodes pruned
        """
        self._prune_cycle()
        return self._pruned_count
    
    def get_status(self) -> dict:
        """
        Get current status of the pruner.
        
        Returns:
            Dictionary with current state information
        """
        return {
            "running": self.running,
            "current_interval_minutes": self._current_interval_minutes,
            "initial_interval_minutes": self._initial_interval_minutes,
            "max_interval_minutes": self._max_interval_minutes,
            "last_prune_time": self._last_prune_time.isoformat() if self._last_prune_time else None,
            "pruned_count": self._pruned_count,
            "total_pruned": self._total_pruned,
            "dream_window_days": self._dream_window_days,
            "consolidation_window_days": self._consolidation_window_days,
            "quality_threshold": self._quality_threshold
        }
