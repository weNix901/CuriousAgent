"""DeepReadDaemon - guardian for DeepReadAgent."""
import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Any

import nest_asyncio
from loguru import logger


@dataclass
class DeepReadDaemonConfig:
    """Configuration for DeepReadDaemon."""
    poll_interval_seconds: float = 1800.0
    max_retries: int = 3
    retry_delay_seconds: float = 15.0
    enabled: bool = True


class DeepReadDaemon(threading.Thread):
    """Daemon that runs DeepReadAgent periodically."""
    
    def __init__(
        self,
        deep_read_agent: Any,
        config: DeepReadDaemonConfig | None = None,
    ):
        super().__init__(name="deep_read_daemon", daemon=True)
        self.deep_read_agent = deep_read_agent
        self.config = config or DeepReadDaemonConfig()
        self.running = True
    
    def stop(self):
        """Signal daemon to stop."""
        self.running = False
    
    def run(self):
        """Main daemon loop."""
        nest_asyncio.apply()
        
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            while self.running and self.config.enabled:
                self._loop.run_until_complete(self._tick())
                time.sleep(self.config.poll_interval_seconds)
        finally:
            self._loop.close()
    
    async def _tick(self):
        """Execute one iteration."""
        try:
            result = await self.deep_read_agent.run()
            if result.success:
                logger.info(f"DeepReadDaemon: processed {result.content}")
            else:
                logger.debug(f"DeepReadDaemon: {result.content}")
        except Exception as e:
            logger.error(f"DeepReadDaemon error: {e}")