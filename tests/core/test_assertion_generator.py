# tests/core/test_assertion_generator.py
import pytest
from unittest.mock import Mock
from core.assertion_generator import AssertionGenerator


class TestAssertionGenerator:
    @pytest.fixture
    def generator(self):
        mock_llm = Mock()
        return AssertionGenerator(mock_llm)
    
    def test_validate_good_assertion(self, generator):
        """Test that good assertions pass validation"""
        assert generator._validate("Mamba uses selective state spaces", "Mamba") is True
        assert generator._validate("RLHF aligns models using PPO", "RLHF") is True
    
    def test_validate_too_short(self, generator):
        """Test that short assertions are rejected"""
        assert generator._validate("Mamba is", "Mamba") is False
        assert generator._validate("A", "Mamba") is False
    
    def test_validate_too_long(self, generator):
        long_text = "This is a very long assertion that exceeds the maximum length limit of 200 characters and is therefore rejected by the validation function because it is too long to be a good assertion for the knowledge base"
        assert generator._validate(long_text, "Topic") is False
    
    def test_validate_banned_prefix(self, generator):
        """Test that meta-commentary prefixes are rejected"""
        assert generator._validate("This paper discusses Mamba", "Mamba") is False
        assert generator._validate("The research shows that", "Topic") is False
        assert generator._validate("This article explains", "Topic") is False
    
    def test_validate_topic_repetition(self, generator):
        assert generator._validate("Machine Learning", "Machine Learning") is False
        assert generator._validate("This is about Machine Learning", "Machine Learning") is False
    
    def test_parse_assertions(self, generator):
        """Test parsing assertions from LLM response"""
        response = """
1. First assertion here
2. Second assertion here
- Third with bullet
* Fourth with star
Regular line without prefix
        """
        
        assertions = generator._parse_assertions(response)
        
        assert len(assertions) == 5
        assert "First assertion here" in assertions
        assert "Second assertion here" in assertions
        assert "Third with bullet" in assertions
        assert "Fourth with star" in assertions
        assert "Regular line without prefix" in assertions
    
    def test_generate_with_mock_llm(self, generator):
        """Test generate method with mocked LLM"""
        generator.llm.chat.return_value = """
Mamba uses selective state spaces
Mamba achieves O(N) inference
This paper discusses Mamba
        """
        
        findings = {
            'summary': 'Mamba is a state space model.',
            'sources': [{'title': 'Mamba Paper'}],
            'papers': []
        }
        
        assertions = generator.generate("Mamba", findings, num_assertions=3)
        
        assert len(assertions) == 2
        assert "Mamba uses selective state spaces" in assertions
        assert "Mamba achieves O(N) inference" in assertions
        assert "This paper discusses Mamba" not in assertions
    
    def test_generate_handles_llm_error(self, generator):
        """Test that LLM errors are handled gracefully"""
        generator.llm.chat.side_effect = Exception("API Error")
        
        findings = {'summary': 'Test', 'sources': [], 'papers': []}
        assertions = generator.generate("Test", findings)
        
        assert assertions == []
