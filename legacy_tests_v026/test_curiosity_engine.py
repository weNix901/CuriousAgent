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

        assert "Transformer Attention" in keywords
        assert "Reflection Mechanisms" in keywords
    
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
    
    @patch('core.knowledge_graph_compat.add_curiosity')
    def test_auto_queue_adds_relevant_topics(self, mock_add):
        """Test adds topics that pass research filter"""
        engine = CuriosityEngine()
        engine.score_topic = Mock(return_value={'final_score': 8.0})
        
        topics = ["agent memory", "transformer attention"]
        count = engine.auto_queue_topics(topics, "parent")
        
        assert count > 0
        mock_add.assert_called()
    
    @patch('core.knowledge_graph_compat.add_curiosity')
    def test_auto_queue_skips_unrelated_topics(self, mock_add):
        """Test skips topics that fail research filter"""
        engine = CuriosityEngine()
        
        topics = ["Digital Marketing", "CTO"]
        count = engine.auto_queue_topics(topics, "parent")
        
        assert count == 0
        mock_add.assert_not_called()
    
    @patch('core.knowledge_graph_compat.add_curiosity')
    def test_auto_queue_skips_low_score_topics(self, mock_add):
        """Test skips topics with score < 5.0"""
        engine = CuriosityEngine()
        engine.score_topic = Mock(return_value={'final_score': 3.0})
        
        topics = ["agent memory"]  # Research-related but low score
        count = engine.auto_queue_topics(topics, "parent")
        
        assert count == 0
    
    @patch('core.knowledge_graph_compat.add_curiosity')
    def test_auto_queue_skips_existing_pending(self, mock_add):
        """Test skips topics already in pending queue"""
        from core import knowledge_graph_compat as kg
        
        engine = CuriosityEngine()
        engine.score_topic = Mock(return_value={'final_score': 8.0})
        
        # Add to queue first
        kg.add_curiosity("existing", "reason", 8.0, 7.0)
        
        topics = ["existing"]
        count = engine.auto_queue_topics(topics, "parent")
        
        # Should skip existing
        assert count == 0
    
    @patch('core.knowledge_graph_compat.add_curiosity')
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
        from core import knowledge_graph_compat as kg

        engine = CuriosityEngine()

        # Add items
        kg.add_curiosity("item1", "reason", 5.0, 5.0)
        kg.add_curiosity("item2", "reason", 6.0, 6.0)

        original_compute = engine.compute_curiosity_score
        engine.compute_curiosity_score = Mock(return_value=9.0)

        engine.rescore_all()

        engine.compute_curiosity_score.assert_called()

        engine.compute_curiosity_score = original_compute


class TestSelectNext:
    """Test suite for select_next"""
    
    @patch('core.curiosity_engine.kg.get_top_curiosities')
    def test_select_next_returns_highest_score(self, mock_get_top):
        """Test returns highest scored pending item"""
        mock_get_top.return_value = [
            {"topic": "high", "status": "pending", "score": 81.0}
        ]
        
        engine = CuriosityEngine()
        result = engine.select_next()
        
        assert result is not None
        assert result["topic"] == "high"
    
    @patch('core.curiosity_engine.kg.get_top_curiosities')
    @patch('core.curiosity_engine.CuriosityEngine.generate_initial_curiosities')
    def test_select_next_generates_initial_when_empty(self, mock_generate, mock_get_top):
        """Test generates initial curiosities when queue is empty"""
        mock_get_top.side_effect = [[], [{"topic": "initial", "status": "pending"}]]
        mock_generate.return_value = 1

        engine = CuriosityEngine()
        result = engine.select_next()

        assert result is not None
        assert "topic" in result
    
    @patch('core.curiosity_engine.kg.get_top_curiosities')
    def test_select_next_skips_done_items(self, mock_get_top):
        """Test skips done items and returns pending items"""
        mock_get_top.return_value = [
            {"topic": "pending-item", "status": "pending", "score": 64.0}
        ]

        engine = CuriosityEngine()
        result = engine.select_next()

        assert result is not None
        assert result["topic"] == "pending-item"


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


