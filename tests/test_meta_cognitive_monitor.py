import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import Mock, patch
from core.meta_cognitive_monitor import MetaCognitiveMonitor
from core import knowledge_graph as kg


class TestMetaCognitiveMonitorInit:
    def test_init_without_llm(self):
        monitor = MetaCognitiveMonitor()
        assert monitor.llm is None
        assert monitor.kg is kg

    def test_init_with_llm(self):
        mock_llm = Mock()
        monitor = MetaCognitiveMonitor(llm_client=mock_llm)
        assert monitor.llm is mock_llm


class TestMetaCognitiveMonitorQueries:
    def setup_method(self):
        self.monitor = MetaCognitiveMonitor()
        state = kg.get_state()
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
        kg._save_state(state)

    def test_get_explore_count_new_topic(self):
        assert self.monitor.get_explore_count("new-topic") == 0

    def test_get_explore_count_existing(self):
        kg.update_meta_exploration("test-topic", 7.0, 0.5, False)
        assert self.monitor.get_explore_count("test-topic") == 1

    def test_get_marginal_returns_empty(self):
        assert self.monitor.get_marginal_returns("new-topic") == []

    def test_get_marginal_returns_with_data(self):
        kg.update_meta_exploration("test-topic", 7.0, 0.5, False)
        kg.update_meta_exploration("test-topic", 8.0, 0.3, False)
        returns = self.monitor.get_marginal_returns("test-topic")
        assert len(returns) == 2
        assert returns == [0.5, 0.3]

    def test_get_last_quality_no_history(self):
        assert self.monitor.get_last_quality("new-topic") == 0.0

    def test_get_last_quality_with_history(self):
        kg.update_meta_exploration("test-topic", 7.5, 0.5, False)
        assert self.monitor.get_last_quality("test-topic") == 7.5

    def test_is_topic_blocked_false(self):
        assert self.monitor.is_topic_blocked("active-topic") is False

    def test_is_topic_blocked_true(self):
        kg.mark_topic_done("blocked-topic", "max_count_reached")
        assert self.monitor.is_topic_blocked("blocked-topic") is True


class TestAssessExplorationQuality:
    def setup_method(self):
        self.monitor = MetaCognitiveMonitor()
        state = kg.get_state()
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
        state["knowledge"]["topics"] = {}
        kg._save_state(state)

    def test_assess_quality_new_discovery(self):
        findings = {
            "summary": "Machine learning artificial intelligence deep learning neural networks",
            "sources": ["http://a.com"],
            "papers": []
        }
        quality = self.monitor.assess_exploration_quality("test", findings)
        assert 0 <= quality <= 10

    def test_assess_quality_depth_improvement(self):
        kg.add_knowledge("test", depth=3, summary="Basic info")
        findings = {
            "summary": "A" * 1500,
            "sources": ["http://a.com", "http://b.com", "http://c.com", "http://d.com", "http://e.com"],
            "papers": [{}, {}, {}]
        }
        quality = self.monitor.assess_exploration_quality("test", findings)
        assert quality > 0

    def test_assess_quality_exception_fallback(self):
        findings = {}
        quality = self.monitor.assess_exploration_quality("test", findings)
        assert 0 <= quality <= 10


class TestComputeMarginalReturn:
    def setup_method(self):
        self.monitor = MetaCognitiveMonitor()
        state = kg.get_state()
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
        kg._save_state(state)

    def test_marginal_return_first_exploration(self):
        marginal = self.monitor.compute_marginal_return("new-topic", 8.0)
        assert marginal == 1.0

    def test_marginal_return_improvement(self):
        kg.update_meta_exploration("test", 5.0, 0.0, False)
        marginal = self.monitor.compute_marginal_return("test", 8.0)
        assert marginal > 0

    def test_marginal_return_decline(self):
        kg.update_meta_exploration("test", 8.0, 0.8, False)
        marginal = self.monitor.compute_marginal_return("test", 5.0)
        assert marginal < 0.8


class TestExtractKeywords:
    def test_extract_keywords_fallback(self):
        monitor = MetaCognitiveMonitor(llm_client=None)
        keywords = monitor._extract_keywords("Machine learning and artificial intelligence are important fields")
        assert isinstance(keywords, list)
        assert len(keywords) > 0

    def test_extract_keywords_empty_text(self):
        monitor = MetaCognitiveMonitor(llm_client=None)
        keywords = monitor._extract_keywords("")
        assert keywords == []


class TestDepthScore:
    def test_depth_score_long_summary(self):
        monitor = MetaCognitiveMonitor()
        findings = {"summary": "A" * 2000, "sources": [], "papers": []}
        score = monitor._assess_depth_score(findings)
        assert score > 3

    def test_depth_score_many_sources(self):
        monitor = MetaCognitiveMonitor()
        findings = {"summary": "Short", "sources": ["a", "b", "c", "d", "e", "f"], "papers": []}
        score = monitor._assess_depth_score(findings)
        assert score > 0

    def test_depth_score_balanced(self):
        monitor = MetaCognitiveMonitor()
        findings = {
            "summary": "A" * 1000,
            "sources": ["a", "b", "c"],
            "papers": [{}, {}]
        }
        score = monitor._assess_depth_score(findings)
        assert 0 <= score <= 10


class TestRecordExploration:
    def setup_method(self):
        self.monitor = MetaCognitiveMonitor()
        state = kg.get_state()
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": [],
            "completed_topics": {}
        }
        kg._save_state(state)

    def test_record_exploration(self):
        self.monitor.record_exploration("test-topic", 7.5, 0.5, True)
        assert kg.get_topic_explore_count("test-topic") == 1
        assert self.monitor.get_last_quality("test-topic") == 7.5
        returns = kg.get_topic_marginal_returns("test-topic")
        assert returns == [0.5]
