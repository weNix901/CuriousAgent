"""Tests for DreamAgent - creative dreaming agent with high/low priority queue handling."""
import queue
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from core.dream_agent import DreamAgent
from core.base_agent import BaseAgent


class TestDreamAgentInitialization:
    """Test DreamAgent initialization."""
    
    def test_dream_agent_is_base_agent(self):
        """DreamAgent should inherit from BaseAgent."""
        agent = DreamAgent()
        
        assert isinstance(agent, BaseAgent)
        assert isinstance(agent, threading.Thread)
    
    def test_dream_agent_is_daemon(self):
        """DreamAgent should be a daemon thread."""
        agent = DreamAgent()
        
        assert agent.daemon is True
    
    def test_dream_agent_has_running_flag(self):
        """DreamAgent should have a running flag initialized to True."""
        agent = DreamAgent()
        
        assert agent.running is True
    
    def test_dream_agent_default_name(self):
        """DreamAgent should have default name 'DreamAgent'."""
        agent = DreamAgent()
        
        assert agent.name == "DreamAgent"
    
    def test_dream_agent_custom_name(self):
        """DreamAgent should accept custom name."""
        agent = DreamAgent(name="CustomDream")
        
        assert agent.name == "CustomDream"
    
    def test_dream_agent_has_high_priority_queue(self):
        """DreamAgent should accept high priority queue."""
        hp_queue = queue.Queue()
        agent = DreamAgent(high_priority_queue=hp_queue)
        
        assert agent.high_priority_queue is hp_queue
    
    def test_dream_agent_has_poll_interval(self):
        """DreamAgent should have configurable poll interval."""
        agent = DreamAgent(poll_interval=0.5)
        
        assert agent.poll_interval == 0.5
    
    def test_dream_agent_has_llm_client(self):
        """DreamAgent should have an LLM client."""
        agent = DreamAgent()
        
        assert hasattr(agent, 'llm')
    
    def test_dream_agent_has_f7_constants(self):
        """DreamAgent should have F7 optimization constants."""
        agent = DreamAgent()
        
        assert agent.HIGH_PRIORITY_TIMEOUT_SECONDS == 5
        assert agent.HIGH_PRIORITY_BATCH_SIZE == 5
    
    def test_dream_agent_has_f8_constants(self):
        """DreamAgent should have F8 three-layer randomization constants."""
        agent = DreamAgent()
        
        assert agent.DISTANCE_WEIGHT == 0.70
        assert agent.CROSS_DOMAIN_WEIGHT == 0.20
        assert agent.NEURAL_NOISE_WEIGHT == 0.10
    
    def test_dream_agent_has_quality_threshold(self):
        """DreamAgent should have quality threshold of 0.5."""
        agent = DreamAgent()
        
        assert agent.QUALITY_THRESHOLD == 0.5


class TestDreamAgentStop:
    """Test DreamAgent stop functionality."""
    
    def test_dream_agent_stop_sets_running_false(self):
        """Calling stop() should set running flag to False."""
        agent = DreamAgent()
        
        agent.stop()
        
        assert agent.running is False


