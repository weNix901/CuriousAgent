"""ExploreDaemon - continuous exploration daemon."""
import asyncio
import signal
import threading
import time
from dataclasses import dataclass
from typing import Any

import nest_asyncio
from loguru import logger

from core.kg.repository_factory import get_kg_factory

# Global event for immediate poll requests from API
_request_immediate_poll_event: threading.Event | None = None


def _request_immediate_poll():
    """Trigger daemon to poll immediately (from API injection of high-priority items).
    
    Called when inject_priority=true or score >= 8 to avoid waiting for poll_interval.
    """
    global _request_immediate_poll_event
    if _request_immediate_poll_event is not None:
        _request_immediate_poll_event.set()
        logger.debug("[ExploreDaemon] Immediate poll requested via API")


@dataclass
class ExploreDaemonConfig:
    """Configuration for ExploreDaemon.
    
    Field names match config.json daemon.explore.* for direct config binding.
    """
    poll_interval_seconds: float = 300.0
    max_retries: int = 3
    retry_delay_seconds: float = 15.0
    # Max times an item may bounce to the back after empty-KG results before it
    # is purged (dead-lettered). Prevents poison items looping forever.
    max_requeue_before_purge: int = 5
    # 批4c (v0.3.6): C2 gap→queue 自动入队。
    gap_scan_enabled: bool = True
    # 每轮 tick 最多入队的缺口数（限流，防一次灌爆）。
    gap_scan_max_per_cycle: int = 2


