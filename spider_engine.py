"""
Spider Engine - Main entry point

This module provides the main SpiderEngine class for autonomous exploration.
"""

import asyncio
import importlib.util
import inspect
import logging
from typing import Optional, Protocol
from core.spider.state import SpiderRuntimeState
from core.spider.checkpoint import SpiderCheckpoint
from core.repository.base import KnowledgeRepository
from core.models.topic import Topic
from core.meta_cognitive_controller import MetaCognitiveController
from core.meta_cognitive_monitor import MetaCognitiveMonitor


_spec = importlib.util.spec_from_file_location(
    "spider_config", "core/config/spider_config.py"
)
_spider_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_spider_cfg)
SpiderConfig = _spider_cfg.SpiderConfig

logger = logging.getLogger(__name__)


class TopicExplorer(Protocol):
    async def explore(self, topic: str, depth: str = "medium") -> dict:
        ...


class TopicDecomposer(Protocol):
    async def decompose(self, topic: str) -> list[dict]:
        ...


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
        llm_client=None,
        monitor: MetaCognitiveMonitor = None,
        controller: MetaCognitiveController = None,
        seed_topics: list = None,
    ):
        if repo is None:
            raise RuntimeError("repo is required")
        
        self.repo = repo
        self.config = config or SpiderConfig()
        self.explorer = explorer
        self.decomposer = decomposer
        self.checkpoint = checkpoint
        self.llm_client = llm_client
        
        if controller:
            self.controller = controller
        else:
            monitor_instance = monitor or MetaCognitiveMonitor(llm_client=llm_client)
            self.controller = MetaCognitiveController(monitor=monitor_instance)
        
        self.runtime_state = SpiderRuntimeState()
        self.logger = logging.getLogger(f"{__name__}.{id(self)}")
        
        if seed_topics:
            self.runtime_state.frontier.extend(seed_topics)
            self.logger.info(f"Initialized with {len(seed_topics)} seed topics")
        
        if checkpoint:
            self._restore_from_checkpoint()
    
    def __repr__(self):
        return (f"SpiderEngine(current_node={self.runtime_state.current_node}, "
                f"frontier={len(self.runtime_state.frontier)}, "
                f"visited={len(self.runtime_state.visited)}, "
                f"step={self.runtime_state.step_count})")
    
    def _restore_from_checkpoint(self) -> None:
        if self.checkpoint and self.checkpoint.exists():
            loaded = self.checkpoint.load()
            if loaded:
                self.runtime_state, kg_path = loaded
                if kg_path and kg_path != self.repo.get_storage_path():
                    self.logger.warning(
                        f"Checkpoint kg_path ({kg_path}) differs from "
                        f"current repo path ({self.repo.get_storage_path()})"
                    )
    
    async def run_once(self) -> bool:
        """
        Execute one exploration cycle.
        
        Returns:
            True if exploration was performed, False otherwise
        """
        if self.repo is None:
            raise RuntimeError("repo is required")
        
        if not self.runtime_state.current_node:
            self._select_next_node()
        
        if not self.runtime_state.current_node:
            self.logger.warning("No unexplored nodes available, stopping")
            return False
        
        node = self.runtime_state.current_node
        
        if self.explorer:
            curiosity_item = {
                "topic": node,
                "score": 7.0,
                "depth": self._depth_to_numeric(self.config.default_exploration_depth),
                "reason": "SpiderEngine exploration",
                "status": "pending"
            }
            result = await self._explore_with_adapter(curiosity_item)
        else:
            result = {"summary": f"Explored {node}", "sources": []}
        
        quality = self.controller.monitor.assess_exploration_quality(node, result)
        should_continue, reason = self.controller.should_continue(node)
        
        topic = self.repo.get_topic(node) or Topic(name=node)
        topic.mark_explored()
        topic.last_quality = quality
        topic.findings_summary = result.get("summary", result.get("findings", ""))[:500]
        self.repo.save_topic(topic)
        
        if should_continue:
            if self.decomposer:
                await self._expand_frontier(node, result)
            self.runtime_state.consecutive_low_gain = 0
        else:
            topic.mark_fully_explored()
            self.repo.save_topic(topic)
            self.runtime_state.consecutive_low_gain += 1
            
            if self.runtime_state.consecutive_low_gain >= self.config.max_consecutive_low_gain:
                next_node = self.repo.get_high_degree_unexplored()
                if next_node is None:
                    self.logger.warning("No more unexplored nodes available")
                    return False
                self.runtime_state.current_node = next_node
                self.runtime_state.consecutive_low_gain = 0
            else:
                self._select_next_node()
        
        self.runtime_state.visited.add(node)
        self.runtime_state.step_count += 1
        
        if self.checkpoint:
            self.checkpoint.save(self.runtime_state, self.repo.get_storage_path())
        
        return True
    
    def _depth_to_numeric(self, depth: str) -> float:
        """Convert depth string to numeric value."""
        depth_map = {"shallow": 3.0, "medium": 6.0, "deep": 9.0}
        return depth_map.get(depth, 6.0)
    
    async def _explore_with_adapter(self, curiosity_item: dict) -> dict:
        """
        Adapter to bridge between Protocol and actual Explorer implementation.
        The Protocol expects (topic, depth) but Explorer expects (curiosity_item dict).
        This adapter handles both cases.
        """
        try:
            # Try the new Protocol interface first
            import inspect
            sig = inspect.signature(self.explorer.explore)
            params = list(sig.parameters.keys())
            
            if len(params) >= 2 and params[1] != 'curiosity_item':
                # New style: explore(self, topic, depth)
                return await self.explorer.explore(
                    curiosity_item["topic"], 
                    self.config.default_exploration_depth
                )
            else:
                # Old style: explore(self, curiosity_item)
                return await self.explorer.explore(curiosity_item)
        except TypeError as e:
            # Fallback to dict style if signature inspection fails
            if "takes" in str(e) and "positional arguments" in str(e):
                return await self.explorer.explore(curiosity_item)
            raise
    
    def _select_next_node(self) -> None:
        if self.runtime_state.frontier:
            self.runtime_state.current_node = self.runtime_state.frontier.pop(0)
        else:
            self.runtime_state.current_node = self.repo.get_high_degree_unexplored()
            if not self.runtime_state.current_node:
                self.logger.warning("No unexplored nodes available in repository")
    
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
        except Exception as e:
            self.logger.warning(f"[_expand_frontier] Decompose failed for {node}: {e}")
    
    def run(self, max_steps: Optional[int] = None, max_runtime_seconds: Optional[float] = None) -> None:
        """Run spider loop (blocking)."""
        asyncio.run(self._run_async(max_steps, max_runtime_seconds))
    
    async def _run_async(self, max_steps: Optional[int] = None, max_runtime_seconds: Optional[float] = None) -> None:
        """Async run loop with exception handling and timeout protection."""
        step = 0
        start_time = asyncio.get_event_loop().time()
        
        while True:
            if max_steps and step >= max_steps:
                self.logger.info(f"Reached max_steps ({max_steps}), stopping")
                break
            
            if max_runtime_seconds:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= max_runtime_seconds:
                    self.logger.info(f"Reached max_runtime_seconds ({max_runtime_seconds}), stopping")
                    break
            
            try:
                if not await self.run_once():
                    self.logger.info("run_once returned False, stopping")
                    break
            except Exception as e:
                self.logger.error(f"[_run_async] run_once failed: {e}")
                await asyncio.sleep(self.config.loop_interval)
                continue
            
            step += 1
            await asyncio.sleep(self.config.loop_interval)
