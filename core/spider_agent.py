"""SpiderAgent - Continuous exploration agent running in dedicated thread."""
import queue
import time
from typing import Optional

from core.base_agent import BaseAgent
from core.explorer import Explorer
from core import knowledge_graph as kg
from core.node_lock_registry import NodeLockRegistry
from core.quality_v2 import QualityV2Assessor
from core.llm_client import LLMClient


class SpiderAgent(BaseAgent):
    """
    Continuous exploration agent that runs in a dedicated thread.

    Responsibilities:
    1. Consume topics from DreamInbox
    2. Explore topics via Explorer
    3. Write results to KG with proper locking
    4. Strengthen co-occurring connections (Hebbian learning)
    5. Notify DreamAgent via queue when exploration completes

    Thread Safety:
    - All KG writes use NodeLockRegistry for node-level locking
    - Uses queue.Queue for thread-safe DreamAgent notification
    """

    HEBBIAN_DELTA = 0.1
    HEBBIAN_CO_OCCURRENCE_THRESHOLD = 0.5

    def __init__(
        self,
        name: str = "SpiderAgent",
        notification_queue: Optional[queue.Queue] = None,
        exploration_depth: str = "medium",
        poll_interval: float = 1.0
    ):
        """
        Initialize SpiderAgent.

        Args:
            name: Thread name for debugging
            notification_queue: Queue to notify DreamAgent of completed explorations
            exploration_depth: Depth for Explorer ("shallow", "medium", "deep")
            poll_interval: Seconds to wait between inbox polls
        """
        super().__init__(name=name)
        self.notification_queue = notification_queue
        self.explorer = Explorer(exploration_depth=exploration_depth)
        self.poll_interval = poll_interval
        self._explored_topics: list[str] = []
        self._last_explored_timestamp = time.time()
        self._consecutive_empty_inbox = 0

    def run(self):
        """
        Main loop: consume inbox, explore, write to KG, notify DreamAgent.

        Loop continues until running flag is set to False via stop().
        """
        while self.running:
            try:
                self._process_inbox_cycle()
            except Exception as e:
                print(f"[SpiderAgent] Error in exploration cycle: {e}")

            self.yield_to_other()
            time.sleep(self.poll_interval)

    def _process_inbox_cycle(self):
        """Process one cycle: consume inbox, explore, write, notify."""
        inbox_items = kg.fetch_and_clear_dream_inbox()

        if not inbox_items:
            # === v0.2.8: 批量 claim 填满并发槽位 ===
            MAX_CLAIM_PER_CYCLE = 20  # 每次最多 claim 20 个，平衡速率和调度粒度
            claimed = 0
            while claimed < MAX_CLAIM_PER_CYCLE:
                pending_item = kg.claim_pending_item()
                if not pending_item:
                    break
                topic = pending_item["topic"]
                inbox_items.append({
                    "topic": topic,
                    "source_insight": "curiosity_queue_fallback"
                })
                claimed += 1
            if inbox_items:
                print(f"[SpiderAgent] DreamInbox empty, batch-claimed {len(inbox_items)} items from curiosity_queue")
                self._consecutive_empty_inbox = 0
            else:
                self._consecutive_empty_inbox += 1
                if self._consecutive_empty_inbox >= 5:
                    print(f"[SpiderAgent] Warning: DreamInbox and curiosity_queue both empty for {self._consecutive_empty_inbox} consecutive cycles")
                    self._consecutive_empty_inbox = 0
                return
            # === v0.2.8 批量 claim 结束 ===

        self._consecutive_empty_inbox = 0
        cycle_topics = []

        for item in inbox_items:
            topic = item.get("topic")
            source_insight = item.get("source_insight", "")

            if not topic:
                continue

            if kg.is_topic_completed(topic):
                continue

            result = self._explore_topic(topic, source_insight)

            if result:
                cycle_topics.append(topic)
                self._explored_topics.append(topic)

                if len(self._explored_topics) > 100:
                    self._explored_topics = self._explored_topics[-100:]

                self._decompose_and_enqueue(topic)

        if len(cycle_topics) >= 2:
            self._apply_hebbian_learning(cycle_topics)

    def _explore_topic(self, topic: str, source_insight: str) -> Optional[dict]:
        """
        Explore a single topic with proper KG locking.

        Args:
            topic: Topic to explore
            source_insight: Source insight that triggered this exploration

        Returns:
            Exploration result dict or None if exploration failed
        """
        curiosity_item = {
            "topic": topic,
            "score": 7.0,
            "depth": 5.0,
            "reason": f"Dream-triggered exploration from: {source_insight}"
        }

        try:
            with NodeLockRegistry.global_write_lock():
                lock = NodeLockRegistry.get_lock(topic)
                with lock:
                    result = self.explorer.explore(curiosity_item)
                    if result:
                        self._last_explored_timestamp = time.time()
                        # === G6-Fix: SpiderAgent 同步路径调用 QualityV2 ===
                        try:
                            llm = LLMClient()
                            quality_assessor = QualityV2Assessor(llm)
                            findings = {
                                "summary": result.get("findings", ""),
                                "sources": result.get("sources", [])
                            }
                            quality = quality_assessor.assess_quality(topic, findings, kg)
                            result["quality"] = quality
                            # 更新 KG 中的 quality
                            kg.update_topic_quality(topic, quality)
                        except Exception as e:
                            print(f"[SpiderAgent] Quality assessment failed for '{topic}': {e}")
                        # === G6-Fix 结束 ===
                    self._notify_dream_agent(topic, result)
                    return result
        except Exception as e:
            print(f"[SpiderAgent] Exploration failed for '{topic}': {e}")
            return None

    def _notify_dream_agent(self, topic: str, result: dict):
        """
        Notify DreamAgent of completed exploration via queue.

        Args:
            topic: Topic that was explored
            result: Exploration result
        """
        if self.notification_queue is None:
            return

        notification = {
            "type": "exploration_complete",
            "topic": topic,
            "findings": result.get("findings", ""),
            "sources": result.get("sources", []),
            "score": result.get("score", 0),
            "notified": result.get("notified", False)
        }

        try:
            self.notification_queue.put(notification, block=False)
        except queue.Full:
            print(f"[SpiderAgent] Notification queue full, dropping notification for '{topic}'")

    def _apply_hebbian_learning(self, cycle_topics: list[str]):
        """
        Apply Hebbian learning: strengthen connections between co-occurring topics.

        "Neurons that fire together, wire together" - topics explored in the same
        cycle get their connections strengthened.

        Args:
            cycle_topics: List of topics explored in this cycle
        """
        for i, topic_a in enumerate(cycle_topics):
            for topic_b in cycle_topics[i + 1:]:
                connected = kg.get_directly_connected(topic_a)

                should_strengthen = topic_b in connected or self._share_common_ancestor(
                    topic_a, topic_b, max_distance=2
                )

                if should_strengthen:
                    kg.strengthen_connection(
                        topic_a, topic_b, delta=self.HEBBIAN_DELTA
                    )

    def _share_common_ancestor(self, topic_a: str, topic_b: str, max_distance: int = 2) -> bool:
        """
        Check if two topics share a common ancestor within max_distance hops.

        Args:
            topic_a: First topic
            topic_b: Second topic
            max_distance: Maximum distance to check

        Returns:
            True if topics share a common ancestor within max_distance
        """
        ancestors_a = self._get_ancestors(topic_a, max_depth=max_distance)
        ancestors_b = self._get_ancestors(topic_b, max_depth=max_distance)

        return bool(ancestors_a & ancestors_b)

    def _get_ancestors(self, topic: str, max_depth: int = 2) -> set[str]:
        """
        Get ancestors of a topic up to max_depth.

        Args:
            topic: Topic to get ancestors for
            max_depth: Maximum depth to traverse

        Returns:
            Set of ancestor topic names
        """
        ancestors = set()

        with NodeLockRegistry.global_write_lock():
            state = kg._load_state()
            topics = state.get("knowledge", {}).get("topics", {})

            current_level = [topic]
            visited = {topic}

            for _ in range(max_depth):
                next_level = []
                for current in current_level:
                    if current not in topics:
                        continue
                    node = topics[current]
                    for parent in node.get("parents", []):
                        if parent not in visited:
                            ancestors.add(parent)
                            visited.add(parent)
                            next_level.append(parent)
                current_level = next_level
                if not current_level:
                    break

        return ancestors

    def get_recently_explored(self, limit: int = 10) -> list[str]:
        """
        Get recently explored topics.

        Args:
            limit: Maximum number of topics to return

        Returns:
            List of recently explored topic names
        """
        return self._explored_topics[-limit:]

    def _decompose_and_enqueue(self, topic: str):
        """
        探索完成后触发 decomposition，把 subtopics 加入队列。
        使用统一的 decompose_and_write() 方法。
        """
        try:
            from core.curiosity_decomposer import CuriosityDecomposer
            from core.llm_manager import LLMManager
            from core.provider_registry import init_default_providers
            from core import knowledge_graph as kg
            from core.config import get_config

            # Guard: skip decomposition if topic has no_content status in curiosity_queue
            state = kg.get_state()
            topics = state.get('knowledge', {}).get('topics', {})
            queue = state.get('curiosity_queue', [])
            queue_item = next((item for item in queue if item['topic'] == topic), {})
            if queue_item.get('status') == 'no_content':
                print(f"[SpiderAgent] Skipping decompose for no_content topic: {topic}")
                return

            config = get_config()
            llm_config = {"providers": {}, "selection_strategy": "capability"}
            for p in config.llm_providers:
                llm_config["providers"][p.name] = {
                    "api_url": p.api_url,
                    "timeout": p.timeout,
                    "enabled": p.enabled,
                    "models": [
                        {"model": m.model, "weight": m.weight, "capabilities": m.capabilities, "max_tokens": m.max_tokens}
                        for m in p.models
                    ]
                }

            llm_manager = LLMManager.get_instance(llm_config)
            registry = init_default_providers()
            state = kg.get_state()

            decomposer = CuriosityDecomposer(
                llm_client=llm_manager,
                provider_registry=registry,
                kg=state
            )

            subtopics = decomposer.decompose_and_write(topic)
            print(f"[SpiderAgent] Decomposed '{topic}' into {len(subtopics)} subtopics")
            for st in subtopics:
                print(f"  + {st['sub_topic']} ({st.get('signal_strength', 'unknown')})")
        except Exception as e:
            print(f"[SpiderAgent] Decompose failed for '{topic}': {e}")

    def is_healthy(self, max_idle_seconds: float = 300) -> bool:
        idle_time = time.time() - self._last_explored_timestamp
        return idle_time < max_idle_seconds
    
    def get_idle_time(self) -> float:
        return time.time() - self._last_explored_timestamp
    
    def get_explored_count(self) -> int:
        return len(self._explored_topics)
