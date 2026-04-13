"""ExploreHook for SpiderAgent exploration tracking."""
import logging
from typing import Any
from core.frameworks.agent_hook import AgentHook, AgentHookContext

logger = logging.getLogger(__name__)


class ExploreHook(AgentHook):
    """Hook for tracking SpiderAgent exploration lifecycle."""

    def before_iteration(self, context: AgentHookContext) -> None:
        logger.info(f"Exploration iteration {context.iteration} starting")

    def after_iteration(self, context: AgentHookContext) -> None:
        quality = context.metadata.get('quality_score', 0)
        logger.info(f"Exploration iteration {context.iteration} complete, quality={quality}")

    def on_tool_call(self, tool_name: str, params: dict) -> None:
        logger.debug(f"Tool call: {tool_name} with params={params}")

    def on_error(self, error: Exception) -> None:
        logger.error(f"Exploration error: {error}")

    def on_complete(self, result: Any) -> None:
        quality = result.get('quality', 0) if isinstance(result, dict) else 0
        logger.info(f"Exploration complete, final quality={quality}")