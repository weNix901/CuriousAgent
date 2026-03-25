import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import Mock, patch
from core.meta_cognitive_monitor import MetaCognitiveMonitor
from core import knowledge_graph as kg
from tests.test_utils import isolated_knowledge_graph, create_test_topic


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
    def test_get_explore_count_new_topic(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            assert monitor.get_explore_count(create_test_topic("new-topic")) == 0

    def test_get_explore_count_existing(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            test_topic = create_test_topic("count-topic")
            kg_module.update_meta_exploration(test_topic, 7.0, 0.5, False)
            assert monitor.get_explore_count(test_topic) == 1

    def test_get_marginal_returns_empty(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            assert monitor.get_marginal_returns(create_test_topic("new-topic")) == []

    def test_get_marginal_returns_with_data(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            test_topic = create_test_topic("returns-topic")
            kg_module.update_meta_exploration(test_topic, 7.0, 0.5, False)
            kg_module.update_meta_exploration(test_topic, 8.0, 0.3, False)
            returns = monitor.get_marginal_returns(test_topic)
            assert len(returns) == 2
            assert returns == [0.5, 0.3]

    def test_get_last_quality_no_history(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            assert monitor.get_last_quality(create_test_topic("new-topic")) == 0.0

    def test_get_last_quality_with_history(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            test_topic = create_test_topic("quality-topic")
            kg_module.update_meta_exploration(test_topic, 7.5, 0.5, False)
            assert monitor.get_last_quality(test_topic) == 7.5

    def test_is_topic_blocked_false(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            assert monitor.is_topic_blocked(create_test_topic("active-topic")) is False

    def test_is_topic_blocked_true(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            test_topic = create_test_topic("blocked-topic")
            kg_module.mark_topic_done(test_topic, "max_count_reached")
            assert monitor.is_topic_blocked(test_topic) is True


class TestAssessExplorationQuality:
    def test_assess_quality_new_discovery(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            findings = {
                "summary": "Machine learning artificial intelligence deep learning neural networks",
                "sources": ["http://a.com"],
                "papers": []
            }
            quality = monitor.assess_exploration_quality(create_test_topic("discovery"), findings)
            assert 0 <= quality <= 10

    def test_assess_quality_depth_improvement(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            test_topic = create_test_topic("depth-topic")
            kg_module.add_knowledge(test_topic, depth=3, summary="Basic info")
            findings = {
                "summary": "A" * 1500,
                "sources": ["http://a.com", "http://b.com", "http://c.com", "http://d.com", "http://e.com"],
                "papers": [{}, {}, {}]
            }
            quality = monitor.assess_exploration_quality(test_topic, findings)
            assert quality > 0

    def test_assess_quality_exception_fallback(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            findings = {}
            quality = monitor.assess_exploration_quality(create_test_topic("fallback"), findings)
            assert 0 <= quality <= 10


class TestComputeMarginalReturn:
    def test_marginal_return_first_exploration(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            marginal = monitor.compute_marginal_return(create_test_topic("first-explore"), 8.0)
            assert marginal == 1.0

    def test_marginal_return_improvement(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            test_topic = create_test_topic("improvement-topic")
            kg_module.update_meta_exploration(test_topic, 5.0, 0.0, False)
            marginal = monitor.compute_marginal_return(test_topic, 8.0)
            assert marginal > 0

    def test_marginal_return_decline(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            test_topic = create_test_topic("decline-topic")
            kg_module.update_meta_exploration(test_topic, 8.0, 0.8, False)
            marginal = monitor.compute_marginal_return(test_topic, 5.0)
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
    def test_record_exploration(self):
        with isolated_knowledge_graph() as kg_module:
            monitor = MetaCognitiveMonitor()
            test_topic = create_test_topic("record-topic")
            monitor.record_exploration(test_topic, 7.5, 0.5, True)
            assert kg_module.get_topic_explore_count(test_topic) == 1
            assert monitor.get_last_quality(test_topic) == 7.5
            returns = kg_module.get_topic_marginal_returns(test_topic)
            assert returns == [0.5]
