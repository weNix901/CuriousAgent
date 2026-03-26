"""
Spider Engine - Main entry point

This module provides the main SpiderEngine class for autonomous exploration.
"""

import asyncio
import importlib.util
from typing import Optional, Protocol
from core.spider.state import SpiderRuntimeState
from core.spider.checkpoint import SpiderCheckpoint
from core.repository.base import KnowledgeRepository
from core.models.topic import Topic


# Dynamically load SpiderConfig to avoid core.config package/file shadow conflict
_spec = importlib.util.spec_from_file_location(
    "spider_config", "core/config/spider_config.py"
)
_spider_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_spider_cfg)
SpiderConfig = _spider_cfg.SpiderConfig


class TopicExplorer(Protocol):
    async def explore(self, topic: str, depth: str = "medium") -> dict:
        ...


class TopicDecomposer(Protocol):
    async def decompose(self, topic: str) -> list[dict]:
        ...


class MetaCognitiveController:
    def __init__(self, monitor=None):
        self.monitor = monitor or MetaCognitiveMonitor()
    
    def should_continue(self, topic: str) -> tuple[bool, str]:
        returns = self.monitor.get_marginal_returns(topic)
        min_return = 0.3
        
        if not returns:
            return True, "First exploration"
        
        last_return = returns[-1]
        if last_return < min_return:
            return False, f"Marginal return {last_return:.2f} below threshold {min_return}"
        
        return True, f"Marginal return healthy ({last_return:.2f})"


class MetaCognitiveMonitor:
    def get_marginal_returns(self, topic: str) -> list[float]:
        return []
    
    def assess_exploration_quality(self, topic: str, findings: dict) -> float:
        return 5.0


class SpiderEngine:
    """
    Spider Engine for autonomous knowledge exploration.
    
    Uses TDD-developed components:
    - Repository (JSONKnowledgeRepository)
    - Runtime State (SpiderRuntimeState)
    - Checkpoint (SpiderCheckpoint)
    - Config (SpiderConfig)
    """
    
    def __init__(
        self,
        repo: KnowledgeRepository,
        config: SpiderConfig = None,
        explorer: TopicExplorer = None,
        decomposer: TopicDecomposer = None,
        checkpoint: SpiderCheckpoint = None,
    ):
        self.repo = repo
        self.config = config or SpiderConfig()
        self.explorer = explorer
        self.decomposer = decomposer
        self.checkpoint = checkpoint
        
        self.controller = MetaCognitiveController()
        self.runtime_state = SpiderRuntimeState()
        
        if checkpoint:
            self._restore_from_checkpoint()
    
    def _restore_from_checkpoint(self) -> None:
        if self.checkpoint and self.checkpoint.exists():
            loaded = self.checkpoint.load()
            if loaded:
                self.runtime_state, _ = loaded
    
    async def run_once(self) -> bool:
        """
        Execute one exploration cycle.
        
        Returns:
            True if exploration was performed, False otherwise
        """
        if not self.runtime_state.current_node:
            self._select_next_node()
        
        if not self.runtime_state.current_node:
            return False
        
        node = self.runtime_state.current_node
        
        if self.explorer:
            result = await self.explorer.explore(node, self.config.default_exploration_depth)
        else:
            result = {"summary": f"Explored {node}", "sources": []}
        
        quality = self.controller.monitor.assess_exploration_quality(node, result)
        should_continue, reason = self.controller.should_continue(node)
        
        topic = self.repo.get_topic(node) or Topic(name=node)
        topic.mark_explored()
        topic.last_quality = quality
        topic.findings_summary = result.get("summary", "")[:500]
        self.repo.save_topic(topic)
        
        if should_continue and self.decomposer:
            await self._expand_frontier(node, result)
            self.runtime_state.consecutive_low_gain = 0
        else:
            topic.mark_fully_explored()
            self.repo.save_topic(topic)
            self.runtime_state.consecutive_low_gain += 1
            
            if self.runtime_state.consecutive_low_gain >= self.config.max_consecutive_low_gain:
                next_node = self.repo.get_high_degree_unexplored()
                self.runtime_state.current_node = next_node
                self.runtime_state.consecutive_low_gain = 0
            else:
                self._select_next_node()
        
        self.runtime_state.visited.add(node)
        self.runtime_state.step_count += 1
        
        if self.checkpoint:
            self.checkpoint.save(self.runtime_state, self.repo.get_storage_path())
        
        return True
    
    def _select_next_node(self) -> None:
        if self.runtime_state.frontier:
            self.runtime_state.current_node = self.runtime_state.frontier.pop(0)
        else:
            self.runtime_state.current_node = self.repo.get_high_degree_unexplored()
    
    async def _expand_frontier(self, node: str, result: dict) -> None:
        if not self.decomposer:
            return
        
        try:
            subtopics = await self.decomposer.decompose(node)
            
            for st in subtopics[:5]:
                child_name = st.get("topic", "")
                if not child_name:
                    continue
                
                self.repo.add_relation(node, child_name, "decomposed_from")
                
                child = self.repo.get_topic(child_name)
                if not child or not child.explored:
                    self.runtime_state.frontier.append(child_name)
        except Exception:
            pass
    
    def run(self, max_steps: Optional[int] = None) -> None:
        """Run spider loop (blocking)."""
        asyncio.run(self._run_async(max_steps))
    
    async def _run_async(self, max_steps: Optional[int] = None) -> None:
        """Async run loop."""
        step = 0
        while True:
            if max_steps and step >= max_steps:
                break
            
            if not await self.run_once():
                break
            
            step += 1
            await asyncio.sleep(self.config.loop_interval)
