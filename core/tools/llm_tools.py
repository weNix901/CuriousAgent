"""LLM-powered tools for analysis and summarization."""
import json
from typing import Any

from core.tools.base import Tool
from core.llm_client import LLMClient


class LLMAnalyzeTool(Tool):
    """Tool for analyzing content and returning structured insights."""

    @property
    def name(self) -> str:
        return "llm_analyze"

    @property
    def description(self) -> str:
        return "Analyze content and return structured insights including key points, insights, and confidence score"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to analyze"
                },
                "analysis_type": {
                    "type": "string",
                    "description": "Type of analysis (e.g., technical, general, scientific)",
                    "default": "general"
                }
            },
            "required": ["content"]
        }

    async def execute(self, **kwargs: Any) -> str:
        """Execute the analysis tool."""
        content = kwargs.get("content", "")
        analysis_type = kwargs.get("analysis_type", "general")

        if not content:
            return json.dumps({
                "error": "Empty content provided",
                "key_points": [],
                "insights": [],
                "confidence": 0.0
            })

        result = await self._analyze_with_fallback(content, analysis_type)
        return result

    async def _analyze_with_fallback(self, content: str, analysis_type: str) -> str:
        """Analyze content with provider fallback."""
        providers = ["volcengine", "minimax"]
        last_error = None

        for provider in providers:
            try:
                result = await self._call_llm(
                    content=content,
                    analysis_type=analysis_type,
                    provider=provider
                )
                return result
            except Exception as e:
                last_error = e
                continue

        return json.dumps({
            "error": f"All providers failed: {str(last_error)}",
            "key_points": [],
            "insights": [],
            "confidence": 0.0
        })

    async def _call_llm(self, content: str, analysis_type: str, provider: str) -> str:
        """Call LLM for analysis."""
        client = LLMClient(provider_name=provider)

        prompt = f"""Analyze the following content and provide structured insights.

Content to analyze:
{content}

Analysis type: {analysis_type}

Return a JSON object with exactly this structure:
{{
  "key_points": ["list of key points extracted"],
  "insights": ["list of deeper insights or patterns"],
  "confidence": 0.0-1.0 (confidence score in the analysis)
}}

Be concise but comprehensive. Focus on the most important aspects."""

        response = client.chat(prompt)

        try:
            start = response.find('{')
            end = response.rfind('}')
            if start >= 0 and end > start:
                parsed = json.loads(response[start:end + 1])
                return json.dumps(parsed)
        except json.JSONDecodeError:
            pass

        return response


class LLMSummarizeTool(Tool):
    """Tool for summarizing content to key points."""

    @property
    def name(self) -> str:
        return "llm_summarize"

    @property
    def description(self) -> str:
        return "Summarize content to key points and a brief summary"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to summarize"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum length of summary in words",
                    "default": 100
                }
            },
            "required": ["content"]
        }

    async def execute(self, **kwargs: Any) -> str:
        """Execute the summarization tool."""
        content = kwargs.get("content", "")
        max_length = kwargs.get("max_length", 100)

        if not content:
            return json.dumps({
                "error": "Empty content provided",
                "summary": "",
                "key_points": [],
                "length": 0
            })

        result = await self._summarize_with_fallback(content, max_length)
        return result

    async def _summarize_with_fallback(self, content: str, max_length: int) -> str:
        """Summarize content with provider fallback."""
        providers = ["volcengine", "minimax"]
        last_error = None

        for provider in providers:
            try:
                result = await self._call_llm(
                    content=content,
                    max_length=max_length,
                    provider=provider
                )
                return result
            except Exception as e:
                last_error = e
                continue

        return json.dumps({
            "error": f"All providers failed: {str(last_error)}",
            "summary": "",
            "key_points": [],
            "length": 0
        })

    async def _call_llm(self, content: str, max_length: int, provider: str) -> str:
        """Call LLM for summarization."""
        client = LLMClient(provider_name=provider)

        prompt = f"""Summarize the following content concisely.

Content to summarize:
{content}

Constraints:
- Summary should be approximately {max_length} words or less
- Extract the most important key points

Return a JSON object with exactly this structure:
{{
  "summary": "brief summary of the content",
  "key_points": ["list of 3-5 key points"],
  "length": <actual word count of summary>
}}

Be concise and focus on the most essential information."""

        response = client.chat(prompt)

        try:
            start = response.find('{')
            end = response.rfind('}')
            if start >= 0 and end > start:
                parsed = json.loads(response[start:end + 1])
                return json.dumps(parsed)
        except json.JSONDecodeError:
            pass

        return response
