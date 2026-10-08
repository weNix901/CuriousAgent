"""DreamDaemon - periodic DreamAgent execution."""
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from core.agents.dream_agent import DreamAgent, DreamAgentConfig
from core.tools.registry import ToolRegistry
from loguru import logger

DEFAULT_DREAM_INTERVAL_S = 30 * 60  # 30 minutes — was 6h, fixed for continuous operation


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
        logger.info(f"DreamDaemon starting (every {self.config.interval_seconds}s)")
        # Run the loop directly instead of creating a task, so this method blocks
        await self._run_loop()
        logger.info("DreamDaemon stopped")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        # Run first tick immediately, then wait
        while self._running:
            try:
                await self._tick()
                await asyncio.sleep(self.config.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DreamDaemon _tick error: {e}", exc_info=True)

    async def _tick(self) -> None:
        logger.info("DreamDaemon: _tick START - running Dream Agent...")
        start_time = time.time()
        
        try:
            result = self.agent.run(input_data="generate curiosity topics from knowledge graph")
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Inject l4_topics into queue so ExploreDaemon can consume them.
            # C2b (2026-10-08): 唯一通路 —— 改走 kg.add_curiosity()（跨库去重），
            # 不再直接 QueueStorage.add_item()。
            if result and hasattr(result, 'topics_generated'):
                topics = result.topics_generated or []
                if topics:
                    from core.knowledge_graph_compat import add_curiosity
                    from core.tools.queue_tools import QueueStorage
                    added = 0
                    for t in topics:
                        before = {i["topic"] for i in QueueStorage().get_pending_items()}
                        add_curiosity(
                            topic=t,
                            reason="DreamDaemon: l4 topic",
                            relevance=6.0,
                            depth=6.0,
                            source="dream_daemon",
                            l4=True,
                        )
                        after = {i["topic"] for i in QueueStorage().get_pending_items()}
                        if t in (after - before):
                            added += 1
                    logger.info(f"DreamDaemon: injected {added}/{len(topics)} topics into queue")
                logger.info(f"DreamDaemon: generated {len(topics)} topics in {duration_ms}ms")
            else:
                logger.info(f"DreamDaemon: completed in {duration_ms}ms (no topics)")

            # After dreaming, repair relations for isolated nodes
            self._repair_relations()

        except Exception as e:
            logger.error(f"DreamDaemon tick failed: {e}")

    def _repair_relations(self) -> None:
        """Run relation repair service for isolated nodes."""
        try:
            from core.relation_repair import RelationRepairService
            from core.llm_client import LLMClient

            llm = LLMClient()
            service = RelationRepairService(llm_client=llm)
            stats = service.scan_and_repair()
            if stats.get("relations_created", 0) > 0:
                logger.info(f"[DreamDaemon] Relation repair: {stats}")
        except Exception as e:
            logger.warning(f"[DreamDaemon] Relation repair failed: {e}")