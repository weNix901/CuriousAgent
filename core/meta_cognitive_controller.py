from core.meta_cognitive_monitor import MetaCognitiveMonitor
from core import knowledge_graph_compat as kg_compat
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MetaCognitiveController:
    DEFAULT_THRESHOLDS = {
        "max_explore_count": 3,
        "min_marginal_return": 0.3,
        "high_quality_threshold": 7.0,
        "orphan_max_explore_boost": 2,
        "high_quality_max_explore_multiplier": 2.0,
        "very_high_quality_max_explore_multiplier": 3.0,
    }

    def __init__(self, monitor: MetaCognitiveMonitor, config: Optional[dict] = None):
        self.monitor = monitor
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()

        if config:
            self.thresholds.update(config.get("thresholds", {}))
        else:
            try:
                from core.config import get_config
                cfg = get_config()
                curiosity = cfg.behavior.get("curiosity", {})
                self.thresholds.update({
                    "max_explore_count": getattr(curiosity, 'max_explore_count', 3),
                    "min_marginal_return": getattr(curiosity, 'min_marginal_return', 0.3),
                    "high_quality_threshold": getattr(curiosity, 'high_quality_threshold', 7.0),
                    "orphan_max_explore_boost": getattr(curiosity, 'orphan_max_explore_boost', 2),
                    "high_quality_max_explore_multiplier": getattr(curiosity, 'high_quality_max_explore_multiplier', 2.0),
                    "very_high_quality_max_explore_multiplier": getattr(curiosity, 'very_high_quality_max_explore_multiplier', 3.0),
                })
            except Exception as e:
                logger.warning(f"Failed to load config thresholds: {e}", exc_info=True)

    def should_explore(self, topic: str) -> tuple[bool, str]:
        if self.monitor.is_topic_blocked(topic):
            return False, f"Topic '{topic}' is blocked (completed)"

        explore_count = self.monitor.get_explore_count(topic)
        base_max = self.thresholds["max_explore_count"]

        quality = self.monitor.get_last_quality(topic)
        if quality >= 8.0:
            max_count = int(base_max * self.thresholds["very_high_quality_max_explore_multiplier"])
        elif quality >= 7.0:
            max_count = int(base_max * self.thresholds["high_quality_max_explore_multiplier"])
        else:
            max_count = base_max

        relations_count = self._get_relations_count(topic)
        if relations_count == 0:
            max_count += self.thresholds["orphan_max_explore_boost"]

        if explore_count >= max_count:
            return False, f"Max explore count ({max_count}) reached for '{topic}' (quality={quality:.1f}, relations={relations_count})"

        return True, f"Explore allowed ({explore_count}/{max_count})"

    def _get_relations_count(self, topic: str) -> int:
        try:
            return kg_compat.get_relations_count(topic)
        except Exception:
            return 0

    def should_continue(self, topic: str) -> tuple[bool, str]:
        returns = self.monitor.get_marginal_returns(topic)
        min_return = self.thresholds["min_marginal_return"]

        if not returns:
            return True, "First exploration, continue to gather data"

        last_return = returns[-1]
        quality = self.monitor.get_last_quality(topic)

        if quality >= 7.0:
            if last_return > 0:
                return True, f"High quality ({quality:.1f}), marginal return positive ({last_return:.2f})"
            explore_count = self.monitor.get_explore_count(topic)
            if explore_count < 2:
                return True, f"High quality ({quality:.1f}), too few explorations ({explore_count}) to stop"

        if last_return < min_return:
            return False, f"Marginal return ({last_return:.2f}) below threshold ({min_return})"

        if len(returns) >= 2:
            if returns[-1] < min_return and returns[-2] < min_return:
                return False, "Marginal return declining for 2 consecutive explorations"

        return True, f"Marginal return healthy ({last_return:.2f})"

    def should_notify(self, topic: str) -> tuple[bool, str]:
        quality = self.monitor.get_last_quality(topic)
        threshold = self.thresholds["high_quality_threshold"]

        if quality >= threshold:
            return True, f"High quality discovery ({quality:.1f} >= {threshold})"

        return False, f"Quality ({quality:.1f}) below notification threshold ({threshold})"

    def get_decision_summary(self, topic: str) -> dict:
        explore_allowed, explore_reason = self.should_explore(topic)
        continue_allowed, continue_reason = self.should_continue(topic)
        notify, notify_reason = self.should_notify(topic)

        return {
            "topic": topic,
            "should_explore": explore_allowed,
            "explore_reason": explore_reason,
            "should_continue": continue_allowed,
            "continue_reason": continue_reason,
            "should_notify": notify,
            "notify_reason": notify_reason,
            "explore_count": self.monitor.get_explore_count(topic),
            "last_quality": self.monitor.get_last_quality(topic),
            "marginal_returns": self.monitor.get_marginal_returns(topic)
        }
