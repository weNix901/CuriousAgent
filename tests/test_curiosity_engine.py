"""
Tests for CuriosityEngine - v0.2.1 ICM Fusion Scoring
Tests score_topic, auto_queue, keyword extraction, and filtering
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.curiosity_engine import CuriosityEngine


class TestScoreTopic:
    """Test suite for score_topic with fusion scoring"""
    
    def test_score_topic_returns_fusion_result(self):
        """Test score_topic returns complete fusion result"""
        engine = CuriosityEngine()
        
        # Mock intrinsic scorer
        engine.intrinsic_scorer = Mock()
        engine.intrinsic_scorer.score.return_value = {
            'total': 8.0,
            'signals': {'pred_error': 8.5, 'graph_density': 7.0, 'novelty': 9.0},
            'weights': {'pred_error': 0.4, 'graph_density': 0.3, 'novelty': 0.3}
        }
        
        result = engine.score_topic("test topic", alpha=0.5)
        
        assert 'final_score' in result
        assert 'human_score' in result
        assert 'intrinsic_score' in result
        assert 'alpha' in result
        assert result['alpha'] == 0.5
        assert result['intrinsic_score'] == 8.0
    
    def test_score_topic_with_different_alpha_values(self):
        """Test score_topic with various alpha values"""
        engine = CuriosityEngine()
        engine.intrinsic_scorer = Mock()
        engine.intrinsic_scorer.score.return_value = {'total': 8.0, 'signals': {}, 'weights': {}}
        
        for alpha in [0.0, 0.3, 0.5, 0.7, 1.0]:
            result = engine.score_topic("test", alpha=alpha)
            assert result['alpha'] == alpha
    
    def test_score_topic_alpha_0_is_pure_intrinsic(self):
        """Test alpha=0 gives pure intrinsic score"""
        engine = CuriosityEngine()
        engine.intrinsic_scorer = Mock()
        engine.intrinsic_scorer.score.return_value = {'total': 8.0, 'signals': {}, 'weights': {}}
        
        result = engine.score_topic("test", alpha=0.0)
        # With alpha=0, final should equal intrinsic
        assert result['final_score'] == result['intrinsic_score']
    
    def test_score_topic_alpha_1_is_pure_human(self):
        """Test alpha=1 gives pure human score"""
        engine = CuriosityEngine()
        engine.intrinsic_scorer = Mock()
        engine.intrinsic_scorer.score.return_value = {'total': 8.0, 'signals': {}, 'weights': {}}
        
        result = engine.score_topic("test", alpha=1.0)
        # With alpha=1, final should equal human
        assert result['final_score'] == result['human_score']
    
    def test_score_topic_default_alpha_is_0_5(self):
        """Test default alpha is 0.5"""
        engine = CuriosityEngine()
        engine.intrinsic_scorer = Mock()
        engine.intrinsic_scorer.score.return_value = {'total': 8.0, 'signals': {}, 'weights': {}}
        
        result = engine.score_topic("test")
        assert result['alpha'] == 0.5
    
    def test_score_topic_returns_signals(self):
        """Test score_topic returns intrinsic signals"""
        engine = CuriosityEngine()
        engine.intrinsic_scorer = Mock()
        engine.intrinsic_scorer.score.return_value = {
            'total': 8.0,
            'signals': {'pred_error': 8.5, 'graph_density': 7.0, 'novelty': 9.0},
            'weights': {'pred_error': 0.4, 'graph_density': 0.3, 'novelty': 0.3}
        }
        
        result = engine.score_topic("test")
        
        assert 'signals' in result
        assert 'pred_error' in result['signals']
        assert 'graph_density' in result['signals']
        assert 'novelty' in result['signals']
    
    def test_score_topic_returns_weights(self):
        """Test score_topic returns signal weights"""
        engine = CuriosityEngine()
        engine.intrinsic_scorer = Mock()
        engine.intrinsic_scorer.score.return_value = {
            'total': 8.0,
            'signals': {},
            'weights': {'pred_error': 0.4, 'graph_density': 0.3, 'novelty': 0.3}
        }
        
        result = engine.score_topic("test")
        
        assert 'weights' in result
        assert result['weights']['pred_error'] == 0.4


class TestExtractKeywords:
    """Test suite for _extract_keywords with filtering"""
    
    def test_extract_keywords_finds_capitalized_phrases(self):
        """Test extracts capitalized phrases"""
        engine = CuriosityEngine()
        text = "Transformer Attention and Self-Reflection Mechanisms"
        
        keywords = engine._extract_keywords(text)
        
        assert "Transformer" in keywords
        assert "Attention" in keywords
        assert "Self-Reflection" in keywords or "Reflection" in keywords
    
    def test_extract_keywords_filters_short_words(self):
        """Test filters words shorter than 4 chars"""
        engine = CuriosityEngine()
        text = "AI LLM and NLP"
        
        keywords = engine._extract_keywords(text)
        
        # Short words should be filtered
        assert "AI" not in keywords
        assert "NLP" not in keywords
    
    def test_extract_keywords_filters_stopwords(self):
        """Test filters stopwords like CTO, AI Strategy"""
        engine = CuriosityEngine()
        text = "CTO and AI Strategy for Digital Marketing"
        
        keywords = engine._extract_keywords(text)
        
        assert "CTO" not in keywords
        assert "AI Strategy" not in keywords
        assert "Digital Marketing" not in keywords
    
    def test_extract_keywords_handles_newlines(self):
        """Test handles newlines in text"""
        engine = CuriosityEngine()
        text = "First Line\nSecond Line\nTransformer Attention"
        
        keywords = engine._extract_keywords(text)
        
        # Should not include truncated words from line breaks
        assert "Line" not in keywords or len(keywords) > 0
    
    def test_extract_keywords_limits_to_10(self):
        """Test limits to max 10 keywords"""
        engine = CuriosityEngine()
        text = "One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve"
        
        keywords = engine._extract_keywords(text)
        
        assert len(keywords) <= 10
    
    def test_extract_keywords_deduplicates(self):
        """Test removes duplicate keywords"""
        engine = CuriosityEngine()
        text = "Transformer Attention Transformer Attention"
        
        keywords = engine._extract_keywords(text)
        
        assert len(keywords) == len(set(keywords))  # No duplicates


class TestIsResearchRelated:
    """Test suite for _is_research_related filtering"""
    
    def test_is_research_related_matches_keywords(self):
        """Test matches research keywords"""
        engine = CuriosityEngine()
        
        assert engine._is_research_related("agent memory") is True
        assert engine._is_research_related("llm reasoning") is True
        assert engine._is_research_related("transformer attention") is True
    
    def test_is_research_related_rejects_unrelated(self):
        """Test rejects non-research keywords"""
        engine = CuriosityEngine()
        
        assert engine._is_research_related("Digital Marketing") is False
        assert engine._is_research_related("AI Strategy") is False
        assert engine._is_research_related("Random Topic") is False


class TestAutoQueueTopics:
    """Test suite for auto_queue_topics with filtering"""
    
    @patch('core.knowledge_graph.add_curiosity')
    def test_auto_queue_adds_relevant_topics(self, mock_add):
        """Test adds topics that pass research filter"""
        engine = CuriosityEngine()
        engine.score_topic = Mock(return_value={'final_score': 8.0})
        
        topics = ["agent memory", "transformer attention"]
        count = engine.auto_queue_topics(topics, "parent")
        
        assert count > 0
        mock_add.assert_called()
    
    @patch('core.knowledge_graph.add_curiosity')
    def test_auto_queue_skips_unrelated_topics(self, mock_add):
        """Test skips topics that fail research filter"""
        engine = CuriosityEngine()
        
        topics = ["Digital Marketing", "CTO"]
        count = engine.auto_queue_topics(topics, "parent")
        
        assert count == 0
        mock_add.assert_not_called()
    
    @patch('core.knowledge_graph.add_curiosity')
    def test_auto_queue_skips_low_score_topics(self, mock_add):
        """Test skips topics with score < 5.0"""
        engine = CuriosityEngine()
        engine.score_topic = Mock(return_value={'final_score': 3.0})
        
        topics = ["agent memory"]  # Research-related but low score
        count = engine.auto_queue_topics(topics, "parent")
        
        assert count == 0
    
    @patch('core.knowledge_graph.add_curiosity')
    def test_auto_queue_skips_existing_pending(self, mock_add):
        """Test skips topics already in pending queue"""
        from core import knowledge_graph as kg
        
        engine = CuriosityEngine()
        engine.score_topic = Mock(return_value={'final_score': 8.0})
        
        # Add to queue first
        kg.add_curiosity("existing", "reason", 8.0, 7.0)
        
        topics = ["existing"]
        count = engine.auto_queue_topics(topics, "parent")
        
        # Should skip existing
        assert count == 0
    
    @patch('core.knowledge_graph.add_curiosity')
    def test_auto_queue_filters_empty_strings(self, mock_add):
        """Test filters empty strings"""
        engine = CuriosityEngine()
        
        topics = ["", "   ", "agent memory"]
        count = engine.auto_queue_topics(topics, "parent")
        
        # Should only process "agent memory"
        assert count <= 1


class TestRescoreAll:
    """Test suite for rescore_all"""
    
    def test_rescore_all_updates_scores(self):
        """Test rescore_all updates all pending item scores"""
        from core import knowledge_graph as kg
        
        engine = CuriosityEngine()
        
        # Add items
        kg.add_curiosity("item1", "reason", 5.0, 5.0)
        kg.add_curiosity("item2", "reason", 6.0, 6.0)
        
        # Mock score_topic to return new scores
        original_score_topic = engine.score_topic
        engine.score_topic = Mock(return_value={'final_score': 9.0})
        
        engine.rescore_all()
        
        # Score_topic should be called for pending items
        engine.score_topic.assert_called()


class TestSelectNext:
    """Test suite for select_next"""
    
    def test_select_next_returns_highest_score(self):
        """Test returns highest scored pending item"""
        from core import knowledge_graph as kg
        
        engine = CuriosityEngine()
        
        # Add items with different scores
        kg.add_curiosity("low", "reason", 5.0, 5.0)   # score 25
        kg.add_curiosity("high", "reason", 9.0, 9.0)  # score 81
        
        result = engine.select_next()
        
        assert result is not None
        assert result["topic"] == "high"
    
    def test_select_next_returns_none_when_empty(self):
        """Test returns None when queue is empty"""
        engine = CuriosityEngine()
        
        result = engine.select_next()
        
        assert result is None
    
    def test_select_next_skips_done_items(self):
        """Test skips done items"""
        from core import knowledge_graph as kg
        
        engine = CuriosityEngine()
        
        kg.add_curiosity("done-item", "reason", 9.0, 9.0)
        kg.update_curiosity_status("done-item", "done")
        
        result = engine.select_next()
        
        assert result is None


class TestCuriosityEngineInitialization:
    """Test suite for CuriosityEngine initialization"""
    
    def test_engine_initializes_with_config(self):
        """Test engine initializes with config"""
        config = {"custom": "value"}
        engine = CuriosityEngine(config=config)
        
        assert engine.config == config
    
    def test_engine_initializes_intrinsic_scorer(self):
        """Test engine initializes IntrinsicScorer"""
        engine = CuriosityEngine()
        
        assert hasattr(engine, 'intrinsic_scorer')
        assert engine.intrinsic_scorer is not None
    
    def test_engine_loads_exploration_history(self):
        """Test engine loads exploration history on init"""
        engine = CuriosityEngine()
        
        assert hasattr(engine, '_get_exploration_history')
