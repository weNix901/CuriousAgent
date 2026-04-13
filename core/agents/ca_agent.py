"""CAAgent unified class for Curious Agent."""
from dataclasses import dataclass, field
from typing import Any, List

from core.tools.registry import ToolRegistry


@dataclass
class AgentResult:
    """Result from CAAgent execution."""
    content: str
    success: bool
    iterations_used: int


@dataclass
class CAAgentConfig:
    """Configuration for CAAgent."""
    name: str = "ca_agent"
    system_prompt: str = "CAAgent unified agent."
    tools: List[str] = field(default_factory=list)
    max_iterations: int = 20
    model: str = "doubao-pro"


class CAAgent:
    """Unified agent class for Curious Agent."""

    def __init__(self, config: CAAgentConfig, tool_registry: ToolRegistry):
        """Initialize CAAgent with config and tool registry."""
        self.config = config
        self.tool_registry = tool_registry
        self.name = config.name
        self.tools = config.tools

    def run(self, input_data: str) -> AgentResult:
        """Run the agent with given input data."""
        return AgentResult(
            content=f"Agent {self.config.name} processed: {input_data}",
            success=True,
            iterations_used=1
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt from config."""
        return self.config.system_prompt

    def _get_tool_schemas(self) -> List[dict[str, Any]]:
        """Get schemas for registered tools."""
        return self.tool_registry.get_schemas()
