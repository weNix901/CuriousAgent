"""Tests for tool base class."""
import pytest
from core.tools.base import Tool


class MockTool(Tool):
    @property
    def name(self) -> str:
        return "test_tool"
    
    @property
    def description(self) -> str:
        return "A test tool"
    
    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"input": {"type": "string"}}}
    
    async def execute(self, **kwargs) -> str:
        return "result"


class TestToolBase:
    def test_tool_name_property(self):
        tool = MockTool()
        assert tool.name == "test_tool"

    def test_tool_description_property(self):
        tool = MockTool()
        assert tool.description == "A test tool"

    def test_tool_parameters_property(self):
        tool = MockTool()
        params = tool.parameters
        assert params["type"] == "object"

    def test_tool_to_schema_format(self):
        tool = MockTool()
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "test_tool"

    def test_tool_to_schema_has_description(self):
        tool = MockTool()
        schema = tool.to_schema()
        assert schema["function"]["description"] == "A test tool"

    def test_tool_to_schema_has_parameters(self):
        tool = MockTool()
        schema = tool.to_schema()
        assert "parameters" in schema["function"]

    @pytest.mark.asyncio
    async def test_tool_execute(self):
        tool = MockTool()
        result = await tool.execute(input="test")
        assert result == "result"


class TestToolImports:
    def test_base_imports(self):
        from core.tools import base
        assert hasattr(base, 'Tool')