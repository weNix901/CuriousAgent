"""ExploreDaemon - continuous exploration daemon."""
import asyncio
import signal
import threading
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class ExploreDaemonConfig:
    """Configuration for ExploreDaemon."""
    poll_interval: float = 5.0
    max_retries: int = 3
    retry_delay: float = 1.0


class ExploreDaemon(threading.Thread):
    """
    Continuous exploration daemon that runs in a background thread.
    
    Workflow:
    1. Poll queue for pending items
    2. Claim an item
    3. Run ExploreAgent to explore the topic
    4. Mark item as done (or failed after retries)
    5. Repeat
    """
    
    def __init__(
        self,
        explore_agent: Any,
        queue_storage: Any = None,
        config: ExploreDaemonConfig | None = None,
    ):
        super().__init__(name="explore_daemon", daemon=True)
        self.explore_agent = explore_agent
        self.queue_storage = queue_storage
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
        """Main daemon loop: claim → explore → mark done."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            while self.running:
                self._loop.run_until_complete(self._tick())
                time.sleep(self.config.poll_interval)
        finally:
            self._loop.close()
    
    async def _tick(self):
        """Execute one iteration of the daemon loop."""
        if not self.queue_storage:
            return
        
        pending_items = self.queue_storage.get_pending_items(limit=1)
        
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
                result = await self.explore_agent.run(topic)
                
                if result.success:
                    self.queue_storage.mark_done(item_id, self.explore_agent.holder_id)
                    logger.info(f"ExploreDaemon: completed item {item_id}")
                    return
                else:
                    retries += 1
                    if retries < self.config.max_retries:
                        await asyncio.sleep(self.config.retry_delay)
            except Exception as e:
                logger.error(f"ExploreDaemon: exploration error - {e}")
                retries += 1
                if retries < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay)
        
        if retries >= self.config.max_retries:
            self.queue_storage.mark_failed(
                item_id,
                self.explore_agent.holder_id,
                requeue=False,
                reason="Max retries exceeded"
            )
            logger.warning(f"ExploreDaemon: marked item {item_id} as failed after {retries} retries")