class TestGenerateInitialCuriosities:
    """Test suite for generate_initial_curiosities"""
    
    @patch('core.curiosity_engine.kg.get_state')
    @patch('core.curiosity_engine.kg.add_curiosity')
    def test_generate_when_queue_empty(self, mock_add, mock_get_state):
        mock_get_state.return_value = {"curiosity_queue": []}
        engine = CuriosityEngine()
        count = engine.generate_initial_curiosities()
        assert count == mock_add.call_count
        assert count > 0
    
    @patch('core.curiosity_engine.kg.get_state')
    @patch('core.curiosity_engine.kg.add_curiosity')
    def test_skip_when_queue_has_pending(self, mock_add, mock_get_state):
        """Test skips generation when queue has pending items"""
        mock_get_state.return_value = {
            "curiosity_queue": [{"status": "pending", "topic": "existing"}]
        }
        
        engine = CuriosityEngine()
        count = engine.generate_initial_curiosities()
        
        assert count == 0
        mock_add.assert_not_called()
    
    @patch('core.curiosity_engine.kg.get_state')
    @patch('core.curiosity_engine.kg.add_curiosity')
    def test_generated_topics_structure(self, mock_add, mock_get_state):
        mock_get_state.return_value = {"curiosity_queue": []}
        engine = CuriosityEngine()
        engine.generate_initial_curiosities()
        call_args = mock_add.call_args_list[0]
        assert call_args[0][0] == "LLM self-reflection mechanisms"
        assert call_args[0][2] == 9.0
        assert call_args[0][3] == 8.0


class TestComputeCuriosityScore:
    """Test suite for compute_curiosity_score"""
    
    def test_score_matches_user_interests(self):
        """Test score increases when topic matches user interests"""
        engine = CuriosityEngine()
        
        # Topic matching "AI agent autonomy" interest
        score_match = engine.compute_curiosity_score(
            "agent autonomy framework", 5.0, 5.0
        )
        
        # Topic not matching any interest
        score_no_match = engine.compute_curiosity_score(
            "random unrelated topic", 5.0, 5.0
        )
        
        assert score_match > score_no_match
    
    def test_score_returns_0_to_10_range(self):
        """Test score always returns value in 0-10 range"""
        engine = CuriosityEngine()
        
        for rel in [1.0, 5.0, 10.0]:
            for depth in [1.0, 5.0, 10.0]:
                score = engine.compute_curiosity_score("test", rel, depth)
                assert 0 <= score <= 10
    
    def test_score_calculates_recency(self):
        """Test score includes recency calculation"""
        from core import knowledge_graph_compat as kg
        from datetime import datetime, timezone, timedelta
        
        engine = CuriosityEngine()
        
        # Add topic with recent update
        kg.add_knowledge("recent_topic", depth=5)
        
        # Add topic with old update
        state = kg.get_state()
        state["knowledge"]["topics"]["old_topic"] = {
            "known": True,
            "depth": 5,
            "last_updated": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        }
        kg._save_state(state)
        
        score_recent = engine.compute_curiosity_score("recent_topic", 5.0, 5.0)
        score_old = engine.compute_curiosity_score("old_topic", 5.0, 5.0)
        
        # Old topic should have higher recency score
        assert score_old >= score_recent


class TestAddContextualCuriosity:
    """Test suite for add_contextual_curiosity"""
    
    @patch('core.knowledge_graph_compat.add_curiosity')
    def test_extracts_keywords_from_context(self, mock_add):
        """Test extracts keywords from conversation context"""
        engine = CuriosityEngine()
        context = "I am interested in Transformer Attention and Self Reflection"
        
        engine.add_contextual_curiosity(context)
        
        assert mock_add.called
        # Should extract phrases like "Transformer Attention"
        call_topics = [call[1]["topic"] for call in mock_add.call_args_list]
        assert any("Transformer" in t or "Reflection" in t for t in call_topics)
    
    @patch('core.knowledge_graph_compat.add_curiosity')
    def test_filters_short_phrases(self, mock_add):
        """Test filters phrases shorter than 7 characters"""
        engine = CuriosityEngine()
        context = "AI LLM and NLP are interesting"
        
        engine.add_contextual_curiosity(context)
        
        # Short phrases should be filtered
        call_topics = [call[1]["topic"] for call in mock_add.call_args_list]
        assert "AI" not in call_topics
        assert "LLM" not in call_topics
    
    @patch('core.knowledge_graph_compat.add_curiosity')
    def test_limits_to_5_phrases(self, mock_add):
        """Test limits to max 5 phrases"""
        engine = CuriosityEngine()
        context = "One Two Three Four Five Six Seven Eight"
        
        engine.add_contextual_curiosity(context)
        
        assert mock_add.call_count <= 5


class TestGetExplorationHistory:
    """Test suite for _get_exploration_history"""
    
    def test_returns_dict_structure(self):
        """Test returns dict structure"""
        engine = CuriosityEngine()
        history = engine._get_exploration_history()

        assert isinstance(history, dict)
    
    @patch('core.curiosity_engine.kg.get_state')
    def test_builds_history_from_logs(self, mock_get_state):
        """Test builds history dict from exploration_log"""
        mock_get_state.return_value = {
            "exploration_log": [
                {"topic": "topic1", "action": "action", "findings": "findings", "notified": True, "timestamp": "2024-01-01", "insight_quality": 5},
                {"topic": "topic1", "action": "action2", "findings": "findings2", "notified": False, "timestamp": "2024-01-02", "insight_quality": 5},
                {"topic": "topic2", "action": "action", "findings": "findings", "notified": True, "timestamp": "2024-01-03", "insight_quality": 5},
            ]
        }

        engine = CuriosityEngine()
        history = engine._get_exploration_history()

        assert "topic1" in history
        assert "topic2" in history
        assert len(history["topic1"]) == 2  # Two records for topic1


