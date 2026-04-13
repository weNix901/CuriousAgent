"""DreamHook for DreamAgent phase tracking."""
import logging
from typing import Any
from core.frameworks.agent_hook import AgentHook, AgentHookContext

logger = logging.getLogger(__name__)


class DreamHook(AgentHook):
    """Hook for tracking DreamAgent dream phase lifecycle."""

    def before_iteration(self, context: AgentHookContext) -> None:
        phase = context.metadata.get('phase', 'unknown')
        logger.info(f"Dream phase {phase} iteration {context.iteration} starting")

    def after_iteration(self, context: AgentHookContext) -> None:
        queue_size = context.metadata.get('queue_size', 0)
        logger.debug(f"Dream iteration {context.iteration} complete, queue_size={queue_size}")

    def on_tool_call(self, tool_name: str, params: dict) -> None:
        logger.debug(f"Dream tool call: {tool_name} with params={params}")

    def on_error(self, error: Exception) -> None:
        logger.error(f"Dream phase error: {error}")

    def on_complete(self, result: Any) -> None:
        topics = result.get('topics', []) if isinstance(result, dict) else []
        logger.info(f"Dream complete, generated {len(topics)} topics")