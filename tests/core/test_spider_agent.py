"""Tests for SpiderAgent - continuous exploration agent."""
import queue
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from core.spider_agent import SpiderAgent
from core.base_agent import BaseAgent


class TestSpiderAgentInitialization:
    """Test SpiderAgent initialization."""
    
    def test_spider_agent_is_base_agent(self):
        """SpiderAgent should inherit from BaseAgent."""
        agent = SpiderAgent()
        
        assert isinstance(agent, BaseAgent)
        assert isinstance(agent, threading.Thread)
    
    def test_spider_agent_is_daemon(self):
        """SpiderAgent should be a daemon thread."""
        agent = SpiderAgent()
        
        assert agent.daemon is True
    
    def test_spider_agent_has_running_flag(self):
        """SpiderAgent should have a running flag initialized to True."""
        agent = SpiderAgent()
        
        assert agent.running is True
    
    def test_spider_agent_default_name(self):
        """SpiderAgent should have default name 'SpiderAgent'."""
        agent = SpiderAgent()
        
        assert agent.name == "SpiderAgent"
    
    def test_spider_agent_custom_name(self):
        """SpiderAgent should accept custom name."""
        agent = SpiderAgent(name="CustomSpider")
        
        assert agent.name == "CustomSpider"
    
    def test_spider_agent_has_notification_queue(self):
        """SpiderAgent should accept notification queue."""
        notification_queue = queue.Queue()
        agent = SpiderAgent(notification_queue=notification_queue)
        
        assert agent.notification_queue is notification_queue
    
    def test_spider_agent_has_explorer(self):
        """SpiderAgent should have an Explorer instance."""
        agent = SpiderAgent()
        
        assert hasattr(agent, 'explorer')
    
    def test_spider_agent_has_poll_interval(self):
        """SpiderAgent should have configurable poll interval."""
        agent = SpiderAgent(poll_interval=0.5)
        
        assert agent.poll_interval == 0.5
    
    def test_spider_agent_has_hebbian_constants(self):
        """SpiderAgent should have Hebbian learning constants."""
        agent = SpiderAgent()
        
        assert hasattr(agent, 'HEBBIAN_DELTA')
        assert hasattr(agent, 'HEBBIAN_CO_OCCURRENCE_THRESHOLD')
        assert agent.HEBBIAN_DELTA == 0.1


class TestSpiderAgentStop:
    """Test SpiderAgent stop functionality."""
    
    def test_spider_agent_stop_sets_running_false(self):
        """Calling stop() should set running flag to False."""
        agent = SpiderAgent()
        
        agent.stop()
        
        assert agent.running is False


class TestSpiderAgentNotification:
    """Test SpiderAgent notification to DreamAgent."""
    
    def test_notify_dream_agent_puts_to_queue(self):
        """_notify_dream_agent should put notification in queue."""
        notification_queue = queue.Queue()
        agent = SpiderAgent(notification_queue=notification_queue)
        
        result = {"findings": "test findings", "sources": [], "score": 7.0}
        agent._notify_dream_agent("test_topic", result)
        
        notification = notification_queue.get(timeout=1.0)
        
        assert notification["type"] == "exploration_complete"
        assert notification["topic"] == "test_topic"
        assert notification["findings"] == "test findings"
    
    def test_notify_dream_agent_handles_none_queue(self):
        """_notify_dream_agent should handle None queue gracefully."""
        agent = SpiderAgent(notification_queue=None)
        
        result = {"findings": "test", "sources": [], "score": 7.0}
        agent._notify_dream_agent("test_topic", result)
    
    def test_notify_dream_agent_handles_full_queue(self):
        """_notify_dream_agent should handle full queue gracefully."""
        notification_queue = queue.Queue(maxsize=1)
        notification_queue.put({"existing": "item"})
        
        agent = SpiderAgent(notification_queue=notification_queue)
        
        result = {"findings": "test", "sources": [], "score": 7.0}
        agent._notify_dream_agent("test_topic", result)


