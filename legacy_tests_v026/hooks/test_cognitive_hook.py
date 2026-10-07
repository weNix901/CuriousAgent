"""Unit tests for CognitiveHook."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from unittest.mock import MagicMock, patch
from core.hooks.cognitive_hook import (
    CognitiveHook,
    ConfidenceLevel,
    AnswerStrategy,
    CognitiveGuidance,
)


class TestConfidenceLevel:
    """Test confidence level classification."""

    def test_novice_below_0_3(self):
        assert ConfidenceLevel.from_confidence(0.0) == ConfidenceLevel.NOVICE
        assert ConfidenceLevel.from_confidence(0.29) == ConfidenceLevel.NOVICE

    def test_beginner_0_3_to_0_6(self):
        assert ConfidenceLevel.from_confidence(0.3) == ConfidenceLevel.BEGINNER
        assert ConfidenceLevel.from_confidence(0.5) == ConfidenceLevel.BEGINNER

    def test_intermediate_0_6_to_0_85(self):
        assert ConfidenceLevel.from_confidence(0.6) == ConfidenceLevel.INTERMEDIATE
        assert ConfidenceLevel.from_confidence(0.8) == ConfidenceLevel.INTERMEDIATE

    def test_expert_above_0_85(self):
        assert ConfidenceLevel.from_confidence(0.85) == ConfidenceLevel.EXPERT
        assert ConfidenceLevel.from_confidence(1.0) == ConfidenceLevel.EXPERT


class TestCognitiveHook:
    """Test CognitiveHook core methods."""

    def test_init_with_config(self):
        """Hook should initialize with config values."""
        config = {
            "confidence_threshold": 0.7,
            "auto_inject_unknowns": False,
            "search_before_llm": False,
        }
        hook = CognitiveHook(config)
        
        assert hook.confidence_threshold == 0.7
        assert hook.auto_inject == False
        assert hook.search_before_llm == False

    def test_init_defaults(self):
        """Hook should use defaults for missing config."""
        hook = CognitiveHook({})
        
        assert hook.confidence_threshold == 0.6
        assert hook.auto_inject == True
        assert hook.search_before_llm == True

    def test_build_guidance_expert(self):
        """Expert level should recommend KG answer."""
        hook = CognitiveHook({})
        guidance = hook.build_guidance("FlashAttention", 0.9, ["implementation"])
        
        assert guidance.level == ConfidenceLevel.EXPERT
        assert guidance.should_search == False
        assert guidance.should_inject == False
        assert "🟢" in guidance.guidance_message

    def test_build_guidance_beginner(self):
        """Beginner level should recommend search + inject."""
        hook = CognitiveHook({})
        guidance = hook.build_guidance("FlashAttention", 0.4, ["implementation", "benchmark"])
        
        assert guidance.level == ConfidenceLevel.BEGINNER
        assert guidance.should_search == True
        assert guidance.should_inject == True
        assert "🟠" in guidance.guidance_message

    def test_build_guidance_novice(self):
        """Novice level should always inject."""
        hook = CognitiveHook({})
        guidance = hook.build_guidance("UnknownTopic", 0.1, [])
        
        assert guidance.level == ConfidenceLevel.NOVICE
        assert guidance.should_search == True
        assert guidance.should_inject == True
        assert "🔴" in guidance.guidance_message
        assert "ALWAYS inject" in guidance.guidance_message

    def test_detect_strategy_kg_answer(self):
        """Should detect KG answer from response."""
        hook = CognitiveHook({})
        strategy = hook.detect_strategy("Based on my knowledge graph, FlashAttention is...")
        
        assert strategy == AnswerStrategy.KG_ANSWER

    def test_detect_strategy_search_answer(self):
        """Should detect search-based answer."""
        hook = CognitiveHook({})
        strategy = hook.detect_strategy("According to my web search results, I found that...")
        
        assert strategy == AnswerStrategy.SEARCH_ANSWER

    def test_detect_strategy_llm_answer(self):
        """Should detect LLM fallback answer."""
        hook = CognitiveHook({})
        strategy = hook.detect_strategy("FlashAttention is a technique for...")
        
        assert strategy == AnswerStrategy.LLM_ANSWER