class TestDreamAgentHighPriorityQueue:
    """Test DreamAgent high-priority queue handling (F7)."""
    
    def test_process_high_priority_batch_returns_false_when_no_queue(self):
        """_process_high_priority_batch should return False when no queue."""
        agent = DreamAgent(high_priority_queue=None)
        
        result = agent._process_high_priority_batch()
        
        assert result is False
    
    def test_process_high_priority_batch_returns_false_when_empty(self):
        """_process_high_priority_batch should return False when queue empty."""
        hp_queue = queue.Queue()
        agent = DreamAgent(high_priority_queue=hp_queue)
        
        result = agent._process_high_priority_batch()
        
        assert result is False
    
    def test_process_high_priority_batch_processes_items(self):
        """_process_high_priority_batch should process items from queue."""
        hp_queue = queue.Queue()
        agent = DreamAgent(high_priority_queue=hp_queue)
        
        hp_queue.put({"type": "exploration_complete", "topic": "test_topic", "findings": "test"})
        
        with patch.object(agent, '_process_high_priority_item'):
            with patch.object(agent, '_generate_insight_with_distant_pair'):
                result = agent._process_high_priority_batch()
        
        assert result is True
        assert agent._high_priority_processed == 1
    
    def test_process_high_priority_batch_respects_batch_size(self):
        """_process_high_priority_batch should respect batch size limit."""
        hp_queue = queue.Queue()
        agent = DreamAgent(high_priority_queue=hp_queue)
        
        for i in range(10):
            hp_queue.put({"type": "exploration_complete", "topic": f"topic_{i}", "findings": "test"})
        
        with patch.object(agent, '_process_high_priority_item'):
            with patch.object(agent, '_generate_insight_with_distant_pair'):
                agent._process_high_priority_batch()
        
        assert agent._high_priority_processed == 5
    
    def test_process_high_priority_item_marks_dreamed(self):
        """_process_high_priority_item should mark topic as dreamed."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.mark_dreamed') as mock_mark:
            with patch.object(agent, '_generate_insight_with_distant_pair'):
                agent._process_high_priority_item({
                    "type": "exploration_complete",
                    "topic": "test_topic",
                    "findings": "test findings"
                })
            
            mock_mark.assert_called_once_with("test_topic")


class TestDreamAgentLowPriorityQueue:
    """Test DreamAgent low-priority round-robin polling."""
    
    def test_process_low_priority_cycle_uses_round_robin(self):
        """_process_low_priority_cycle should use round-robin pointer."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_all_nodes') as mock_nodes:
            mock_nodes.return_value = [
                ("topic_a", {"status": "complete"}),
                ("topic_b", {"status": "complete"}),
                ("topic_c", {"status": "complete"})
            ]
            with patch('core.dream_agent.kg.get_recently_dreamed', return_value=set()):
                with patch.object(agent, '_generate_insight_with_distant_pair'):
                    agent._process_low_priority_cycle()
        
        assert agent._low_priority_pointer == 1
    
    def test_process_low_priority_cycle_wraps_pointer(self):
        """_process_low_priority_cycle should wrap pointer when reaching end."""
        agent = DreamAgent()
        agent._low_priority_pointer = 2
        
        with patch('core.dream_agent.kg.get_all_nodes') as mock_nodes:
            mock_nodes.return_value = [
                ("topic_a", {"status": "complete"}),
                ("topic_b", {"status": "complete"}),
                ("topic_c", {"status": "complete"})
            ]
            with patch('core.dream_agent.kg.get_recently_dreamed', return_value=set()):
                with patch.object(agent, '_generate_insight_with_distant_pair'):
                    agent._process_low_priority_cycle()
                    assert agent._low_priority_pointer == 3
        
        with patch('core.dream_agent.kg.get_all_nodes') as mock_nodes:
            mock_nodes.return_value = [
                ("topic_a", {"status": "complete"}),
                ("topic_b", {"status": "complete"}),
                ("topic_c", {"status": "complete"})
            ]
            with patch('core.dream_agent.kg.get_recently_dreamed', return_value=set()):
                with patch.object(agent, '_generate_insight_with_distant_pair'):
                    agent._process_low_priority_cycle()
        
        assert agent._low_priority_pointer == 1
    
    def test_process_low_priority_skips_recently_dreamed(self):
        """_process_low_priority_cycle should skip recently dreamed topics."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_all_nodes') as mock_nodes:
            mock_nodes.return_value = [
                ("topic_a", {"status": "complete"}),
                ("topic_b", {"status": "complete"})
            ]
            with patch('core.dream_agent.kg.get_recently_dreamed', return_value={"topic_a"}):
                with patch.object(agent, '_generate_insight_with_distant_pair') as mock_gen:
                    agent._process_low_priority_cycle()
                    
                    assert mock_gen.call_count == 1
                    assert mock_gen.call_args[0][0] == "topic_b"


class TestDreamAgentThreeLayerRandomization:
    """Test DreamAgent three-layer randomization (F8)."""
    
    def test_select_distant_pair_returns_none_when_no_candidates(self):
        """_select_distant_pair should return None when no candidates."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_all_nodes', return_value=[("only_topic", {})]):
            result = agent._select_distant_pair("only_topic")
        
        assert result is None
    
    def test_select_distant_pair_uses_distance_weight(self):
        """_select_distant_pair should use distance-based selection 70% of time."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_all_nodes', return_value=[
            ("topic_a", {}), ("topic_b", {}), ("topic_c", {})
        ]):
            with patch('random.random', return_value=0.5):
                with patch.object(agent, '_select_by_distance', return_value="distant_topic") as mock:
                    agent._select_distant_pair("topic_a")
                    
                    mock.assert_called_once()
    
    def test_select_distant_pair_uses_cross_domain_weight(self):
        """_select_distant_pair should use cross-domain selection 20% of time."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_all_nodes', return_value=[
            ("topic_a", {}), ("topic_b", {}), ("topic_c", {})
        ]):
            with patch('random.random', return_value=0.75):
                with patch.object(agent, '_select_cross_domain', return_value="cross_topic") as mock:
                    agent._select_distant_pair("topic_a")
                    
                    mock.assert_called_once()
    
    def test_select_distant_pair_uses_neural_noise(self):
        """_select_distant_pair should use pure random 10% of time."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_all_nodes', return_value=[
            ("topic_a", {}), ("topic_b", {}), ("topic_c", {})
        ]):
            with patch('random.random', return_value=0.95):
                with patch('random.choice', return_value="random_topic") as mock:
                    agent._select_distant_pair("topic_a")
                    
                    mock.assert_called_once()
    
    def test_select_by_distance_returns_max_distance(self):
        """_select_by_distance should return topic with maximum distance."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_shortest_path_length') as mock_dist:
            mock_dist.side_effect = lambda a, b: 5 if b == "far_topic" else 1
            
            result = agent._select_by_distance("topic_a", ["near_topic", "far_topic"])
            
            assert result == "far_topic"
    
    def test_select_cross_domain_returns_different_parent(self):
        """_select_cross_domain should return topic with different parents."""
        agent = DreamAgent()
        
        with patch.object(agent, '_get_topic_parents') as mock_parents:
            mock_parents.side_effect = lambda t: {"parent_x"} if t == "topic_a" else {"parent_y"}
            
            result = agent._select_cross_domain("topic_a", ["topic_b", "topic_c"])
            
            assert result in ["topic_b", "topic_c"]


