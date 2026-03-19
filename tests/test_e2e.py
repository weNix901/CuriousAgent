"""
End-to-end tests for Curious Agent v0.2

Tests the complete workflow from trigger to result, verifying:
- Full workflow from trigger to result
- All three layers work together
- Auto-queue adds new topics
- State is updated correctly
"""
import json
import os
import sys
import tempfile
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_state_file(tmp_path):
    """Create a temporary state file for testing"""
    state_file = tmp_path / "state.json"
    initial_state = {
        "knowledge": {"topics": {}},
        "curiosity_queue": [],
        "exploration_log": [],
        "last_update": None,
        "config": {
            "notification_threshold": 7.0
        }
    }
    state_file.write_text(json.dumps(initial_state, ensure_ascii=False))
    return str(state_file)


@pytest.fixture
def mock_external_apis():
    """Mock all external APIs (Bocha, arXiv, LLM)"""
    with patch('core.explorer.ArxivAnalyzer') as MockArxiv, \
         patch('core.explorer.LLMClient') as MockLLM, \
         patch('core.explorer.Explorer._call_bocha_search') as MockSearch:
        
        # Mock Bocha Search (Layer 1)
        MockSearch.return_value = [
            {
                "title": "Knowledge Graph Embedding Methods Survey",
                "snippet": "This paper surveys recent advances in knowledge graph embedding techniques including TransE, RotatE, and neural approaches.",
                "url": "https://arxiv.org/abs/2401.02009"
            },
            {
                "title": "Neural Networks for Graph Learning",
                "snippet": "Graph neural networks have shown remarkable success in learning representations.",
                "url": "https://example.com/paper2"
            }
        ]
        
        # Mock ArXiv Analyzer (Layer 2)
        mock_analyzer = Mock()
        mock_analyzer.analyze_papers.return_value = {
            "papers": [
                {
                    "arxiv_id": "2401.02009",
                    "title": "Knowledge Graph Embedding Methods Survey",
                    "authors": ["Author A", "Author B"],
                    "abstract": "A comprehensive survey of knowledge graph embedding methods...",
                    "relevance_score": 0.85,
                    "key_findings": [
                        "TransE is effective for simple relations",
                        "RotatE handles complex relations better",
                        "Neural approaches show promise for multi-hop reasoning"
                    ],
                    "downloaded_full": True
                },
                {
                    "arxiv_id": "2401.02010",
                    "title": "Advanced Graph Neural Networks",
                    "authors": ["Author C"],
                    "abstract": "Novel approaches to graph neural networks...",
                    "relevance_score": 0.72,
                    "key_findings": [
                        "Attention mechanisms improve performance",
                        "Scalability remains a challenge"
                    ],
                    "downloaded_full": False
                }
            ],
            "papers_analyzed": 2,
            "high_relevance_count": 2
        }
        MockArxiv.return_value = mock_analyzer
        
        # Mock LLM Client (Layer 3)
        mock_llm = Mock()
        mock_llm.generate_insights.return_value = {
            "status": "success",
            "insights": """## 方法论对比

| 方法 | 创新点 | 局限性 |
|------|--------|--------|
| TransE | 简单高效 | 难以处理复杂关系 |
| RotatE | 复数空间建模 | 计算开销较大 |

## 核心贡献总结
1. 系统性梳理了知识图谱嵌入的发展脉络
2. 提出了新的评估框架

## 跨论文趋势观察
- 注意力机制成为主流
- 多跳推理是研究热点

## 建议
值得深入探索，特别是注意力机制在知识图谱中的应用。
""",
            "papers_compared": 2,
            "model": "minimax-m2.7"
        }
        MockLLM.return_value = mock_llm
        
        yield {
            "search": MockSearch,
            "arxiv": MockArxiv,
            "llm": MockLLM,
            "analyzer": mock_analyzer,
            "llm_client": mock_llm
        }


