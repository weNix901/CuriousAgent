"""DreamDaemon - heartbeat-triggered DreamAgent execution."""
from dataclasses import dataclass
from pathlib import Path

from core.agents.dream_agent import DreamAgent, DreamAgentConfig
from core.frameworks.heartbeat import HeartbeatService
from core.tools.registry import ToolRegistry


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

        self.heartbeat = HeartbeatService(
            workspace=workspace,
            on_heartbeat=self._on_heartbeat,
            interval_s=self.config.interval_seconds,
            enabled=self.config.enabled,
        )

    async def start(self) -> None:
        if not self.config.enabled:
            return
        self._running = True
        await self.heartbeat.start()

    def stop(self) -> None:
        self._running = False
        self.heartbeat.stop()

    async def _on_heartbeat(self, prompt: str) -> str:
        result = self.agent.run(input_data=prompt)
        return result.content