class TestDreamAgentInsightGeneration:
    """Test DreamAgent insight generation."""
    
    def test_generate_creative_insight_returns_dict(self):
        """_generate_creative_insight should return insight dict."""
        mock_llm = MagicMock()
        mock_llm.chat.return_value = '{"content": "test insight", "quality": 0.8}'
        
        agent = DreamAgent(llm_client=mock_llm)
        
        result = agent._generate_creative_insight(
            "topic_a", "findings a",
            "topic_b", {"summary": "findings b"}
        )
        
        assert result is not None
        assert "content" in result
    
    def test_generate_creative_insight_handles_llm_failure(self):
        """_generate_creative_insight should handle LLM failure gracefully."""
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = Exception("LLM error")
        
        agent = DreamAgent(llm_client=mock_llm)
        
        result = agent._generate_creative_insight(
            "topic_a", "findings a",
            "topic_b", {"summary": "findings b"}
        )
        
        assert result is None
    
    def test_parse_insight_response_extracts_json(self):
        """_parse_insight_response should extract JSON from response."""
        agent = DreamAgent()
        
        response = 'Some text before {"content": "insight", "quality": 0.7} some text after'
        result = agent._parse_insight_response(response)
        
        assert result is not None
        assert result["content"] == "insight"
    
    def test_parse_insight_response_returns_none_for_invalid(self):
        """_parse_insight_response should return None for invalid JSON."""
        agent = DreamAgent()
        
        result = agent._parse_insight_response("not json at all")
        
        assert result is None
    
    def test_parse_insight_response_sets_defaults(self):
        """_parse_insight_response should set defaults for missing fields."""
        agent = DreamAgent()
        
        response = '{"content": "insight"}'
        result = agent._parse_insight_response(response)
        
        assert result["type"] == "creative"
        assert result["surprise"] == 0.5
        assert result["novelty"] == 0.5
        assert result["quality"] == 0.5


