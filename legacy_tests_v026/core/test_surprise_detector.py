import pytest
from unittest.mock import Mock
from core.surprise_detector import SurpriseDetector


class TestSurpriseDetector:
    @pytest.fixture
    def detector(self):
        mock_llm = Mock()
        return SurpriseDetector(mock_llm)
    
    def test_generate_assumptions(self, detector):
        detector.llm.chat.return_value = """
我以为：attention机制计算复杂度是O(n^2)
我以为：transformer需要大量训练数据
我以为：self-attention是唯一的注意力机制
"""
        
        assumptions = detector.generate_assumptions("attention mechanism")
        
        assert len(assumptions) == 3
        assert all("我以为：" in a for a in assumptions)
    
    def test_generate_assumptions_empty_response(self, detector):
        detector.llm.chat.return_value = ""
        
        assumptions = detector.generate_assumptions("topic")
        
        assert assumptions == []
    
    def test_generate_assumptions_llm_error(self, detector):
        detector.llm.chat.side_effect = Exception("LLM error")
        
        assumptions = detector.generate_assumptions("topic")
        
        assert assumptions == []
    
    def test_check_surprise_true(self, detector):
        detector.llm.chat.return_value = '{"is_surprise": true, "surprise_level": 0.8}'
        
        findings = {"summary": "发现新的线性注意力机制"}
        assumptions = ["我以为：attention是O(n^2)"]
        
        result = detector.check_surprise(findings, assumptions)
        
        assert result["is_surprise"] is True
        assert result["surprise_level"] == 0.8
    
    def test_check_surprise_false(self, detector):
        detector.llm.chat.return_value = '{"is_surprise": false, "surprise_level": 0.0}'
        
        findings = {"summary": "标准的attention机制"}
        assumptions = ["我以为：attention是O(n^2)"]
        
        result = detector.check_surprise(findings, assumptions)
        
        assert result["is_surprise"] is False
        assert result["surprise_level"] == 0.0
    
    def test_check_surprise_empty_assumptions(self, detector):
        findings = {"summary": "一些发现"}
        
        result = detector.check_surprise(findings, [])
        
        assert result["is_surprise"] is False
        assert result["surprise_level"] == 0.0
    
    def test_check_surprise_llm_error(self, detector):
        detector.llm.chat.side_effect = Exception("LLM error")
        
        findings = {"summary": "发现"}
        assumptions = ["假设"]
        
        result = detector.check_surprise(findings, assumptions)
        
        assert result["is_surprise"] is False
        assert result["surprise_level"] == 0.0
    
    def test_check_surprise_malformed_json(self, detector):
        detector.llm.chat.return_value = "不是有效的JSON"
        
        findings = {"summary": "发现"}
        assumptions = ["假设"]
        
        result = detector.check_surprise(findings, assumptions)
        
        assert result["is_surprise"] is False
        assert result["surprise_level"] == 0.0
