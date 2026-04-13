"""Tests for tool_registry module."""
import pytest
from core.tools.registry import ToolRegistry
from core.tools.base import Tool


class MockTool(Tool):
    @property
    def name(self) -> str:
        return "mock_tool"
    
    @property
    def description(self) -> str:
        return "A mock tool for testing"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            }
        }
    
    async def execute(self, **kwargs) -> str:
        return f"executed with {kwargs}"


class TestToolRegistry:
    def test_create_empty_registry(self):
        registry = ToolRegistry()
        assert len(registry) == 0

    def test_register_tool(self):
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        assert len(registry) == 1
        assert registry.has("mock_tool")

    def test_get_tool(self):
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        retrieved = registry.get("mock_tool")
        assert retrieved is tool

    def test_get_missing_tool(self):
        registry = ToolRegistry()
        retrieved = registry.get("nonexistent")
        assert retrieved is None

    def test_list_tools(self):
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        names = registry.list_tools()
        assert names == ["mock_tool"]

    def test_unregister_tool(self):
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        registry.unregister("mock_tool")
        assert len(registry) == 0

    def test_contains_tool(self):
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        assert "mock_tool" in registry

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        result = await registry.execute("mock_tool", {"input": "test"})
        assert "test" in result

    @pytest.mark.asyncio
    async def test_execute_missing_tool(self):
        registry = ToolRegistry()
        result = await registry.execute("nonexistent", {})
        assert "Error" in result

    def test_get_schemas(self):
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)
        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"


class TestToolBase:
    def test_tool_has_name(self):
        tool = MockTool()
        assert tool.name == "mock_tool"

    def test_tool_has_description(self):
        tool = MockTool()
        assert tool.description == "A mock tool for testing"

    def test_tool_to_schema(self):
        tool = MockTool()
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "mock_tool"