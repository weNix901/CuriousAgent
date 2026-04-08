"""Integration tests for QualityV2Assessor with KnowledgeAssertionEvaluator"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from core.quality_v2 import QualityV2Assessor


class TestDualChannelQualityAssessment:
    """Test dual-channel quality assessment integration"""
    
    def test_init_with_optional_dependencies(self):
        """QualityV2Assessor should accept optional embedding dependencies"""
        mock_llm = Mock()
        mock_embedding = Mock()
        mock_index = Mock()
        mock_kg = Mock()
        
        assessor = QualityV2Assessor(
            mock_llm,
            embedding_service=mock_embedding,
            assertion_index=mock_index,
            knowledge_graph=mock_kg
        )
        
        assert assessor.llm == mock_llm
        assert assessor.embedding_service == mock_embedding
        assert assessor.assertion_index == mock_index
        assert assessor.kg == mock_kg
        assert assessor.assertion_evaluator is not None
    
    def test_init_without_optional_dependencies(self):
        """QualityV2Assessor should work without embedding dependencies (backward compat)"""
        mock_llm = Mock()
        
        assessor = QualityV2Assessor(mock_llm)
        
        assert assessor.llm == mock_llm
        assert assessor.embedding_service is None
        assert assessor.assertion_index is None
        assert assessor.assertion_evaluator is None
    
    def test_assess_quality_runs_both_channels(self):
        """assess_quality should run both assertion and legacy evaluation"""
        mock_llm = Mock()
        mock_llm.chat = Mock(return_value="0.5")
        
        mock_embedding = Mock()
        mock_embedding.embed = Mock(return_value=[[0.1] * 768])
        
        mock_index = Mock()
        mock_index.search_similar = Mock(return_value=[])
        mock_index.insert = Mock(return_value=1)
        
        mock_kg = Mock()
        mock_kg.get_state = Mock(return_value={
            "knowledge": {"topics": {}}
        })
        
        assessor = QualityV2Assessor(
            mock_llm,
            embedding_service=mock_embedding,
            assertion_index=mock_index,
            knowledge_graph=mock_kg
        )
        
        findings = {"summary": "Test summary about AI agents"}
        
        # Mock the assertion evaluator's assess_quality
        with patch.object(assessor.assertion_evaluator, 'assess_quality') as mock_assert:
            mock_assert.return_value = {
                'quality': 7.5,
                'new_assertions': ['test assertion'],
                'known_assertions': [],
                'details': {}
            }
            
            result = assessor.assess_quality("test_topic", findings, mock_kg)
            
            # Should have called assertion evaluator
            mock_assert.assert_called_once_with("test_topic", findings)
            
            # Should return a float quality score
            assert isinstance(result, float)
            assert 0 <= result <= 10
    
    def test_aggregate_quality_both_low(self):
        """When both channels agree on low quality, return low"""
        mock_llm = Mock()
        assessor = QualityV2Assessor(mock_llm)
        
        assertion_result = {'quality': 2.0, 'new_assertions': [], 'known_assertions': [], 'details': {}}
        legacy_quality = 1.5
        
        result = assessor._aggregate_quality(assertion_result, legacy_quality)
        
        assert result < 3.0
        assert result == min(2.0, 1.5)
    
    def test_aggregate_quality_assertion_zero_legacy_high(self):
        """When assertion is 0.0 but legacy is high, trust legacy"""
        mock_llm = Mock()
        assessor = QualityV2Assessor(mock_llm)
        
        assertion_result = {'quality': 0.0, 'new_assertions': [], 'known_assertions': [], 'details': {}}
        legacy_quality = 7.5
        
        result = assessor._aggregate_quality(assertion_result, legacy_quality)
        
        assert result == 7.5
    
    def test_aggregate_quality_assertion_high_legacy_low(self):
        """When assertion is high but legacy is very low, blend"""
        mock_llm = Mock()
        assessor = QualityV2Assessor(mock_llm)
        
        assertion_result = {'quality': 8.0, 'new_assertions': [], 'known_assertions': [], 'details': {}}
        legacy_quality = 2.0
        
        result = assessor._aggregate_quality(assertion_result, legacy_quality)
        
        # Should be blended: 8.0 * 0.7 + 2.0 * 0.3 = 6.2
        assert result == 6.2
    
    def test_aggregate_quality_assertion_only(self):
        """When only assertion available, use it"""
        mock_llm = Mock()
        assessor = QualityV2Assessor(mock_llm)
        
        assertion_result = {'quality': 6.5, 'new_assertions': [], 'known_assertions': [], 'details': {}}
        
        result = assessor._aggregate_quality(assertion_result, None)
        
        assert result == 6.5
    
    def test_aggregate_quality_legacy_only(self):
        """When only legacy available, use it"""
        mock_llm = Mock()
        assessor = QualityV2Assessor(mock_llm)
        
        legacy_quality = 5.5
        
        result = assessor._aggregate_quality(None, legacy_quality)
        
        assert result == 5.5
    
    def test_aggregate_quality_both_none(self):
        """When both channels fail, return neutral"""
        mock_llm = Mock()
        assessor = QualityV2Assessor(mock_llm)
        
        result = assessor._aggregate_quality(None, None)
        
        assert result == 5.0
    
    def test_calculate_legacy_quality(self):
        """Legacy quality calculation should work independently"""
        mock_llm = Mock()
        mock_llm.chat = Mock(return_value="0.5")
        assessor = QualityV2Assessor(mock_llm)
        
        mock_kg = Mock()
        mock_kg.get_state = Mock(return_value={
            "knowledge": {"topics": {}}
        })
        
        findings = {"summary": "Test summary about AI agents"}
        
        result = assessor._calculate_legacy_quality("test_topic", findings, mock_kg)
        
        assert isinstance(result, float)
        assert 0 <= result <= 10
    
    def test_assess_quality_fallback_on_assertion_error(self):
        """assess_quality should fallback to legacy when assertion fails"""
        mock_llm = Mock()
        mock_llm.chat = Mock(return_value="0.5")
        
        mock_embedding = Mock()
        mock_index = Mock()
        mock_kg = Mock()
        mock_kg.get_state = Mock(return_value={
            "knowledge": {"topics": {}}
        })
        
        assessor = QualityV2Assessor(
            mock_llm,
            embedding_service=mock_embedding,
            assertion_index=mock_index,
            knowledge_graph=mock_kg
        )
        
        findings = {"summary": "Test summary"}
        
        # Make assertion evaluator raise an error
        with patch.object(assessor.assertion_evaluator, 'assess_quality') as mock_assert:
            mock_assert.side_effect = Exception("Assertion failed")
            
            result = assessor.assess_quality("test_topic", findings, mock_kg)
            
            # Should still return a valid quality score from legacy
            assert isinstance(result, float)
            assert 0 <= result <= 10
    
    def test_backward_compatibility_old_api(self):
        """Old code using just llm_client should still work"""
        mock_llm = Mock()
        mock_llm.chat = Mock(return_value="0.5")
        
        # Old-style instantiation
        assessor = QualityV2Assessor(mock_llm)
        
        mock_kg = Mock()
        mock_kg.get_state = Mock(return_value={
            "knowledge": {"topics": {}}
        })
        
        findings = {"summary": "Test summary"}
        
        # Should work without errors
        result = assessor.assess_quality("test_topic", findings, mock_kg)
        
        assert isinstance(result, float)
        assert 0 <= result <= 10
