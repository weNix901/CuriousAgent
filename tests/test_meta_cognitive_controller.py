import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import Mock
from core.meta_cognitive_controller import MetaCognitiveController
from core.meta_cognitive_monitor import MetaCognitiveMonitor
from core import knowledge_graph as kg


class TestMetaCognitiveControllerInit:
    def test_init_default_thresholds(self):
        monitor = MetaCognitiveMonitor()
        controller = MetaCognitiveController(monitor)
        assert controller.thresholds["max_explore_count"] == 3
        assert controller.thresholds["min_marginal_return"] == 0.3
        assert controller.thresholds["high_quality_threshold"] == 7.0

    def test_init_custom_thresholds(self):
        monitor = MetaCognitiveMonitor()
        config = {"thresholds": {"max_explore_count": 5, "min_marginal_return": 0.5}}
        controller = MetaCognitiveController(monitor, config)
        assert controller.thresholds["max_explore_count"] == 5
        assert controller.thresholds["min_marginal_return"] == 0.5


class TestShouldExplore:
    def setup_method(self):
        self.monitor = MetaCognitiveMonitor()
        self.controller = MetaCognitiveController(self.monitor)
        state = kg.get_state()
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
        kg._save_state(state)

    def test_should_explore_new_topic(self):
        allowed, reason = self.controller.should_explore("new-topic")
        assert allowed is True
        assert "Explore allowed" in reason

    def test_should_explore_blocked(self):
        kg.mark_topic_done("blocked-topic", "max_count_reached")
        allowed, reason = self.controller.should_explore("blocked-topic")
        assert allowed is False
        assert "blocked" in reason.lower()

    def test_should_explore_max_count(self):
        for i in range(3):
            kg.update_meta_exploration("test-topic", 7.0, 0.5, False)
        allowed, reason = self.controller.should_explore("test-topic")
        assert allowed is False
        assert "Max explore count" in reason

    def test_should_explore_under_limit(self):
        kg.update_meta_exploration("test-topic", 7.0, 0.5, False)
        allowed, reason = self.controller.should_explore("test-topic")
        assert allowed is True
        assert "1/3" in reason


class TestShouldContinue:
    def setup_method(self):
        self.monitor = MetaCognitiveMonitor()
        self.controller = MetaCognitiveController(self.monitor)
        state = kg.get_state()
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
        kg._save_state(state)

    def test_should_continue_first(self):
        allowed, reason = self.controller.should_continue("new-topic")
        assert allowed is True
        assert "First exploration" in reason

    def test_should_continue_high_return(self):
        kg.update_meta_exploration("test", 8.0, 0.8, False)
        allowed, reason = self.controller.should_continue("test")
        assert allowed is True
        assert "healthy" in reason.lower()

    def test_should_continue_low_return(self):
        kg.update_meta_exploration("test", 5.0, 0.1, False)
        allowed, reason = self.controller.should_continue("test")
        assert allowed is False
        assert "below threshold" in reason.lower()

    def test_should_continue_declining(self):
        kg.update_meta_exploration("test", 6.0, 0.4, False)
        kg.update_meta_exploration("test", 5.0, 0.25, False)
        allowed, reason = self.controller.should_continue("test")
        assert allowed is False
        assert "below threshold" in reason.lower()


class TestShouldNotify:
    def setup_method(self):
        self.monitor = MetaCognitiveMonitor()
        self.controller = MetaCognitiveController(self.monitor)
        state = kg.get_state()
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
        kg._save_state(state)

    def test_should_notify_high_quality(self):
        kg.update_meta_exploration("test", 8.0, 0.5, False)
        should, reason = self.controller.should_notify("test")
        assert should is True
        assert "High quality" in reason

    def test_should_notify_low_quality(self):
        kg.update_meta_exploration("test", 5.0, 0.5, False)
        should, reason = self.controller.should_notify("test")
        assert should is False
        assert "below" in reason.lower()

    def test_should_notify_at_threshold(self):
        kg.update_meta_exploration("test", 7.0, 0.5, False)
        should, reason = self.controller.should_notify("test")
        assert should is True


class TestGetDecisionSummary:
    def setup_method(self):
        self.monitor = MetaCognitiveMonitor()
        self.controller = MetaCognitiveController(self.monitor)
        state = kg.get_state()
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
        kg._save_state(state)

    def test_decision_summary_complete(self):
        kg.update_meta_exploration("test", 8.0, 0.5, False)
        summary = self.controller.get_decision_summary("test")
        assert "topic" in summary
        assert "should_explore" in summary
        assert "should_continue" in summary
        assert "should_notify" in summary
        assert summary["topic"] == "test"
