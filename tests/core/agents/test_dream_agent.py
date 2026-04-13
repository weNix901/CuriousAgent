"""Tests for DreamAgent multi-cycle architecture."""
import pytest
from dataclasses import dataclass
from typing import List
from unittest.mock import Mock, MagicMock, patch


class TestDreamAgentConfig:
    """Test DreamAgentConfig dataclass."""

    def test_import_dream_agent_config(self):
        """DreamAgentConfig should be importable from core.agents.dream_agent."""
        from core.agents.dream_agent import DreamAgentConfig
        assert DreamAgentConfig is not None

    def test_dream_agent_config_has_required_fields(self):
        """DreamAgentConfig should have name, system_prompt, tools, scoring_weights."""
        from core.agents.dream_agent import DreamAgentConfig
        
        config = DreamAgentConfig(
            name="dream_agent",
            system_prompt="You are a dream agent",
            tools=["kg_query", "queue_write", "llm_call"],
            scoring_weights={
                "relevance": 0.25,
                "frequency": 0.15,
                "recency": 0.15,
                "quality": 0.20,
                "surprise": 0.15,
                "cross_domain": 0.10
            }
        )
        
        assert config.name == "dream_agent"
        assert config.system_prompt == "You are a dream agent"
        assert config.tools == ["kg_query", "queue_write", "llm_call"]
        assert config.scoring_weights["relevance"] == 0.25

    def test_dream_agent_config_default_scoring_weights(self):
        """DreamAgentConfig should have default 6-dimension scoring weights."""
        from core.agents.dream_agent import DreamAgentConfig
        
        config = DreamAgentConfig(
            name="default_dream",
            system_prompt="Default prompt"
        )
        
        # Default weights should sum to 1.0
        total = sum(config.scoring_weights.values())
        assert total == 1.0
        
        # Should have all 6 dimensions
        expected_dims = ["relevance", "frequency", "recency", "quality", "surprise", "cross_domain"]
        for dim in expected_dims:
            assert dim in config.scoring_weights

    def test_dream_agent_config_threshold_defaults(self):
        """DreamAgentConfig should have threshold defaults for filtering."""
        from core.agents.dream_agent import DreamAgentConfig
        
        config = DreamAgentConfig(
            name="dream",
            system_prompt="test"
        )
        
        assert config.min_score_threshold == 0.8
        assert config.min_recall_count == 3


