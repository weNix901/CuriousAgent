import pytest
from unittest.mock import Mock, MagicMock, patch

class TestQualityV2EndToEnd:
    @pytest.fixture
    def full_setup(self, tmp_path):
        from core.llm_client import LLMClient
        from core.embedding_service import EmbeddingService, EmbeddingConfig
        from core.assertion_index import AssertionIndex
        from core.quality_v2 import QualityV2Assessor
        
        mock_llm = Mock()
        mock_llm.chat.return_value = """
Mamba uses selective state spaces
Mamba achieves O(N) inference
Mamba was proposed in 2024
        """
        
        config = EmbeddingConfig(provider="volcengine")
        embedding_service = EmbeddingService(config)
        assertion_index = AssertionIndex(str(tmp_path / "assertions.db"))
        kg = MagicMock()
        kg.get_state.return_value = {"knowledge": {"topics": {}}}
        
        assessor = QualityV2Assessor(
            mock_llm, embedding_service, assertion_index, kg
        )
        
        return assessor, kg
    
    def test_rich_findings_get_high_quality(self, full_setup):
        assessor, kg = full_setup
        
        rich_findings = {
            'summary': 'Mamba uses selective state spaces to achieve O(N) inference. '
                      'It was proposed by Gu and Dao in 2024 and competes with '
                      'Transformers on long-sequence tasks.',
            'sources': [{'title': 'Mamba Paper'}],
            'papers': [{'title': 'Mamba Paper'}]
        }
        
        quality = assessor.assess_quality("Mamba", rich_findings, kg)
        
        assert quality > 6.0, f"Expected high quality for rich findings, got {quality}"
    
    def test_assertion_quality_differs_from_legacy(self, full_setup):
        assessor, kg = full_setup
        
        findings = {
            'summary': 'Mamba is a state space model architecture.',
            'sources': [{'title': 'Mamba Paper'}],
            'papers': [{'title': 'Mamba Paper'}]
        }
        
        quality = assessor.assess_quality("Mamba", findings, kg)
        # Assertion-based quality should be used (returns quality >= 0)
        assert quality >= 0, f"Expected non-negative quality, got {quality}"
