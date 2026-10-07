import pytest
from unittest.mock import Mock, patch
from core.insight_synthesizer import InsightSynthesizer, Pattern, Hypothesis


def test_synthesize_basic():
    synthesizer = InsightSynthesizer()
    
    # Mock LLM responses
    with patch.object(synthesizer, 'llm') as mock_llm:
        mock_llm.chat.return_value = '''
        {
            "patterns": [
                {"pattern": "test pattern", "supporting_snippets": ["s1"], "related_sub_topics": ["t1"]}
            ],
            "hypotheses": [
                {"hypothesis": "test hypothesis", "type": "causal", "reasoning": "test reasoning"}
            ]
        }
        '''
        
        sub_topic_results = {
            "sub1": [{"snippet": "test snippet"}]
        }
        
        # Should not crash
        insights = synthesizer.synthesize("test_topic", sub_topic_results)
        
        assert isinstance(insights, list)


def test_compute_confidence():
    synthesizer = InsightSynthesizer()
    
    hypothesis = Hypothesis(
        hypothesis="test",
        type="causal",
        reasoning="test",
        supporting_snippets=["s1", "s2", "s3", "s4", "s5"]
    )
    
    confidence = synthesizer.compute_confidence(hypothesis, ["s1", "s2", "s3", "s4", "s5"])
    
    assert 0.0 <= confidence <= 1.0


def test_parse_patterns_valid_json():
    synthesizer = InsightSynthesizer()
    
    response = '{"patterns": [{"pattern": "p1", "supporting_snippets": ["s1"], "related_sub_topics": ["t1"]}]}'
    patterns = synthesizer._parse_patterns(response)
    
    assert len(patterns) == 1
    assert patterns[0].pattern == "p1"


def test_parse_hypotheses_valid_json():
    synthesizer = InsightSynthesizer()
    
    response = '{"hypotheses": [{"hypothesis": "h1", "type": "causal", "reasoning": "r1", "supporting_snippets": ["s1"]}]}'
    hypotheses = synthesizer._parse_hypotheses(response)
    
    assert len(hypotheses) == 1
    assert hypotheses[0].hypothesis == "h1"
