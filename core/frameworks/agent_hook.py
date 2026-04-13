"""Agent hook system for CA."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentHookContext:
    iteration: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)
    result: Any = None
    metadata: dict = field(default_factory=dict)


class AgentHook(ABC):
    @abstractmethod
    def before_iteration(self, context: AgentHookContext) -> None:
        pass
    
    @abstractmethod
    def after_iteration(self, context: AgentHookContext) -> None:
        pass
    
    @abstractmethod
    def on_tool_call(self, tool_name: str, params: dict) -> None:
        pass
    
    @abstractmethod
    def on_error(self, error: Exception) -> None:
        pass
    
    @abstractmethod
    def on_complete(self, result: Any) -> None:
        pass