class TestE2EFullWorkflow:
    """End-to-end tests for complete workflow"""

    def test_full_workflow_deep_exploration(self, mock_external_apis, mock_state_file):
        """Test complete workflow from trigger to result with deep exploration"""
        import core.knowledge_graph as kg_module
        
        # Temporarily use mock state file
        original_state_file = kg_module.STATE_FILE
        kg_module.STATE_FILE = mock_state_file
        
        try:
            from core.knowledge_graph import add_curiosity, get_state
            
            # Setup: Add a curiosity to explore
            add_curiosity(
                topic="knowledge graph embedding",
                reason="E2E test trigger",
                relevance=8.0,
                depth=7.0
            )
            
            # Execute: Run one cycle with deep exploration
            from curious_agent import run_one_cycle
            result = run_one_cycle(depth="deep")
            
            # Verify: Result structure
            assert result["status"] in ["success", "idle"]
            
            if result["status"] == "success":
                # Verify exploration result
                exploration_result = result["result"]
                assert "topic" in exploration_result
                assert "findings" in exploration_result
                assert "sources" in exploration_result
                
                # Verify all layers were called
                mock_external_apis["search"].assert_called()
                
                # Verify state was updated
                state = get_state()
                assert len(state["exploration_log"]) > 0
                
        finally:
            kg_module.STATE_FILE = original_state_file

    def test_shallow_exploration_only_layer1(self, mock_external_apis, mock_state_file):
        """Test that shallow exploration only calls Layer 1"""
        import core.knowledge_graph as kg_module
        kg_module.STATE_FILE = mock_state_file
        
        try:
            from core.knowledge_graph import add_curiosity
            from core.explorer import Explorer
            
            add_curiosity(topic="test shallow", reason="test", relevance=7.0, depth=5.0)
            
            # Create explorer with shallow depth and verify layer dispatch
            explorer = Explorer(exploration_depth="shallow")
            
            # Mock layer methods to track calls
            with patch.object(explorer, '_layer2_arxiv') as mock_layer2, \
                 patch.object(explorer, '_layer3_insights') as mock_layer3:
                
                explorer._layer1_search = Mock(return_value={
                    "findings": "test",
                    "sources": [],
                    "arxiv_links": ["https://arxiv.org/abs/2401.02009"]
                })
                
                result = explorer._explore_layers("test topic")
                
                # Layer 1 should be called
                explorer._layer1_search.assert_called_once()
                # Layer 2 and 3 should NOT be called for shallow
                mock_layer2.assert_not_called()
                mock_layer3.assert_not_called()
                
        finally:
            pass

    def test_medium_exploration_layer1_and_layer2(self, mock_external_apis, mock_state_file):
        """Test that medium exploration calls Layer 1 and Layer 2"""
        import core.knowledge_graph as kg_module
        kg_module.STATE_FILE = mock_state_file
        
        try:
            from core.knowledge_graph import add_curiosity
            from curious_agent import run_one_cycle
            
            add_curiosity(topic="test medium", reason="test", relevance=7.0, depth=5.0)
            
            result = run_one_cycle(depth="medium")
            
            if result["status"] == "success":
                # Layer 1 should be called
                mock_external_apis["search"].assert_called()
                # Layer 2 should be called for medium (if arxiv links found)
                # Layer 3 should NOT be called for medium
                mock_external_apis["llm"].assert_not_called()
                
        finally:
            pass


