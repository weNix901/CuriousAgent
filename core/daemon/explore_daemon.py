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


@dataclass
class ExploreDaemonConfig:
    """Configuration for ExploreDaemon.
    
    Field names match config.json daemon.explore.* for direct config binding.
    """
    poll_interval_seconds: float = 300.0
    max_retries: int = 3
    retry_delay_seconds: float = 15.0


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
        # Allow nested asyncio.run() calls from tools within this event loop
        nest_asyncio.apply()
        
        # Create QueueStorage in this thread to avoid SQLite threading issues
        from core.tools.queue_tools import QueueStorage
        queue_storage = QueueStorage()
        queue_storage.initialize()
        self.queue_storage = queue_storage
        
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            while self.running:
                self._loop.run_until_complete(self._tick())
                time.sleep(self.config.poll_interval_seconds)
        finally:
            self._loop.close()
    
    async def _tick(self):
        """Execute one iteration of the daemon loop."""
        if not self.queue_storage:
            return
        
        pending_items = self.queue_storage.get_pending_items(limit=1, exclude_task_type="deep_read")
        
        if not pending_items:
            logger.debug("ExploreDaemon: queue empty, waiting...")
            return
        
        item = pending_items[0]
        item_id = item["id"]
        topic = item["topic"]
        
        if not self.queue_storage.claim_item(item_id, self.explore_agent.holder_id):
            logger.warning(f"ExploreDaemon: failed to claim item {item_id}")
            return
        
        logger.info(f"ExploreDaemon: claimed item {item_id} - {topic}")
        
        retries = 0
        while retries < self.config.max_retries and self.running:
            try:
                result = await self.explore_agent.run(topic, pre_claimed_item_id=item_id)
                
                if result.success:
                    try:
                        kg_factory = get_kg_factory()
                        node = kg_factory.get_node_sync(topic)
                        if node and node.get('content') and len(str(node.get('content', ''))) > 10:
                            # KG has valid content → delete queue item
                            self.queue_storage.delete_item(item_id, self.explore_agent.holder_id)
                            logger.info(f"ExploreDaemon: item {item_id} {topic} → KG verified, queue deleted")
                        else:
                            # KG empty or content too brief → keep claimed, timeout will release
                            logger.warning(f"ExploreDaemon: KG empty/brief for {topic}, keeping claimed (will timeout)")
                    except Exception as e:
                        # KG verification itself failed (Neo4j down, etc.) → keep claimed, don't delete
                        logger.warning(f"ExploreDaemon: KG verification failed for {topic}: {e}, keeping claimed")
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