"""Tests for three-agent daemon mode (v0.2.6)."""
import queue
import signal
import threading
import time
from unittest.mock import MagicMock, patch

import pytest


class TestDaemonModeStartsThreeAgents:
    """Test that daemon_mode starts SpiderAgent, DreamAgent, and SleepPruner."""
    
    def test_daemon_mode_starts_all_agents(self):
        """daemon_mode should start SpiderAgent, DreamAgent, and SleepPruner threads."""
        from curious_agent import daemon_mode
        
        started_agents = []
        
        def create_mock_agent_class(agent_name):
            class MockAgent:
                def __init__(self, name=agent_name, **kwargs):
                    self.name = name
                    self.running = True
                    started_agents.append(name)
                
                def start(self):
                    pass
                
                def is_alive(self):
                    return True
                
                def stop(self):
                    self.running = False
                
                def join(self, timeout=None):
                    pass
                
                def get_recently_explored(self, limit=10):
                    return []
                
                def get_status(self):
                    return {}
            return MockAgent
        
        mock_spider = create_mock_agent_class('SpiderAgent')
        mock_dream = create_mock_agent_class('DreamAgent')
        mock_pruner = create_mock_agent_class('SleepPruner')
        
        patches = [
            patch('core.spider_agent.SpiderAgent', mock_spider),
            patch('core.dream_agent.DreamAgent', mock_dream),
            patch('core.sleep_pruner.SleepPruner', mock_pruner),
            patch('curious_agent.kg.init_root_pool'),
        ]
        
        for p in patches:
            p.start()
        
        try:
            with patch('signal.signal'), \
                 patch('curious_agent.time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda x: None
                daemon_mode(interval_minutes=30)
        finally:
            for p in patches:
                p.stop()
        
        assert 'SpiderAgent' in started_agents
        assert 'DreamAgent' in started_agents
        assert 'SleepPruner' in started_agents


class TestDaemonModeGracefulShutdown:
    """Test that daemon_mode handles graceful shutdown on Ctrl+C."""
    
    def test_daemon_mode_stops_agents_on_shutdown(self):
        """daemon_mode should stop all agents when shutdown is requested."""
        from curious_agent import daemon_mode
        
        stopped_agents = []
        
        class MockAgent:
            def __init__(self, name, **kwargs):
                self.name = name
                self.running = True
            
            def start(self):
                pass
            
            def is_alive(self):
                return self.running
            
            def stop(self):
                self.running = False
                stopped_agents.append(self.name)
            
            def join(self, timeout=None):
                pass
            
            def get_recently_explored(self, limit=10):
                return []
            
            def get_status(self):
                return {}
        
        patches = [
            patch('core.spider_agent.SpiderAgent', MockAgent),
            patch('core.dream_agent.DreamAgent', MockAgent),
            patch('core.sleep_pruner.SleepPruner', MockAgent),
            patch('curious_agent.kg.init_root_pool'),
        ]
        
        for p in patches:
            p.start()
        
        try:
            with patch('signal.signal'), \
                 patch('curious_agent.time.sleep') as mock_sleep:
                call_count = [0]
                
                def sleep_with_shutdown(seconds):
                    call_count[0] += 1
                    if call_count[0] >= 3:
                        raise KeyboardInterrupt()
                
                mock_sleep.side_effect = sleep_with_shutdown
                
                with pytest.raises(KeyboardInterrupt):
                    daemon_mode(interval_minutes=30)
        finally:
            for p in patches:
                p.stop()
        
        assert 'SpiderAgent' in stopped_agents
        assert 'DreamAgent' in stopped_agents
        assert 'SleepPruner' in stopped_agents