class ExploreDaemon(threading.Thread):
    """
    Continuous exploration daemon that runs in a background thread.
    
    Workflow:
    1. Poll queue for pending items
    2. Claim an item
    3. Run ExploreAgent to explore the topic
    4. Verify KG content; delete item if valid, keep claimed if empty
    5. On max retries, delete item and log dead letter
    6. Repeat
    """
    
    def __init__(
        self,
        explore_agent: Any,
        queue_storage: Any = None,
        config: ExploreDaemonConfig | None = None,
    ):
        super().__init__(name="explore_daemon", daemon=True)
        self.explore_agent = explore_agent
        # QueueStorage uses SQLite which is not thread-safe, so create it in the thread
        self._external_queue_storage = queue_storage
        self.config = config or ExploreDaemonConfig()
        self.running = True
        self._loop: asyncio.AbstractEventLoop | None = None
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
    
    def _handle_shutdown_signal(self, signum: int, frame: Any):
        """Handle shutdown signal (SIGINT/SIGTERM)."""
        logger.info(f"ExploreDaemon received signal {signum}, shutting down...")
        self.running = False
    
    def stop(self):
        """Signal daemon to stop gracefully."""
        self.running = False
    
    def run(self):
        """Main daemon loop: claim → explore → verify KG → delete/keep."""
        global _request_immediate_poll_event
        
        # Allow nested asyncio.run() calls from tools within this event loop
        nest_asyncio.apply()
        
        # Create QueueStorage in this thread to avoid SQLite threading issues
        from core.tools.queue_tools import QueueStorage
        queue_storage = QueueStorage()
        queue_storage.initialize()
        self.queue_storage = queue_storage
        
        _request_immediate_poll_event = threading.Event()
        
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            while self.running:
                self._loop.run_until_complete(self._tick())
                # Wait for poll_interval, but can be interrupted by immediate poll request
                _request_immediate_poll_event.wait(timeout=self.config.poll_interval_seconds)
                if _request_immediate_poll_event.is_set():
                    _request_immediate_poll_event.clear()
                    logger.debug("[ExploreDaemon] Immediate poll triggered, skipping sleep")
        finally:
            self._loop.close()
            _request_immediate_poll_event = None
    
    async def _tick(self):
        """Execute one iteration of the daemon loop."""
        if not self.queue_storage:
            return

        pending_items = self.queue_storage.get_pending_items(limit=1, exclude_task_type="deep_read")

        if not pending_items:
            logger.debug("ExploreDaemon: queue empty, waiting...")
            # 批4c: 队列空时，正好是自主缺口入队的时机（C2 自主行为）。
            self._enqueue_gaps()
            await self._scan_orphan_nodes()
            return
        
        item = pending_items[0]
        item_id = item["id"]
        topic = item["topic"]
        
        if not self.queue_storage.claim_item(item_id, self.explore_agent.holder_id):
            logger.warning(f"ExploreDaemon: failed to claim item {item_id}")
            return
        
        logger.info(f"ExploreDaemon: claimed item {item_id} - {topic}")

        # Read the persisted requeue_count BEFORE exploring. This value survives
        # across ticks (requeue_to_back bumps it), so a poison item that keeps
        # "succeeding" with empty-KG results is eventually purged instead of
        # looping forever at the head / re-claiming forever.
        current_item = self.queue_storage.get_item(item_id) or {}
        requeue_count = current_item.get("requeue_count", 0)
        purge_threshold = getattr(self.config, "max_requeue_before_purge", 5)

        retries = 0
        while retries < self.config.max_retries and self.running:
            try:
                result = await self.explore_agent.run(topic, pre_claimed_item_id=item_id)
                
                if result.success:
                    # Feed high-quality discoveries into the behavior-rule pipeline.
                    # NOTE: explore_agent.run() returns an AgentResult dataclass, but
                    # intermediate returns may be dicts. Handle both shapes defensively.
                    # This was the missing link that left curious-agent-behaviors.md
                    # frozen since 2026-04-17.
                    try:
                        def _rget(obj, key, default=None):
                            if isinstance(obj, dict):
                                return obj.get(key, default)
                            return getattr(obj, key, default)

                        quality = _rget(result, "quality")
                        findings = _rget(result, "findings") or {}
                        if quality is not None and quality >= 7.0:
                            from core.agent_behavior_writer import AgentBehaviorWriter
                            bw = AgentBehaviorWriter()
                            bw_result = bw.process(
                                topic, findings, quality, findings.get("sources", [])
                            )
                            if bw_result.get("applied"):
                                logger.info(
                                    f"ExploreDaemon: BehaviorWriter wrote '{topic}' "
                                    f"→ {bw_result.get('section')} (Q={quality})"
                                )
                            else:
                                logger.debug(
                                    f"ExploreDaemon: BehaviorWriter skipped '{topic}': "
                                    f"{bw_result.get('reason')}"
                                )
                    except Exception as e:
                        logger.warning(f"ExploreDaemon: BehaviorWriter failed for '{topic}': {e}")

                    try:
                        kg_factory = get_kg_factory()
                        node = kg_factory.get_node_sync(topic)
                        if node and node.get('content') and len(str(node.get('content', ''))) > 10:
                            # KG has valid content → delete queue item
                            self.queue_storage.delete_item(item_id, self.explore_agent.holder_id)
                            logger.info(f"ExploreDaemon: item {item_id} {topic} → KG verified, queue deleted")
                            return
                        # KG empty/brief after a "successful" explore → poison risk.
                        reason = "explore_success_but_kg_empty"
                    except Exception as e:
                        # KG verification itself failed (Neo4j down, etc.)
                        reason = f"kg_verify_error: {e}"
                        logger.warning(f"ExploreDaemon: KG verification failed for {topic}: {e}")

                    # Reached here only when KG NOT verified (empty/brief or error).
                    # requeue_count is the persisted bounce counter across ticks.
                    if requeue_count + 1 >= purge_threshold:
                        # Bounced too many times → purge permanently (dead letter).
                        self._log_dead_letter(item_id, topic, reason)
                        self.queue_storage.delete_item(item_id, self.explore_agent.holder_id)
                        logger.warning(
                            f"ExploreDaemon: PURGED poison item {item_id} {topic} "
                            f"after {requeue_count + 1} empty-KG bounces ({reason})"
                        )
                        return

                    # Otherwise push to the BACK so it stops starving the head;
                    # requeue_count is incremented in DB and survives next tick.
                    self.queue_storage.requeue_to_back(
                        item_id, self.explore_agent.holder_id, reason=reason
                    )
                    logger.warning(
                        f"ExploreDaemon: KG empty/brief for {topic} "
                        f"(bounce {requeue_count + 1}/{purge_threshold}), requeued to back"
                    )
                    return
                else:
                    retries += 1
                    if retries < self.config.max_retries:
                        await asyncio.sleep(self.config.retry_delay_seconds)
            except Exception as e:
                logger.error(f"ExploreDaemon: exploration error - {e}")
                retries += 1
                if retries < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay_seconds)
        
        if retries >= self.config.max_retries:
            self._log_dead_letter(item_id, topic, "max_retries_exceeded")
            self.queue_storage.delete_item(item_id, self.explore_agent.holder_id)
            logger.warning(f"ExploreDaemon: deleted item {item_id} after max retries - {topic}")
            return

    def _log_dead_letter(self, item_id: int, topic: str, reason: str):
        """Log dead letter for analysis (non-blocking)."""
        logger.warning(f"[DEAD_LETTER] item_id={item_id}, topic={topic}, reason={reason}")

    def _enqueue_gaps(self):
        """批4c (v0.3.6): C2 缺口→队列自动入队闭环。

        链路（CA2.0 §3.2）：C1 unknown/void → 4a 落库 ops.db.gaps
        → 4b gap_calculator 算分 → 高价值缺口 → add_curiosity(去重) → 入队
        → mark_consumed（避免重复入队）。

        限流：每轮最多 gap_scan_max_per_cycle 条（防一次灌爆）。
        任何异常 → 静默返回（绝不打断现有探索主循环）。
        """
        if not getattr(self.config, "gap_scan_enabled", True):
            return
        try:
            from core.api.gap_calculator import compute_from_store

            max_per_cycle = getattr(self.config, "gap_scan_max_per_cycle", 2)
            candidates = compute_from_store(only_unconsumed=True)
            if not candidates:
                return

            from core import knowledge_graph_compat as kg_compat
            qs = kg_compat._get_queue_storage()
            enqueued = 0
            for score in candidates:
                if enqueued >= max_per_cycle:
                    break
                before = {i["topic"] for i in qs.get_pending_items()}
                kg_compat.add_curiosity(
                    topic=score.topic,
                    reason=(f"C2 gap auto-queue: {score.status}, "
                            f"value={score.value:.3f} ({score.reason})"),
                    relevance=score.value * 10.0,
                    depth=6.0,
                )
                after = {i["topic"] for i in qs.get_pending_items()}
                if score.topic in (after - before):
                    # 真入队了 → 标记已消费，避免下轮重复
                    try:
                        from core.api.gap_store import mark_consumed
                        mark_consumed(score.topic)
                    except Exception:
                        pass
                    enqueued += 1
                    logger.info(
                        f"[GapQueue] Enqueued gap '{score.topic}' "
                        f"(value={score.value:.3f}, seen-driven)"
                    )
                else:
                    # 去重跳过（已有同义待探索项）→ 仍标记消费，避免反复尝试
                    try:
                        from core.api.gap_store import mark_consumed
                        mark_consumed(score.topic)
                    except Exception:
                        pass
                    logger.debug(f"[GapQueue] Dedup-skipped gap: {score.topic}")
            if enqueued:
                logger.info(f"[GapQueue] cycle done: {enqueued} gap(s) auto-enqueued")
        except Exception as e:
            logger.debug(f"[GapQueue] gap auto-enqueue skipped: {e}")

    async def _scan_orphan_nodes(self):
        """Scan for high-quality isolated nodes and re-enqueue them."""
        if not getattr(self.config, "orphan_scan_enabled", True):
            return

        from core import knowledge_graph_compat as kg_compat

        try:
            kg_factory = get_kg_factory()
            all_nodes = kg_factory.get_all_nodes_sync(limit=500)

            min_quality = getattr(self.config, "orphan_scan_min_quality", 7.0)
            max_per_cycle = getattr(self.config, "orphan_scan_max_per_cycle", 5)
            enqueued = 0

            for node in all_nodes:
                if enqueued >= max_per_cycle:
                    break

                topic = node.get("topic", "")
                quality = node.get("quality", 0.0)
                status = node.get("status", "pending")
                quality = quality or 0.0  # Defensive: avoid None < float TypeError

                if quality < min_quality or status not in ("done", "complete"):
                    continue

                relations = []
                try:
                    repo = await kg_factory._ensure_connected()
                    relations = await repo.get_relations(topic)
                except Exception:
                    pass

                if len(relations) > 0:
                    continue

                if kg_compat.is_topic_completed(topic):
                    state = kg_compat._load_state()
                    mc = state.get("meta_cognitive", {})
                    completed = mc.get("completed_topics", {})
                    if topic in completed:
                        del completed[topic]
                        kg_compat._save_state(state)
                        logger.info(f"[OrphanScan] Re-activated completed orphan: {topic} (quality={quality:.1f})")

                # Try to add - dedup may skip if node has content
                # (for empty done nodes, dedup now allows re-exploration)
                before_count = len(kg_compat._get_queue_storage().get_pending_items()) if hasattr(kg_compat, '_get_queue_storage') else 0
                kg_compat.add_curiosity(
                    topic=topic,
                    reason=f"OrphanScan: high-quality isolated node (quality={quality:.1f})",
                    relevance=quality,
                    depth=7.0,
                )
                # Only count as enqueued if queue actually grew
                after_count = kg_compat._get_queue_storage().get_pending_items().__len__() if hasattr(kg_compat, '_get_queue_storage') else 0
                # Actually, add_curiosity doesn't return - check by re-querying
                # Use a simpler heuristic: check if pending grew
                try:
                    qs = kg_compat._get_queue_storage()
                    new_pending = [i for i in qs.get_pending_items() if i['topic'] == topic]
                    if new_pending:
                        enqueued += 1
                        logger.info(f"[OrphanScan] Enqueued orphan node: {topic} (quality={quality:.1f})")
                    else:
                        logger.debug(f"[OrphanScan] Skipped (dedup): {topic}")
                except Exception:
                    pass

            if enqueued > 0:
                logger.info(f"[OrphanScan] Total {enqueued} orphan nodes enqueued for re-exploration")

        except Exception as e:
            logger.error(f"[OrphanScan] Error scanning orphan nodes: {e}")