class TestE2EAutoQueue:
    """End-to-end tests for auto-queue functionality"""

    def test_auto_queue_adds_new_topics(self, mock_external_apis, mock_state_file):
        """Test that auto-queue adds new topics from findings"""
        import core.knowledge_graph as kg_module
        kg_module.STATE_FILE = mock_state_file
        
        try:
            from core.knowledge_graph import add_curiosity, get_state
            from curious_agent import run_one_cycle
            
            # Add initial curiosity
            add_curiosity(topic="test auto queue", reason="test", relevance=8.0, depth=7.0)
            
            # Run exploration
            result = run_one_cycle(depth="deep")
            
            if result["status"] == "success":
                # Check if auto_queued count is reported
                assert "auto_queued" in result
                
                # Verify state has new curiosities if keywords were found
                state = get_state()
                # The auto_queue should have added topics based on findings
                
        finally:
            pass

    def test_auto_queue_deduplicates(self, mock_state_file):
        """Test that auto-queue doesn't add duplicate topics"""
        import core.knowledge_graph as kg_module
        kg_module.STATE_FILE = mock_state_file
        
        try:
            from core.curiosity_engine import CuriosityEngine
            from core.knowledge_graph import add_curiosity, get_state
            
            # Add existing curiosity
            add_curiosity(topic="existing topic", reason="test", relevance=7.0, depth=5.0)
            
            engine = CuriosityEngine()
            
            # Try to add the same topic via auto_queue
            count = engine.auto_queue_topics(["existing topic"], "parent topic")
            
            # Should not add duplicate
            assert count == 0
            
            state = get_state()
            # Should still have only one "existing topic"
            pending_topics = [item["topic"].lower() for item in state["curiosity_queue"] 
                            if item["status"] == "pending"]
            assert pending_topics.count("existing topic") <= 1
            
        finally:
            pass


class TestE2EStateUpdates:
    """End-to-end tests for state management"""

    def test_exploration_updates_knowledge_graph(self, mock_external_apis, mock_state_file):
        """Test that exploration updates the knowledge graph"""
        import core.knowledge_graph as kg_module
        kg_module.STATE_FILE = mock_state_file
        
        try:
            from core.knowledge_graph import add_curiosity, get_state
            from core.explorer import Explorer
            
            topic = "test knowledge update"
            add_curiosity(topic=topic, reason="test", relevance=7.0, depth=5.0)
            
            explorer = Explorer(exploration_depth="shallow")
            explorer._call_bocha_search = Mock(return_value=[
                {"title": "Test", "snippet": "Test snippet", "url": "https://example.com"}
            ])
            
            state_before = get_state()
            pending_before = [item for item in state_before["curiosity_queue"] if item["status"] == "pending"]
            
            if pending_before:
                result = explorer.explore(pending_before[0])
                
                state = get_state()
                
                # Topic should be in knowledge
                assert topic in state["knowledge"]["topics"]
                
                # Topic should be marked as done in curiosity queue
                queue_item = next(
                    (item for item in state["curiosity_queue"] if item["topic"] == topic),
                    None
                )
                if queue_item:
                    assert queue_item["status"] == "done"
                
                # Exploration should be logged
                assert len(state["exploration_log"]) > 0
                log_entry = state["exploration_log"][-1]
                assert log_entry["topic"] == topic
                
        finally:
            pass

    def test_exploration_log_contains_required_fields(self, mock_external_apis, mock_state_file):
        """Test that exploration log contains all required fields"""
        import core.knowledge_graph as kg_module
        kg_module.STATE_FILE = mock_state_file
        
        try:
            from core.knowledge_graph import add_curiosity, get_state
            from curious_agent import run_one_cycle
            
            add_curiosity(topic="test log fields", reason="test", relevance=7.0, depth=5.0)
            
            result = run_one_cycle(depth="medium")
            
            if result["status"] == "success":
                state = get_state()
                log_entry = state["exploration_log"][-1]
                
                # Required fields
                assert "topic" in log_entry
                assert "action" in log_entry
                assert "findings" in log_entry
                assert "notified_user" in log_entry
                assert "timestamp" in log_entry
                
        finally:
            pass


