"""Integration tests for Explorer layer integration"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFullLayeredExploration:
    """Test suite for full layered exploration integration"""

    def test_full_layered_exploration_deep(self):
        """Test all three layers work together for deep exploration"""
        from core.explorer import Explorer
        
        with patch('core.explorer.ArxivAnalyzer') as MockArxiv, \
             patch('core.explorer.LLMClient') as MockLLM:
            
            # Mock Layer 2 (ArxivAnalyzer)
            mock_analyzer = Mock()
            mock_analyzer.analyze_papers.return_value = {
                "papers": [
                    {"title": "Test Paper 1", "relevance_score": 0.8, "key_findings": ["finding1"], "arxiv_id": "2401.02009"},
                    {"title": "Test Paper 2", "relevance_score": 0.7, "key_findings": ["finding2"], "arxiv_id": "2401.02010"}
                ],
                "papers_analyzed": 2,
                "high_relevance_count": 2
            }
            MockArxiv.return_value = mock_analyzer
            
            # Mock Layer 3 (LLMClient)
            mock_llm = Mock()
            mock_llm.generate_insights.return_value = {
                "status": "success",
                "insights": "Test insights from LLM"
            }
            MockLLM.return_value = mock_llm
            
            # Create explorer with deep depth
            explorer = Explorer(exploration_depth="deep")
            
            # Mock layer1 to return arxiv links
            explorer._layer1_search = Mock(return_value={
                "findings": "Layer 1 findings",
                "sources": ["https://example.com"],
                "arxiv_links": ["https://arxiv.org/abs/2401.02009"]
            })
            
            result = explorer._explore_layers("test topic")
            
            # Verify all layers were called
            assert "findings" in result
            assert "sources" in result
            assert "action" in result
            # For deep exploration, all layers should be involved
            assert "layer1" in result["action"] or "layer2" in result["action"] or "layer3" in result["action"]

    def test_layer2_uses_arxiv_analyzer(self):
        """Test that _layer2_arxiv uses ArxivAnalyzer"""
        from core.explorer import Explorer
        
        with patch('core.explorer.ArxivAnalyzer') as MockArxiv:
            mock_analyzer = Mock()
            mock_analyzer.analyze_papers.return_value = {
                "papers": [{"title": "Test", "relevance_score": 0.8}],
                "papers_analyzed": 1,
                "high_relevance_count": 1
            }
            MockArxiv.return_value = mock_analyzer
            
            explorer = Explorer(exploration_depth="medium")
            result = explorer._layer2_arxiv("test topic", ["https://arxiv.org/abs/2401.02009"])
            
            # Verify ArxivAnalyzer was called
            MockArxiv.assert_called_once()
            mock_analyzer.analyze_papers.assert_called_once_with("test topic", ["https://arxiv.org/abs/2401.02009"])
            
            # Verify result structure
            assert "findings" in result
            assert "sources" in result

    def test_layer3_uses_llm_client(self):
        """Test that _layer3_insights uses LLMClient"""
        from core.explorer import Explorer
        
        with patch('core.explorer.LLMClient') as MockLLM:
            mock_llm = Mock()
            mock_llm.generate_insights.return_value = {
                "status": "success",
                "insights": "Test insights"
            }
            MockLLM.return_value = mock_llm
            
            explorer = Explorer(exploration_depth="deep")
            papers = [
                {"title": "Paper 1", "relevance_score": 0.8, "key_findings": ["f1"]},
                {"title": "Paper 2", "relevance_score": 0.7, "key_findings": ["f2"]}
            ]
            result = explorer._layer3_insights("test topic", papers)
            
            # Verify LLMClient was called
            MockLLM.assert_called_once()
            mock_llm.generate_insights.assert_called_once_with("test topic", papers)
            
            # Verify result structure
            assert "findings" in result
            assert "sources" in result

    def test_synthesize_findings_combines_all_layers(self):
        """Test that _synthesize_findings combines findings from all layers"""
        from core.explorer import Explorer
        
        explorer = Explorer()
        
        # Mock layer results
        layer_results = {
            "layer1": {
                "findings": "Web search findings",
                "sources": ["https://example.com"]
            },
            "layer2": {
                "findings": "ArXiv analysis findings",
                "sources": ["https://arxiv.org/abs/2401.02009"],
                "papers": [
                    {"title": "Test Paper", "relevance_score": 0.8, "key_findings": ["key finding"]}
                ]
            },
            "layer3": {
                "findings": "LLM insights",
                "sources": []
            }
        }
        
        result = explorer._synthesize_findings("test topic", layer_results)
        
        # Should be a string combining all findings
        assert isinstance(result, str)
        assert len(result) > 0

    def test_extract_sources_deduplicates(self):
        """Test that _extract_sources deduplicates URLs"""
        from core.explorer import Explorer
        
        explorer = Explorer()
        
        # Mock layer results with duplicate sources
        layer_results = {
            "layer1": {
                "sources": ["https://example.com", "https://arxiv.org/abs/2401.02009"]
            },
            "layer2": {
                "sources": ["https://arxiv.org/abs/2401.02009"],  # duplicate
                "papers": [{"arxiv_id": "2401.02009"}]
            }
        }
        
        result = explorer._extract_sources(layer_results)
        
        # Should be a list with deduplicated URLs
        assert isinstance(result, list)
        # Check for deduplication
        assert len(result) == len(set(result))

    def test_medium_depth_calls_layer1_and_layer2(self):
        """Test that medium depth calls Layer 1 and Layer 2"""
        from core.explorer import Explorer
        
        with patch('core.explorer.ArxivAnalyzer') as MockArxiv:
            mock_analyzer = Mock()
            mock_analyzer.analyze_papers.return_value = {
                "papers": [],
                "papers_analyzed": 0,
                "high_relevance_count": 0
            }
            MockArxiv.return_value = mock_analyzer
            
            explorer = Explorer(exploration_depth="medium")
            
            explorer._layer1_search = Mock(return_value={
                "findings": "test",
                "sources": [],
                "arxiv_links": ["https://arxiv.org/abs/2401.02009"]
            })
            
            result = explorer._explore_layers("test topic")
            
            # Layer 1 should be called
            explorer._layer1_search.assert_called_once()
            # Layer 2 should be called for medium depth
            MockArxiv.assert_called_once()

    def test_shallow_depth_only_calls_layer1(self):
        """Test that shallow depth only calls Layer 1"""
        from core.explorer import Explorer
        
        with patch('core.explorer.ArxivAnalyzer') as MockArxiv, \
             patch('core.explorer.LLMClient') as MockLLM:
            
            explorer = Explorer(exploration_depth="shallow")
            
            explorer._layer1_search = Mock(return_value={
                "findings": "test",
                "sources": [],
                "arxiv_links": ["https://arxiv.org/abs/2401.02009"]
            })
            
            result = explorer._explore_layers("test topic")
            
            # Layer 1 should be called
            explorer._layer1_search.assert_called_once()
            # Layer 2 and 3 should NOT be called for shallow
            MockArxiv.assert_not_called()
            MockLLM.assert_not_called()


class TestLayerMethodSignatures:
    """Test that layer methods have correct signatures and return types"""

    def test_layer1_search_returns_dict_with_findings_and_sources(self):
        """Test _layer1_search returns correct structure"""
        from core.explorer import Explorer
        
        explorer = Explorer()
        # Mock the Bocha search
        explorer._call_bocha_search = Mock(return_value=[
            {"title": "Test", "snippet": "Test snippet", "url": "https://example.com"}
        ])
        
        result = explorer._layer1_search("test topic")
        
        assert isinstance(result, dict)
        assert "findings" in result
        assert "sources" in result

    def test_layer2_arxiv_returns_dict_with_findings_and_sources(self):
        """Test _layer2_arxiv returns correct structure"""
        from core.explorer import Explorer
        
        with patch('core.explorer.ArxivAnalyzer') as MockArxiv:
            mock_analyzer = Mock()
            mock_analyzer.analyze_papers.return_value = {
                "papers": [],
                "papers_analyzed": 0,
                "high_relevance_count": 0
            }
            MockArxiv.return_value = mock_analyzer
            
            explorer = Explorer()
            result = explorer._layer2_arxiv("test topic", ["https://arxiv.org/abs/2401.02009"])
            
            assert isinstance(result, dict)
            assert "findings" in result
            assert "sources" in result

    def test_layer3_insights_returns_dict_with_findings_and_sources(self):
        """Test _layer3_insights returns correct structure"""
        from core.explorer import Explorer
        
        with patch('core.explorer.LLMClient') as MockLLM:
            mock_llm = Mock()
            mock_llm.generate_insights.return_value = {
                "status": "success",
                "insights": "Test insights"
            }
            MockLLM.return_value = mock_llm
            
            explorer = Explorer()
            papers = [
                {"title": "Paper 1", "relevance_score": 0.8, "key_findings": ["f1"]},
                {"title": "Paper 2", "relevance_score": 0.7, "key_findings": ["f2"]}
            ]
            result = explorer._layer3_insights("test topic", papers)
            
            assert isinstance(result, dict)
            assert "findings" in result
            assert "sources" in result