class TestDreamAgent:
    """Test DreamAgent class."""

    def test_import_dream_agent(self):
        """DreamAgent should be importable from core.agents.dream_agent."""
        from core.agents.dream_agent import DreamAgent
        assert DreamAgent is not None

    def test_dream_agent_inherits_from_ca_agent(self):
        """DreamAgent should inherit from CAAgent."""
        from core.agents.dream_agent import DreamAgent
        from core.agents.ca_agent import CAAgent
        
        assert issubclass(DreamAgent, CAAgent)

    def test_dream_agent_init_requires_config_and_registry(self):
        """DreamAgent __init__ should accept config and tool_registry."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(
            name="dream_agent",
            system_prompt="Dream prompt"
        )
        registry = ToolRegistry()
        
        agent = DreamAgent(config=config, tool_registry=registry)
        
        assert agent is not None
        assert agent.config == config
        assert agent.tool_registry == registry

    def test_dream_agent_has_run_method(self):
        """DreamAgent should have a run method."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        assert hasattr(agent, 'run')

    def test_dream_agent_run_returns_dream_result(self):
        """DreamAgent.run should return a DreamResult."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig, DreamResult
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        result = agent.run()
        
        assert isinstance(result, DreamResult)
        assert hasattr(result, 'candidates_selected')
        assert hasattr(result, 'topics_generated')
        assert hasattr(result, 'success')

    def test_dream_agent_has_l1_light_sleep_method(self):
        """DreamAgent should have _l1_light_sleep method for candidate selection."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        assert hasattr(agent, '_l1_light_sleep')

    def test_dream_agent_has_l2_deep_sleep_method(self):
        """DreamAgent should have _l2_deep_sleep method for 6-dimension scoring."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        assert hasattr(agent, '_l2_deep_sleep')

    def test_dream_agent_has_l3_filtering_method(self):
        """DreamAgent should have _l3_filtering method for threshold gating."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        assert hasattr(agent, '_l3_filtering')

    def test_dream_agent_has_l4_rem_sleep_method(self):
        """DreamAgent should have _l4_rem_sleep method for queue topic generation."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        assert hasattr(agent, '_l4_rem_sleep')

    def test_dream_agent_l1_returns_candidates(self):
        """L1 Light Sleep should return list of candidates from ExplorationLog + KG anomalies."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        candidates = agent._l1_light_sleep()
        
        assert isinstance(candidates, list)

    def test_dream_agent_l2_returns_scored_candidates(self):
        """L2 Deep Sleep should return candidates with 6-dimension scores."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig, ScoredCandidate
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        # Mock candidates from L1
        mock_candidates = ["topic_a", "topic_b"]
        
        scored = agent._l2_deep_sleep(mock_candidates)
        
        assert isinstance(scored, list)
        for item in scored:
            assert isinstance(item, ScoredCandidate)
            assert hasattr(item, 'topic')
            assert hasattr(item, 'total_score')
            assert hasattr(item, 'scores')

    def test_dream_agent_l3_filters_by_threshold(self):
        """L3 Filtering should filter candidates by minScore>=0.8 and minRecallCount>=3."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig, ScoredCandidate
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(
            name="dream",
            system_prompt="test",
            min_score_threshold=0.8,
            min_recall_count=3
        )
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        # Create mock scored candidates
        high_score = ScoredCandidate(
            topic="high_topic",
            total_score=0.9,
            scores={"relevance": 0.9, "frequency": 0.8, "recency": 0.85, 
                    "quality": 0.9, "surprise": 0.7, "cross_domain": 0.8},
            recall_count=5
        )
        low_score = ScoredCandidate(
            topic="low_topic",
            total_score=0.6,
            scores={"relevance": 0.5, "frequency": 0.6, "recency": 0.6,
                    "quality": 0.6, "surprise": 0.5, "cross_domain": 0.5},
            recall_count=2
        )
        
        filtered = agent._l3_filtering([high_score, low_score])
        
        assert len(filtered) == 1
        assert filtered[0].topic == "high_topic"

    def test_dream_agent_l4_generates_queue_topics(self):
        """L4 REM Sleep should generate topics for queue (NO KG write)."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig, ScoredCandidate
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        mock_filtered = [
            ScoredCandidate(
                topic="topic_a",
                total_score=0.85,
                scores={"relevance": 0.85, "frequency": 0.8, "recency": 0.85,
                        "quality": 0.85, "surprise": 0.8, "cross_domain": 0.8},
                recall_count=4
            )
        ]
        
        topics = agent._l4_rem_sleep(mock_filtered)
        
        assert isinstance(topics, list)
        # Should NOT write to KG - only generate topics for queue


class TestScoredCandidate:
    """Test ScoredCandidate dataclass."""

    def test_import_scored_candidate(self):
        """ScoredCandidate should be importable from core.agents.dream_agent."""
        from core.agents.dream_agent import ScoredCandidate
        assert ScoredCandidate is not None

    def test_scored_candidate_has_required_fields(self):
        """ScoredCandidate should have topic, total_score, scores, recall_count."""
        from core.agents.dream_agent import ScoredCandidate
        
        candidate = ScoredCandidate(
            topic="test_topic",
            total_score=0.85,
            scores={
                "relevance": 0.9,
                "frequency": 0.8,
                "recency": 0.85,
                "quality": 0.9,
                "surprise": 0.7,
                "cross_domain": 0.8
            },
            recall_count=5
        )
        
        assert candidate.topic == "test_topic"
        assert candidate.total_score == 0.85
        assert candidate.scores["relevance"] == 0.9
        assert candidate.recall_count == 5

    def test_scored_candidate_scores_has_all_dimensions(self):
        """ScoredCandidate scores should have all 6 dimensions."""
        from core.agents.dream_agent import ScoredCandidate
        
        candidate = ScoredCandidate(
            topic="test",
            total_score=0.8,
            scores={
                "relevance": 0.8,
                "frequency": 0.8,
                "recency": 0.8,
                "quality": 0.8,
                "surprise": 0.8,
                "cross_domain": 0.8
            },
            recall_count=3
        )
        
        expected_dims = ["relevance", "frequency", "recency", "quality", "surprise", "cross_domain"]
        for dim in expected_dims:
            assert dim in candidate.scores


class TestDreamResult:
    """Test DreamResult dataclass."""

    def test_import_dream_result(self):
        """DreamResult should be importable from core.agents.dream_agent."""
        from core.agents.dream_agent import DreamResult
        assert DreamResult is not None

    def test_dream_result_has_required_fields(self):
        """DreamResult should have candidates_selected, topics_generated, success."""
        from core.agents.dream_agent import DreamResult
        
        result = DreamResult(
            content="Dream result",
            success=True,
            iterations_used=1,
            candidates_selected=["topic_a", "topic_b"],
            topics_generated=["new_topic_1", "new_topic_2"]
        )
        
        assert result.candidates_selected == ["topic_a", "topic_b"]
        assert result.topics_generated == ["new_topic_1", "new_topic_2"]
        assert result.success is True

    def test_dream_result_failure_case(self):
        """DreamResult should support failure cases."""
        from core.agents.dream_agent import DreamResult
        
        result = DreamResult(
            content="No topics generated",
            success=False,
            iterations_used=1,
            candidates_selected=[],
            topics_generated=[]
        )
        
        assert result.success is False
        assert result.topics_generated == []


class TestDreamAgentToolSubset:
    """Test DreamAgent uses correct tool subset (KG query + Queue write + LLM, NO KG write)."""

    def test_dream_agent_tools_include_kg_query(self):
        """DreamAgent default tools should include kg_query."""
        from core.agents.dream_agent import DreamAgentConfig
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        
        assert "kg_query" in config.tools

    def test_dream_agent_tools_include_queue_write(self):
        """DreamAgent default tools should include queue_write."""
        from core.agents.dream_agent import DreamAgentConfig
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        
        assert "queue_write" in config.tools

    def test_dream_agent_tools_include_llm_call(self):
        """DreamAgent default tools should include llm_call."""
        from core.agents.dream_agent import DreamAgentConfig
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        
        assert "llm_call" in config.tools

    def test_dream_agent_tools_exclude_kg_write(self):
        """DreamAgent default tools should NOT include kg_write."""
        from core.agents.dream_agent import DreamAgentConfig
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        
        assert "kg_write" not in config.tools

    def test_dream_agent_tool_count_is_15(self):
        """DreamAgent should have exactly 15 tools."""
        from core.agents.dream_agent import DreamAgentConfig
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        
        assert len(config.tools) == 15


class TestDreamAgentLinearPipeline:
    """Test DreamAgent uses linear pipeline (NOT ReAct loop)."""

    def test_dream_agent_run_executes_l1_l2_l3_l4_sequentially(self):
        """DreamAgent.run should execute L1→L2→L3→L4 in sequence."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        # Track execution order
        execution_order = []
        
        def mock_l1():
            execution_order.append("L1")
            return ["topic_a"]
        
        def mock_l2(candidates):
            execution_order.append("L2")
            return []
        
        def mock_l3(scored):
            execution_order.append("L3")
            return []
        
        def mock_l4(filtered):
            execution_order.append("L4")
            return []
        
        agent._l1_light_sleep = mock_l1
        agent._l2_deep_sleep = mock_l2
        agent._l3_filtering = mock_l3
        agent._l4_rem_sleep = mock_l4
        
        agent.run()
        
        assert execution_order == ["L1", "L2", "L3", "L4"]

    def test_dream_agent_does_not_use_react_loop(self):
        """DreamAgent should NOT have ReAct loop iteration logic."""
        from core.agents.dream_agent import DreamAgent, DreamAgentConfig
        from core.tools.registry import ToolRegistry
        
        config = DreamAgentConfig(name="dream", system_prompt="test")
        agent = DreamAgent(config=config, tool_registry=ToolRegistry())
        
        # DreamAgent should not have max_iterations for ReAct loop
        # It uses linear pipeline, not iterative reasoning
        assert not hasattr(agent, '_react_loop')
        assert not hasattr(agent, '_iterate')