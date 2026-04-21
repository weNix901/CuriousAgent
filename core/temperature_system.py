"""Temperature system for knowledge activity tracking (v0.3.3)."""
import logging
from typing import Literal

logger = logging.getLogger(__name__)


class TemperatureSystem:
    """Manage knowledge temperature with exponential decay."""
    
    def __init__(
        self,
        decay_factor: float = 0.95,
        hot_threshold: int = 80,
        warm_threshold: int = 30,
        hit_boost: int = 20,
        new_knowledge_boost: int = 5,
        child_boost_per: int = 2,
        trusted_multiplier: float = 1.1
    ):
        self.decay_factor = decay_factor
        self.hot_threshold = hot_threshold
        self.warm_threshold = warm_threshold
        self.hit_boost = hit_boost
        self.new_knowledge_boost = new_knowledge_boost
        self.child_boost_per = child_boost_per
        self.trusted_multiplier = trusted_multiplier
    
    def apply_decay(self, heat: float) -> float:
        """Apply exponential decay (Ebbinghaus forgetting curve)."""
        return heat * self.decay_factor
    
    def apply_hit(self, heat: float) -> float:
        """Boost heat on retrieval."""
        return heat + self.hit_boost
    
    def apply_new_knowledge(self, heat: float) -> float:
        """Boost for new knowledge (first 3 days)."""
        return heat + self.new_knowledge_boost
    
    def apply_children(self, heat: float, child_count: int) -> float:
        """Boost based on number of child nodes."""
        return heat + child_count * self.child_boost_per
    
    def apply_trusted(self, heat: float, is_trusted: bool) -> float:
        """Multiplier for trusted source knowledge."""
        if is_trusted:
            return heat * self.trusted_multiplier
        return heat
    
    def classify(self, heat: float) -> Literal["hot", "warm", "cold"]:
        """Classify heat into zones."""
        if heat >= self.hot_threshold:
            return "hot"
        elif heat >= self.warm_threshold:
            return "warm"
        else:
            return "cold"
    
    def update_heat(
        self,
        current_heat: float,
        retrieved: bool = False,
        age_days: int = 0,
        child_count: int = 0,
        is_trusted: bool = False
    ) -> float:
        """Complete heat update cycle."""
        heat = current_heat
        
        # Natural decay
        heat = self.apply_decay(heat)
        
        # Retrieval hit
        if retrieved:
            heat = self.apply_hit(heat)
        
        # New knowledge protection (first 3 days)
        if age_days < 3:
            heat = self.apply_new_knowledge(heat)
        
        # Children boost
        heat = self.apply_children(heat, child_count)
        
        # Trusted source multiplier
        heat = self.apply_trusted(heat, is_trusted)
        
        # Clamp to [0, 100]
        return max(0, min(100, heat))