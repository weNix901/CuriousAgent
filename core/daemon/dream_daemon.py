"""DreamDaemon - periodic DreamAgent execution."""
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from core.agents.dream_agent import DreamAgent, DreamAgentConfig
from core.tools.registry import ToolRegistry
from loguru import logger

DEFAULT_DREAM_INTERVAL_S = 6 * 60 * 60


@dataclass
class DreamDaemonConfig:
    interval_seconds: int = DEFAULT_DREAM_INTERVAL_S
    enabled: bool = True


class DreamDaemon:
    def __init__(
        self,
        workspace: Path,
        config: DreamDaemonConfig | None = None,
        agent_config: DreamAgentConfig | None = None,
    ):
        self.workspace = workspace
        self.config = config or DreamDaemonConfig()
        self._running = False

        tool_registry = ToolRegistry()
        if agent_config is None:
            agent_config = DreamAgentConfig(name="DreamAgent")
        self.agent = DreamAgent(config=agent_config, tool_registry=tool_registry)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self.config.enabled:
            logger.info("DreamDaemon disabled")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"DreamDaemon started (every {self.config.interval_seconds}s)")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.config.interval_seconds)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DreamDaemon error: {e}")

    async def _tick(self) -> None:
        logger.info("DreamDaemon: running Dream Agent...")
        start_time = time.time()
        
        try:
            result = self.agent.run(input_data="generate curiosity topics from knowledge graph")
            duration_ms = int((time.time() - start_time) * 1000)
            
            if result and hasattr(result, 'l4_topics'):
                topics = result.l4_topics or []
                logger.info(f"DreamDaemon: generated {len(topics)} topics in {duration_ms}ms")
                for t in topics[:3]:
                    logger.debug(f"  - {t}")
            else:
                logger.info(f"DreamDaemon: completed in {duration_ms}ms (no topics)")
                
        except Exception as e:
            logger.error(f"DreamDaemon tick failed: {e}")