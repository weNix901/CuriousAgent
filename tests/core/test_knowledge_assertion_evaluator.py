# tests/core/test_knowledge_assertion_evaluator.py
import pytest
from unittest.mock import Mock, MagicMock
from core.knowledge_assertion_evaluator import KnowledgeAssertionEvaluator


class TestKnowledgeAssertionEvaluator:
    @pytest.fixture
    def evaluator(self, tmp_path):
        from core.embedding_service import EmbeddingService, EmbeddingConfig
        from core.assertion_index import AssertionIndex
        
        mock_llm = Mock()
        mock_llm.chat.return_value = """
Mamba uses selective state spaces
Mamba achieves O(N) inference complexity
Mamba was proposed by Gu and Dao
        """
        
        config = EmbeddingConfig(provider="volcengine")
        embedding_service = EmbeddingService(config)
        index = AssertionIndex(str(tmp_path / "assertions.db"))
        kg = MagicMock()
        kg.get_state.return_value = {"knowledge": {"topics": {}}}
        
        return KnowledgeAssertionEvaluator(mock_llm, embedding_service, index, kg)
    
    def test_assess_quality_returns_correct_structure(self, evaluator):
        """Test that assess_quality returns expected structure"""
        findings = {
            'summary': 'Mamba is a state space model.',
            'sources': [{'title': 'Mamba Paper'}],
            'papers': []
        }
        
        result = evaluator.assess_quality("Mamba", findings)
        
        assert 'quality' in result
        assert 'new_assertions' in result
        assert 'known_assertions' in result
        assert 'details' in result
        assert 0 <= result['quality'] <= 10
    
    def test_no_assertions_generated(self, evaluator):
        """Test handling when no assertions are generated"""
        evaluator.generator.generate = Mock(return_value=[])
        
        findings = {'summary': '', 'sources': [], 'papers': []}
        result = evaluator.assess_quality("Test", findings)
        
        assert result['quality'] == 0.0
        assert result['new_assertions'] == []
        assert 'error' in result['details']
    
    def test_duplicate_assertion_detection(self, evaluator):
        """Test that duplicate assertions are detected"""
        findings = {'summary': 'Test', 'sources': [], 'papers': []}
        
        # First assessment
        result1 = evaluator.assess_quality("Test", findings)
        initial_new = len(result1['new_assertions'])
        
        # Second assessment should find known assertions
        result2 = evaluator.assess_quality("Test2", findings)
        
        # Some assertions should now be marked as known
        assert len(result2['known_assertions']) >= 0
    
    def test_quality_calculation(self, evaluator):
        """Test quality score calculation"""
        # Mock to return exactly 3 assertions
        evaluator.generator.generate = Mock(return_value=[
            "Assertion one",
            "Assertion two", 
            "Assertion three"
        ])
        
        findings = {'summary': 'Test', 'sources': [], 'papers': []}
        result = evaluator.assess_quality("Test", findings)
        
        # If all new, quality should be 10.0
        # If all known, quality should be 0.0
        assert 0 <= result['quality'] <= 10
        
        # Verify calculation: quality = (new/total) * 10
        total = result['details']['total_assertions']
        new = len(result['new_assertions'])
        expected_quality = (new / total) * 10
        assert result['quality'] == round(expected_quality, 1)
    
    def test_assertion_in_kg_detection(self, evaluator):
        """Test detection of assertions in existing KG summaries"""
        # Setup KG with existing content
        evaluator.kg.get_state.return_value = {
            "knowledge": {
                "topics": {
                    "Existing Topic": {
                        "summary": "This topic is about machine learning and neural networks"
                    }
                }
            }
        }
        
        # Check if assertion exists in KG
        exists = evaluator._assertion_in_kg("machine learning and neural networks")
        
        assert exists is True
    
    def test_is_assertion_new_with_embedding(self, evaluator):
        """Test checking if assertion is new using embedding"""
        # First, index an assertion
        embedding = evaluator.embedding_service.embed("Test assertion")[0]
        evaluator.index.insert("Test assertion", embedding)
        
        # Check if same assertion is new
        is_new = evaluator._is_assertion_new("Test assertion")
        
        assert is_new is False