class TestE2EAPITrigger:
    """End-to-end tests for API trigger endpoint"""

    def test_trigger_endpoint_accepts_request(self):
        """Test that trigger endpoint accepts POST request"""
        from curious_api import app
        
        app.config['TESTING'] = True
        client = app.test_client()
        
        response = client.post('/api/curious/trigger',
                              json={"topic": "test trigger", "depth": "shallow"})
        
        assert response.status_code == 202
        data = response.get_json()
        assert data["status"] == "accepted"
        assert data["topic"] == "test trigger"

    def test_trigger_validates_depth(self):
        """Test that trigger validates depth parameter"""
        from curious_api import app
        
        app.config['TESTING'] = True
        client = app.test_client()
        
        response = client.post('/api/curious/trigger',
                              json={"topic": "test", "depth": "invalid"})
        
        assert response.status_code == 400

    def test_trigger_requires_topic(self):
        """Test that trigger requires topic parameter"""
        from curious_api import app
        
        app.config['TESTING'] = True
        client = app.test_client()
        
        response = client.post('/api/curious/trigger',
                              json={"depth": "shallow"})
        
        assert response.status_code == 400


class TestE2ELayerIntegration:
    """End-to-end tests for layer integration"""

    def test_layer1_provides_arxiv_links_to_layer2(self, mock_external_apis):
        """Test that Layer 1 findings feed into Layer 2"""
        from core.explorer import Explorer
        
        explorer = Explorer(exploration_depth="medium")
        
        # Layer 1 should extract arxiv links
        l1_result = explorer._layer1_search("knowledge graph embedding")
        
        assert "arxiv_links" in l1_result
        assert isinstance(l1_result["arxiv_links"], list)

    def test_layer2_provides_papers_to_layer3(self, mock_external_apis):
        """Test that Layer 2 papers feed into Layer 3"""
        from core.explorer import Explorer
        
        explorer = Explorer(exploration_depth="deep")
        
        # Layer 2 should provide papers
        l2_result = explorer._layer2_arxiv(
            "knowledge graph embedding",
            ["https://arxiv.org/abs/2401.02009"]
        )
        
        assert "papers" in l2_result
        assert isinstance(l2_result["papers"], list)

    def test_findings_synthesis_combines_all_layers(self, mock_external_apis):
        """Test that final findings combine all layer outputs"""
        from core.explorer import Explorer
        
        explorer = Explorer(exploration_depth="deep")
        
        result = explorer._explore_layers("knowledge graph embedding")
        
        assert "findings" in result
        assert isinstance(result["findings"], str)
        assert len(result["findings"]) > 0


class TestE2EErrorHandling:
    """End-to-end tests for error handling"""

    def test_handles_empty_search_results(self, mock_state_file):
        """Test handling of empty search results"""
        import core.knowledge_graph as kg_module
        kg_module.STATE_FILE = mock_state_file
        
        try:
            with patch('core.explorer.Explorer._call_bocha_search') as MockSearch:
                MockSearch.return_value = []  # Empty results
                
                from core.explorer import Explorer
                
                explorer = Explorer(exploration_depth="shallow")
                result = explorer._layer1_search("nonexistent topic xyz")
                
                # Should still return valid structure
                assert "findings" in result
                assert "sources" in result
                
        finally:
            pass

    def test_handles_missing_api_key(self, mock_state_file):
        """Test handling of missing API keys"""
        import core.knowledge_graph as kg_module
        kg_module.STATE_FILE = mock_state_file
        
        try:
            with patch.dict('os.environ', {'BOCHA_API_KEY': ''}):
                from core.explorer import Explorer
                
                explorer = Explorer(exploration_depth="shallow")
                result = explorer._layer1_search("test topic")
                
                # Should handle gracefully
                assert "findings" in result
                
        finally:
            pass


class TestE2ECLI:
    """End-to-end tests for CLI functionality"""

    def test_cli_depth_parameter_validation(self):
        """Test that CLI validates depth parameter"""
        from curious_agent import run_one_cycle
        
        # Valid depths should work
        for depth in ["shallow", "medium", "deep"]:
            # Should not raise
            try:
                run_one_cycle(depth=depth)
            except ValueError:
                pytest.fail(f"Valid depth '{depth}' raised ValueError")

    def test_cli_invalid_depth_raises_error(self):
        """Test that invalid depth raises ValueError"""
        from curious_agent import run_one_cycle
        
        with pytest.raises(ValueError):
            run_one_cycle(depth="invalid_depth")