class TestDreamAgentInsightVerification:
    """Test DreamAgent insight verification and quality decay."""
    
    def test_verify_insight_returns_false_for_nonexistent(self):
        """verify_insight should return False for nonexistent insight."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_dream_insights', return_value=[]):
            result = agent.verify_insight("nonexistent_id")
        
        assert result is False
    
    def test_verify_insight_updates_weight_on_success(self):
        """verify_insight should update weight when topic was explored."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_dream_insights', return_value=[
            {"node_id": "test_id", "source_topics": ["topic_a"]}
        ]):
            with patch('core.dream_agent.kg.has_recent_dreams', return_value=True):
                with patch('core.dream_agent.kg.update_insight_weight') as mock_weight:
                    with patch('core.dream_agent.kg.update_insight_quality'):
                        result = agent.verify_insight("test_id")
                        
                        mock_weight.assert_called_once()
        
        assert result is True
    
    def test_apply_quality_decay_skips_verified(self):
        """apply_quality_decay should skip verified insights."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_dream_insights', return_value=[
            {"node_id": "verified_id", "verified": True}
        ]):
            with patch('core.dream_agent.kg.is_insight_stale', return_value=True):
                with patch('core.dream_agent.kg.update_insight_quality') as mock_quality:
                    agent.apply_quality_decay()
                    
                    mock_quality.assert_not_called()
    
    def test_apply_quality_decay_applies_to_stale(self):
        """apply_quality_decay should apply decay to stale unverified insights."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.get_dream_insights', return_value=[
            {"node_id": "stale_id", "verified": False}
        ]):
            with patch('core.dream_agent.kg.is_insight_stale', return_value=True):
                with patch('core.dream_agent.kg.update_insight_quality') as mock_quality:
                    agent.apply_quality_decay()
                    
                    mock_quality.assert_called_once()


class TestDreamAgentSharedInbox:
    """Test DreamAgent SharedInbox integration."""
    
    def test_notify_spider_agent_adds_to_inbox(self):
        """_notify_spider_agent should add topics to dream inbox."""
        agent = DreamAgent()
        
        with patch('core.dream_agent.kg.add_to_dream_inbox') as mock_add:
            agent._notify_spider_agent("topic_a", "topic_b", {"content": "test insight"})
            
            assert mock_add.call_count == 2


class TestDreamAgentStatus:
    """Test DreamAgent status reporting."""
    
    def test_get_status_returns_dict(self):
        """get_status should return a dictionary."""
        agent = DreamAgent()
        
        status = agent.get_status()
        
        assert isinstance(status, dict)
    
    def test_get_status_contains_running(self):
        """get_status should contain running flag."""
        agent = DreamAgent()
        
        status = agent.get_status()
        
        assert "running" in status
        assert status["running"] is True
    
    def test_get_status_contains_f7_constants(self):
        """get_status should contain F7 optimization constants."""
        agent = DreamAgent()
        
        status = agent.get_status()
        
        assert "high_priority_timeout_seconds" in status
        assert status["high_priority_timeout_seconds"] == 5
        assert "high_priority_batch_size" in status
        assert status["high_priority_batch_size"] == 5
    
    def test_get_status_contains_f8_weights(self):
        """get_status should contain F8 randomization weights."""
        agent = DreamAgent()
        
        status = agent.get_status()
        
        assert "randomization_weights" in status
        weights = status["randomization_weights"]
        assert weights["distance"] == 0.70
        assert weights["cross_domain"] == 0.20
        assert weights["neural_noise"] == 0.10
    
    def test_get_status_contains_statistics(self):
        """get_status should contain processing statistics."""
        agent = DreamAgent()
        
        status = agent.get_status()
        
        assert "insights_generated" in status
        assert "insights_verified" in status
        assert "high_priority_processed" in status
        assert "low_priority_processed" in status


class TestDreamAgentThreadSafety:
    """Test DreamAgent thread safety."""
    
    def test_multiple_agents_can_run_concurrently(self):
        """Multiple DreamAgent instances should be able to run concurrently."""
        agents = [DreamAgent(name=f"agent_{i}") for i in range(3)]
        
        for agent in agents:
            agent.start()
        
        time.sleep(0.1)
        
        for agent in agents:
            agent.stop()
        
        for agent in agents:
            agent.join(timeout=1.0)
        
        for agent in agents:
            assert not agent.is_alive()
    
    def test_low_priority_pointer_is_thread_safe(self):
        """Low priority pointer should be thread-safe."""
        agent = DreamAgent()
        
        def increment_pointer():
            for _ in range(100):
                with agent._low_priority_pointer_lock:
                    agent._low_priority_pointer += 1
        
        threads = [threading.Thread(target=increment_pointer) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert agent._low_priority_pointer == 300
    
    def test_recently_processed_is_thread_safe(self):
        """Recently processed list should be thread-safe."""
        agent = DreamAgent()
        
        def add_to_processed():
            for i in range(50):
                with agent._recently_processed_lock:
                    agent._recently_processed.append(f"topic_{i}")
        
        threads = [threading.Thread(target=add_to_processed) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(agent._recently_processed) == 100
