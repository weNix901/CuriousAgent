from core.meta_cognitive_monitor import MetaCognitiveMonitor
import logging

logger = logging.getLogger(__name__)


class MetaCognitiveController:
    DEFAULT_THRESHOLDS = {
        "max_explore_count": 3,
        "min_marginal_return": 0.3,
        "high_quality_threshold": 7.0
    }

    def __init__(self, monitor: MetaCognitiveMonitor, config: dict = None):
        self.monitor = monitor
        self.thresholds = self.DEFAULT_THRESHOLDS.copy()

        if config:
            self.thresholds.update(config.get("thresholds", {}))
        else:
            try:
                from core.config import get_config
                cfg = get_config()
                self.thresholds.update({
                    "max_explore_count": getattr(cfg.thresholds, 'max_explore_count', 3),
                    "min_marginal_return": getattr(cfg.thresholds, 'min_marginal_return', 0.3),
                    "high_quality_threshold": getattr(cfg.thresholds, 'high_quality_threshold', 7.0)
                })
            except Exception as e:
                logger.warning(f"Failed to load config thresholds: {e}", exc_info=True)

    def should_explore(self, topic: str) -> tuple[bool, str]:
        if self.monitor.is_topic_blocked(topic):
            return False, f"Topic '{topic}' is blocked (completed)"

        explore_count = self.monitor.get_explore_count(topic)
        max_count = self.thresholds["max_explore_count"]

        if explore_count >= max_count:
            return False, f"Max explore count ({max_count}) reached for '{topic}'"

        return True, f"Explore allowed ({explore_count}/{max_count})"

    def should_continue(self, topic: str) -> tuple[bool, str]:
        returns = self.monitor.get_marginal_returns(topic)
        min_return = self.thresholds["min_marginal_return"]

        if not returns:
            return True, "First exploration, continue to gather data"

        last_return = returns[-1]

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