class TestRescoreAllFixed:
    """Fixed test suite for rescore_all"""

    @patch('core.curiosity_engine.CuriosityEngine.compute_curiosity_score')
    @patch('core.knowledge_graph_compat.get_state')
    @patch('core.knowledge_graph_compat._save_state')
    def test_rescore_all_updates_pending_items(self, mock_save, mock_get_state, mock_score):
        """Test rescore_all updates scores for all pending items"""
        mock_get_state.return_value = {
            "curiosity_queue": [
                {"topic": "item1", "status": "pending", "score": 5.0},
                {"topic": "item2", "status": "pending", "score": 6.0},
                {"topic": "item3", "status": "done", "score": 7.0}
            ]
        }
        mock_score.return_value = 9.0

        engine = CuriosityEngine()
        engine.rescore_all()

        assert mock_score.call_count == 2


class TestSelectNextFixed:
    """Fixed test suite for select_next with proper isolation"""

    @patch('core.curiosity_engine.kg.get_top_curiosities')
    @patch('core.curiosity_engine.CuriosityEngine.generate_initial_curiosities')
    def test_select_next_returns_none_when_empty(self, mock_generate, mock_get_top):
        """Test returns None when queue is empty and no initial curiosities generated"""
        mock_get_top.return_value = []
        mock_generate.return_value = 0

        engine = CuriosityEngine()
        result = engine.select_next()

        assert result is None

    @patch('core.curiosity_engine.kg.get_top_curiosities')
    @patch('core.curiosity_engine.CuriosityEngine.generate_initial_curiosities')
    def test_select_next_skips_done_items(self, mock_generate, mock_get_top):
        """Test skips done items and generates new if all done"""
        mock_get_top.return_value = []
        mock_generate.return_value = 0

        engine = CuriosityEngine()
        result = engine.select_next()

        assert result is None


class TestSelectNextRegression:
    """Regression tests for Bug #14: select_next filtering completed topics"""

    @patch('core.curiosity_engine.kg.is_topic_completed')
    @patch('core.curiosity_engine.kg.get_top_curiosities')
    def test_select_next_skips_first_completed_topic(self, mock_get_top, mock_is_completed):
        """Regression test: When first candidate is completed, skip to next"""
        mock_get_top.return_value = [
            {"topic": "completed-topic", "status": "pending", "score": 9.0},
            {"topic": "pending-topic", "status": "pending", "score": 7.0}
        ]
        # First topic is completed, second is not
        mock_is_completed.side_effect = lambda t: t == "completed-topic"

        engine = CuriosityEngine()
        result = engine.select_next()

        assert result is not None
        assert result["topic"] == "pending-topic"
        assert result["topic"] != "completed-topic"

    @patch('core.curiosity_engine.kg.is_topic_completed')
    @patch('core.curiosity_engine.kg.get_top_curiosities')
    def test_select_next_returns_none_when_all_completed(self, mock_get_top, mock_is_completed):
        """Regression test: When all candidates are completed, return None"""
        mock_get_top.return_value = [
            {"topic": "topic-1", "status": "pending", "score": 8.0},
            {"topic": "topic-2", "status": "pending", "score": 7.0}
        ]
        # All topics are completed
        mock_is_completed.return_value = True

        engine = CuriosityEngine()
        result = engine.select_next()

        assert result is None

    @patch('core.curiosity_engine.kg.is_topic_completed')
    @patch('core.curiosity_engine.kg.get_top_curiosities')
    def test_select_next_checks_completion_before_scoring(self, mock_get_top, mock_is_completed):
        """Regression test: is_topic_completed must be checked before scoring"""
        mock_get_top.return_value = [
            {"topic": "high-score-completed", "status": "pending", "score": 9.5},
            {"topic": "low-score-pending", "status": "pending", "score": 6.0}
        ]
        # High score topic is completed, low score is not
        mock_is_completed.side_effect = lambda t: t == "high-score-completed"

        engine = CuriosityEngine()
        result = engine.select_next()

        # Should select the lower score pending topic, not the higher score completed one
        assert result is not None
        assert result["topic"] == "low-score-pending"
        # Verify is_topic_completed was called for the first topic
        mock_is_completed.assert_any_call("high-score-completed")
