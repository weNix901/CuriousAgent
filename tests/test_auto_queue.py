"""Tests for auto-queue functionality in CuriosityEngine"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.curiosity_engine import CuriosityEngine


class TestExtractKeywords:
    """Test suite for _extract_keywords method"""

    def test_extract_keywords_returns_list(self):
        """Test that _extract_keywords returns a list"""
        engine = CuriosityEngine()
        result = engine._extract_keywords("This is a test text about machine learning and AI agents.")
        assert isinstance(result, list)

    def test_extract_keywords_finds_capitalized_phrases(self):
        """Test that capitalized phrases are extracted"""
        engine = CuriosityEngine()
        text = "The ReAct framework and Chain-of-Thought prompting are important."
        keywords = engine._extract_keywords(text)
        # Check that ReAct is found (may be part of a phrase like "The ReAct")
        has_react = any("ReAct" in kw for kw in keywords)
        has_chain = any("Chain" in kw for kw in keywords)
        assert has_react or has_chain

    def test_extract_keywords_filters_short_words(self):
        """Test that short words are filtered out"""
        engine = CuriosityEngine()
        text = "AI is a big field. The API is useful."
        keywords = engine._extract_keywords(text)
        # Should not include single short words like "AI" or "is"
        for kw in keywords:
            assert len(kw) > 3, f"Keyword '{kw}' is too short"

    def test_extract_keywords_removes_duplicates(self):
        """Test that duplicate keywords are removed"""
        engine = CuriosityEngine()
        text = "Machine Learning and Machine Learning are the same. Machine Learning is great."
        keywords = engine._extract_keywords(text)
        # Check no duplicates (case-insensitive)
        lower_keywords = [k.lower() for k in keywords]
        assert len(lower_keywords) == len(set(lower_keywords))

    def test_extract_keywords_limits_results(self):
        """Test that keyword extraction is limited to reasonable number"""
        engine = CuriosityEngine()
        # Long text with many potential keywords
        text = " ".join([f"Topic{i} is important." for i in range(50)])
        keywords = engine._extract_keywords(text)
        assert len(keywords) <= 10, "Should limit to reasonable number of keywords"

    def test_extract_keywords_handles_empty_text(self):
        """Test that empty text returns empty list"""
        engine = CuriosityEngine()
        keywords = engine._extract_keywords("")
        assert keywords == []

    def test_extract_keywords_handles_none(self):
        """Test that None input returns empty list"""
        engine = CuriosityEngine()
        keywords = engine._extract_keywords(None)
        assert keywords == []


class TestAutoQueueTopics:
    """Test suite for auto_queue_topics method"""

    def test_auto_queue_topics_adds_new_curiosities(self):
        """Test that auto_queue_topics adds new topics to queue"""
        engine = CuriosityEngine()
        
        with patch('core.curiosity_engine.kg') as mock_kg:
            mock_kg.get_state.return_value = {
                "curiosity_queue": [],
                "knowledge": {"topics": {}}
            }
            mock_kg.add_curiosity = MagicMock()
            
            topics = ["neural networks", "deep learning"]
            count = engine.auto_queue_topics(topics, parent_topic="machine learning")
            
            assert count == 2
            assert mock_kg.add_curiosity.call_count == 2

    def test_auto_queue_topics_avoids_duplicates_in_queue(self):
        """Test that existing pending topics are not re-added"""
        engine = CuriosityEngine()
        
        with patch('core.curiosity_engine.kg') as mock_kg:
            mock_kg.get_state.return_value = {
                "curiosity_queue": [
                    {"topic": "neural networks", "status": "pending"}
                ],
                "knowledge": {"topics": {}}
            }
            mock_kg.add_curiosity = MagicMock()
            
            topics = ["neural networks", "deep learning"]
            count = engine.auto_queue_topics(topics, parent_topic="machine learning")
            
            # Only "deep learning" should be added
            assert count == 1
            mock_kg.add_curiosity.assert_called_once()

    def test_auto_queue_topics_avoids_duplicates_case_insensitive(self):
        """Test that duplicate check is case-insensitive"""
        engine = CuriosityEngine()
        
        with patch('core.curiosity_engine.kg') as mock_kg:
            mock_kg.get_state.return_value = {
                "curiosity_queue": [
                    {"topic": "Neural Networks", "status": "pending"}
                ],
                "knowledge": {"topics": {}}
            }
            mock_kg.add_curiosity = MagicMock()
            
            topics = ["neural networks", "deep learning"]
            count = engine.auto_queue_topics(topics, parent_topic="machine learning")
            
            # Only "deep learning" should be added
            assert count == 1

    def test_auto_queue_topics_avoids_done_items(self):
        """Test that done items can be re-added"""
        engine = CuriosityEngine()
        
        with patch('core.curiosity_engine.kg') as mock_kg:
            mock_kg.get_state.return_value = {
                "curiosity_queue": [
                    {"topic": "neural networks", "status": "done"}
                ],
                "knowledge": {"topics": {}}
            }
            mock_kg.add_curiosity = MagicMock()
            
            topics = ["neural networks", "deep learning"]
            count = engine.auto_queue_topics(topics, parent_topic="machine learning")
            
            # Both should be added since "neural networks" is done
            assert count == 2

    def test_auto_queue_topics_sets_correct_reason(self):
        """Test that reason includes parent topic"""
        engine = CuriosityEngine()
        
        with patch('core.curiosity_engine.kg') as mock_kg:
            mock_kg.get_state.return_value = {
                "curiosity_queue": [],
                "knowledge": {"topics": {}}
            }
            mock_kg.add_curiosity = MagicMock()
            
            topics = ["transformer architecture"]
            engine.auto_queue_topics(topics, parent_topic="attention mechanisms")
            
            # Check the reason includes parent topic (using kwargs since we use keyword args)
            call_kwargs = mock_kg.add_curiosity.call_args.kwargs
            reason = call_kwargs.get("reason", "")
            assert "attention mechanisms" in reason
            assert "auto:" in reason.lower() or "found in" in reason.lower()

    def test_auto_queue_topics_handles_empty_list(self):
        """Test that empty topics list returns 0"""
        engine = CuriosityEngine()
        
        with patch('core.curiosity_engine.kg') as mock_kg:
            mock_kg.get_state.return_value = {
                "curiosity_queue": [],
                "knowledge": {"topics": {}}
            }
            
            count = engine.auto_queue_topics([], parent_topic="test")
            assert count == 0

    def test_auto_queue_topics_filters_empty_strings(self):
        """Test that empty strings in topics are filtered"""
        engine = CuriosityEngine()
        
        with patch('core.curiosity_engine.kg') as mock_kg:
            mock_kg.get_state.return_value = {
                "curiosity_queue": [],
                "knowledge": {"topics": {}}
            }
            mock_kg.add_curiosity = MagicMock()
            
            topics = ["valid topic", "", "  ", "another topic"]
            count = engine.auto_queue_topics(topics, parent_topic="test")
            
            # Only non-empty topics should be added
            assert count == 2


class TestAutoQueueIntegration:
    """Integration tests for auto-queue in exploration cycle"""

    def test_auto_queue_not_called_for_shallow_depth(self):
        """Test that auto_queue is not called for shallow exploration"""
        from curious_agent import run_one_cycle
        
        with patch('curious_agent.CuriosityEngine') as MockEngine:
            mock_engine = MagicMock()
            mock_engine.generate_initial_curiosities.return_value = 0
            mock_engine.rescore_all.return_value = 0
            mock_engine.select_next.return_value = None
            MockEngine.return_value = mock_engine
            
            run_one_cycle(depth="shallow")
            
            # auto_queue_topics should not be called for shallow
            mock_engine.auto_queue_topics.assert_not_called()

    def test_auto_queue_called_for_medium_depth(self):
        """Test that auto_queue is called for medium exploration"""
        from curious_agent import run_one_cycle, Explorer
        
        with patch('curious_agent.CuriosityEngine') as MockEngine, \
             patch('curious_agent.Explorer') as MockExplorer:
            
            mock_engine = MagicMock()
            mock_engine.generate_initial_curiosities.return_value = 0
            mock_engine.rescore_all.return_value = 0
            mock_engine.select_next.return_value = {
                "topic": "test topic",
                "score": 8.0,
                "depth": 7
            }
            mock_engine._extract_keywords.return_value = ["keyword1", "keyword2"]
            mock_engine.auto_queue_topics.return_value = 2
            MockEngine.return_value = mock_engine
            
            mock_explorer = MagicMock()
            mock_explorer.explore.return_value = {
                "topic": "test topic",
                "action": "web search",
                "findings": "Some findings with keywords",
                "score": 8.0,
                "notified": False
            }
            MockExplorer.return_value = mock_explorer
            
            run_one_cycle(depth="medium")
            
            # auto_queue_topics should be called for medium
            mock_engine.auto_queue_topics.assert_called_once()

    def test_auto_queue_called_for_deep_depth(self):
        """Test that auto_queue is called for deep exploration"""
        from curious_agent import run_one_cycle
        
        with patch('curious_agent.CuriosityEngine') as MockEngine, \
             patch('curious_agent.Explorer') as MockExplorer:
            
            mock_engine = MagicMock()
            mock_engine.generate_initial_curiosities.return_value = 0
            mock_engine.rescore_all.return_value = 0
            mock_engine.select_next.return_value = {
                "topic": "test topic",
                "score": 8.0,
                "depth": 7
            }
            mock_engine._extract_keywords.return_value = ["keyword1"]
            mock_engine.auto_queue_topics.return_value = 1
            MockEngine.return_value = mock_engine
            
            mock_explorer = MagicMock()
            mock_explorer.explore.return_value = {
                "topic": "test topic",
                "action": "deep search",
                "findings": "Deep findings",
                "score": 8.0,
                "notified": False
            }
            MockExplorer.return_value = mock_explorer
            
            run_one_cycle(depth="deep")
            
            # auto_queue_topics should be called for deep
            mock_engine.auto_queue_topics.assert_called_once()
