"""Tests for BaseAgent foundation class."""
import threading
import time

import pytest

from core.base_agent import BaseAgent


class TestBaseAgentIsDaemonThread:
    """Test that BaseAgent is a daemon thread."""
    
    def test_base_agent_is_daemon_thread(self):
        """BaseAgent should be a daemon thread that exits when main process exits."""
        agent = BaseAgent(name="test_agent")
        
        assert isinstance(agent, threading.Thread)
        assert agent.daemon is True


class TestBaseAgentHasRunningFlag:
    """Test that BaseAgent has a running flag for graceful shutdown."""
    
    def test_base_agent_has_running_flag(self):
        """BaseAgent should have a running flag initialized to True."""
        agent = BaseAgent(name="test_agent")
        
        assert hasattr(agent, 'running')
        assert agent.running is True
    
    def test_base_agent_stop_sets_running_false(self):
        """Calling stop() should set running flag to False."""
        agent = BaseAgent(name="test_agent")
        
        agent.stop()
        
        assert agent.running is False


class TestBaseAgentYieldToOther:
    """Test that yield_to_other releases GIL for cooperative multitasking."""
    
    def test_base_agent_yield_to_other(self):
        """yield_to_other should call time.sleep(0) to release GIL."""
        agent = BaseAgent(name="test_agent")
        
        # This should not raise and should complete quickly
        start = time.time()
        agent.yield_to_other()
        elapsed = time.time() - start
        
        # Should complete almost instantly (sleep(0) releases GIL immediately)
        assert elapsed < 0.1


class TestMultipleAgentsRunConcurrently:
    """Test that multiple agents can run concurrently."""
    
    def test_multiple_agents_run_concurrently(self):
        """Multiple BaseAgent instances should be able to run concurrently."""
        
        class CountingAgent(BaseAgent):
            """Test agent that increments a counter."""
            
            def __init__(self, name: str, counter: list):
                super().__init__(name=name)
                self.counter = counter
            
            def run(self):
                while self.running:
                    self.counter[0] += 1
                    self.yield_to_other()
        
        # Shared counter
        counter = [0]
        
        # Create multiple agents
        agents = [
            CountingAgent(name=f"agent_{i}", counter=counter)
            for i in range(3)
        ]
        
        # Start all agents
        for agent in agents:
            agent.start()
        
        # Let them run for a short time
        time.sleep(0.1)
        
        # Stop all agents
        for agent in agents:
            agent.stop()
        
        # Wait for agents to finish
        for agent in agents:
            agent.join(timeout=1.0)
        
        # Counter should have been incremented by multiple agents
        assert counter[0] > 0