class TestSpiderAgentInboxConsumption:
    """Test SpiderAgent inbox consumption."""
    
    @patch('core.spider_agent.kg.fetch_and_clear_dream_inbox')
    def test_process_inbox_cycle_consumes_inbox(self, mock_fetch):
        """_process_inbox_cycle should consume DreamInbox."""
        mock_fetch.return_value = []
        
        agent = SpiderAgent()
        agent._process_inbox_cycle()
        
        mock_fetch.assert_called_once()
    
    @patch('core.spider_agent.kg.fetch_and_clear_dream_inbox')
    @patch('core.spider_agent.kg.is_topic_completed')
    def test_process_inbox_cycle_skips_completed_topics(self, mock_completed, mock_fetch):
        """_process_inbox_cycle should skip completed topics."""
        mock_fetch.return_value = [
            {"topic": "completed_topic", "source_insight": "test"}
        ]
        mock_completed.return_value = True
        
        agent = SpiderAgent()
        agent._process_inbox_cycle()
        
        assert len(agent._explored_topics) == 0
    
    @patch('core.spider_agent.kg.fetch_and_clear_dream_inbox')
    def test_process_inbox_cycle_handles_empty_inbox(self, mock_fetch):
        """_process_inbox_cycle should handle empty inbox."""
        mock_fetch.return_value = []
        
        agent = SpiderAgent()
        agent._process_inbox_cycle()
        
        assert len(agent._explored_topics) == 0


class TestSpiderAgentHebbianLearning:
    """Test SpiderAgent Hebbian learning."""
    
    @patch('core.spider_agent.kg.strengthen_connection')
    @patch('core.spider_agent.kg.get_directly_connected')
    def test_apply_hebbian_learning_strengthens_connected(self, mock_connected, mock_strengthen):
        """_apply_hebbian_learning should strengthen connected topics."""
        mock_connected.return_value = {"topic_b"}
        
        agent = SpiderAgent()
        agent._apply_hebbian_learning(["topic_a", "topic_b"])
        
        mock_strengthen.assert_called_once()
    
    @patch('core.spider_agent.kg.strengthen_connection')
    @patch('core.spider_agent.kg.get_directly_connected')
    def test_apply_hebbian_learning_uses_delta(self, mock_connected, mock_strengthen):
        """_apply_hebbian_learning should use HEBBIAN_DELTA."""
        mock_connected.return_value = {"topic_b"}
        
        agent = SpiderAgent()
        agent._apply_hebbian_learning(["topic_a", "topic_b"])
        
        call_args = mock_strengthen.call_args
        assert call_args.kwargs.get("delta") == agent.HEBBIAN_DELTA


class TestSpiderAgentRecentlyExplored:
    """Test SpiderAgent recently explored tracking."""
    
    def test_get_recently_explored_returns_list(self):
        """get_recently_explored should return a list."""
        agent = SpiderAgent()
        
        result = agent.get_recently_explored()
        
        assert isinstance(result, list)
    
    def test_get_recently_explored_respects_limit(self):
        """get_recently_explored should respect limit parameter."""
        agent = SpiderAgent()
        agent._explored_topics = ["topic1", "topic2", "topic3"]
        
        result = agent.get_recently_explored(limit=2)
        
        assert len(result) == 2
        assert result == ["topic2", "topic3"]


class TestSpiderAgentAncestorMethods:
    """Test SpiderAgent ancestor methods."""
    
    def test_share_common_ancestor_returns_bool(self):
        """_share_common_ancestor should return a boolean."""
        agent = SpiderAgent()
        
        result = agent._share_common_ancestor("topic_a", "topic_b")
        
        assert isinstance(result, bool)
    
    def test_get_ancestors_returns_set(self):
        """_get_ancestors should return a set."""
        agent = SpiderAgent()
        
        result = agent._get_ancestors("nonexistent_topic")
        
        assert isinstance(result, set)


class TestSpiderAgentThreadSafety:
    """Test SpiderAgent thread safety."""
    
    def test_multiple_agents_can_run_concurrently(self):
        """Multiple SpiderAgent instances should be able to run concurrently."""
        agents = [SpiderAgent(name=f"agent_{i}", poll_interval=0.01) for i in range(3)]
        
        for agent in agents:
            agent.start()
        
        time.sleep(0.1)
        
        for agent in agents:
            agent.stop()
        
        for agent in agents:
            agent.join(timeout=3.0)

        for agent in agents:
            assert not agent.is_alive()
