"""E2E test for complete deep_read pipeline."""
import asyncio
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from core.agents.deep_read_agent import DeepReadAgent, DeepReadAgentConfig
from core.tools.registry import ToolRegistry


class _MockReadPaperText:
    name = "read_paper_text"
    description = "Read paper text"
    parameters = {"type": "object", "properties": {"txt_path": {"type": "string"}}, "required": ["txt_path"]}

    async def execute(self, **kwargs):
        return "mock paper text"

    def to_schema(self):
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


class _MockUpdateKgRelation:
    name = "update_kg_relation"
    description = "Update KG relation"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return "ok"

    def to_schema(self):
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_deep_read_agent_with_tools():
    registry = ToolRegistry()
    registry.register(_MockReadPaperText())
    registry.register(_MockUpdateKgRelation())

    config = DeepReadAgentConfig()
    agent = DeepReadAgent(config=config, tool_registry=registry)

    assert agent.tool_registry.get("read_paper_text") is not None
    assert agent.tool_registry.get("update_kg_relation") is not None


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_extract_knowledge_points_not_stub():
    from core.tools.paper_tools import ExtractKnowledgePointsTool

    tool = ExtractKnowledgePointsTool()

    sample_text = """
    Abstract: FlashAttention is a fast attention algorithm.
    It computes attention in blocks to reduce memory access.
    """

    with patch("core.llm_client.LLMClient") as MockLLMClient:
        MockLLMClient.side_effect = Exception("LLM not configured")

        result = await tool.execute(
            paper_text=sample_text,
            topic="FlashAttention",
            parent_topic="attention"
        )

    parsed = json.loads(result)
    assert parsed.get("status") != "not_implemented"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_extract_formulas_not_stub():
    from core.tools.paper_tools import ExtractFormulasTool

    tool = ExtractFormulasTool()

    plain_text = """
    This is a plain text paper about machine learning.
    It discusses neural networks and training methods.
    """

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(plain_text)
        txt_path = f.name

    try:
        with patch("core.llm_client.LLMClient") as MockLLMClient:
            MockLLMClient.side_effect = Exception("LLM not configured")

            result = await tool.execute(txt_path=txt_path)

        parsed = json.loads(result)
        assert parsed.get("status") != "not_implemented"
    finally:
        os.unlink(txt_path)
