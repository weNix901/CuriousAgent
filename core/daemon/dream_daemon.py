"""DreamDaemon - periodic DreamAgent execution."""
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from core.agents.dream_agent import DreamAgent, DreamAgentConfig
from core.tools.registry import ToolRegistry
from loguru import logger

DEFAULT_DREAM_INTERVAL_S = 30 * 60  # 30 minutes — was 6h, fixed for continuous operation

# A-5 (v0.3.7): edge-integrity patrol cadence, counted in dream ticks.
# DreamDaemon runs low-frequency (1800s) and does NOT sit on the explore hot
# path, so this is where the periodic KG edge patrol belongs — NOT in
# ExploreDaemon's per-tick loop (which is single-threaded and must stay fast).
EDGE_INTEGRITY_EVERY_N_TICKS = 2


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
        self._tick_count = 0

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

            # A-5 (v0.3.7): periodic KG edge-integrity patrol (low-frequency,
            # off the explore hot path). Only every N ticks to keep it cheap.
            self._tick_count += 1
            if self._tick_count % EDGE_INTEGRITY_EVERY_N_TICKS == 0:
                await self._check_edge_integrity()

        except Exception as e:
            logger.error(f"DreamDaemon tick failed: {e}")

    async def _check_edge_integrity(self) -> None:
        """A-5 (v0.3.7): read-only KG edge-integrity patrol.

        Detects edges that are missing the synthetic ``key`` (invisible to the
        uniqueness constraint → potential silent duplicates). Logs loudly on
        violation; never raises (a patrol must not kill the dream loop).
        """
        try:
            from core.kg.repository_factory import _get_kg_factory
            from core.kg.edge_integrity import check_edge_integrity_async

            factory = _get_kg_factory()
            client = getattr(factory, "_client", None) or getattr(factory, "client", None)
            if client is None:
                logger.warning("Edge-integrity patrol skipped: no KG client available")
                return

            report = await check_edge_integrity_async(client)
            if report["ok"]:
                logger.info(
                    f"Edge-integrity patrol OK: {report['total']} edges, "
                    f"0 missing key, 0 duplicate"
                )
            else:
                logger.error(
                    f"Edge-integrity patrol VIOLATION: {report['missing_key']} edges "
                    f"missing key, {report['duplicate_keys']} duplicate keys "
                    f"(of {report['total']}). KG not clean — run "
                    f"'python3 -m core.kg.edge_integrity' for details."
                )
        except Exception as e:
            logger.warning(f"Edge-integrity patrol failed (non-fatal): {e}")

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