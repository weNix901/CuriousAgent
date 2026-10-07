import pytest
from unittest.mock import Mock
from core.quality_v2 import QualityV2Assessor


def test_semantic_novelty_cold_start():
    mock_llm = Mock()
    assessor = QualityV2Assessor(mock_llm)
    
    novelty = assessor._calculate_semantic_novelty("", "new content")
    assert novelty == 1.0


def test_semantic_novelty_with_similarity():
    mock_llm = Mock()
    mock_llm.chat = Mock(return_value="0.3")
    assessor = QualityV2Assessor(mock_llm)
    
    novelty = assessor._calculate_semantic_novelty("old summary", "new summary")
    assert novelty == 0.7


def test_assess_similarity_parsing():
    mock_llm = Mock()
    mock_llm.chat = Mock(return_value="Similarity: 0.75")
    assessor = QualityV2Assessor(mock_llm)
    
    result = assessor._assess_similarity("text1", "text2")
    assert result == 0.75


def test_fallback_assessment():
    mock_llm = Mock()
    assessor = QualityV2Assessor(mock_llm)
    
    findings = {
        "summary": "a" * 400,
        "sources": ["url1", "url2"],
        "papers": ["paper1"]
    }
    
    score = assessor.fallback_quality_assessment(findings)
    expected = min(10, 400/200 + 2*1.5 + 1*2)
    assert score == expected
