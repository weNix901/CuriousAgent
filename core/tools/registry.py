"""Tool registry for CA."""

from typing import Any

from core.tools.base import Tool


class ToolRegistry:
    """Registry for Curious Agent tools - supports registration, retrieval, and schema generation."""
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
    
    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        return name in self._tools
    
    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
    
    def get_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"
        try:
            return await tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools