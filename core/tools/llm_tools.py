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


class LLMCandidateIdentifyTool(Tool):
    """Identify knowledge point candidates from content."""

    @property
    def name(self) -> str:
        return "llm_candidate_identify"

    @property
    def description(self) -> str:
        return "Identify knowledge point candidates from content with relevance scoring"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt to send to the LLM"
                },
                "task_type": {
                    "type": "string",
                    "description": "Type of task (analysis, extraction, generation)",
                    "default": "general"
                }
            },
            "required": ["prompt"]
        }

    async def execute(self, **kwargs: Any) -> str:
        prompt = kwargs.get("prompt", "")
        task_type = kwargs.get("task_type", "general")

        if not prompt:
            return "Error: Empty prompt provided"

        providers = ["volcengine", "minimax"]
        last_error = None

        for provider in providers:
            try:
                client = LLMClient(provider_name=provider)
                response = client.chat(prompt)
                return response
            except Exception as e:
                last_error = e
                continue

        return f"Error: All providers failed: {str(last_error)}"


class LLMKnowledgeExtractTool(Tool):
    """Extract structured knowledge using object-oriented KnowledgeNode model."""

    @property
    def name(self) -> str:
        return "llm_extract_knowledge"

    @property
    def description(self) -> str:
        return "Extract structured knowledge with Content, Source, Relations, and Citation objects"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to extract knowledge from"
                },
                "topic": {
                    "type": "string",
                    "description": "The topic name for the knowledge point"
                },
                "source_url": {
                    "type": "string",
                    "description": "Optional source URL for traceability"
                }
            },
            "required": ["content", "topic"]
        }

    async def execute(self, **kwargs: Any) -> str:
        content = kwargs.get("content", "")
        topic = kwargs.get("topic", "")
        source_url = kwargs.get("source_url", "")

        if not content or not topic:
            return json.dumps({"error": "content and topic are required"})

        result = await self._extract_with_fallback(content, topic, source_url)
        return result

    async def _extract_with_fallback(self, content: str, topic: str, source_url: str) -> str:
        providers = ["volcengine", "minimax"]
        last_error = None

        for provider in providers:
            try:
                return await self._call_extraction(content, topic, source_url, provider)
            except Exception as e:
                last_error = e
                continue

        return json.dumps({"error": f"All providers failed: {str(last_error)}"})

    async def _call_extraction(self, content: str, topic: str, source_url: str, provider: str) -> str:
        client = LLMClient(provider_name=provider)

        prompt = f"""Extract structured knowledge about "{topic}" from this content.

Content:
{content[:6000]}

Return a JSON object with this EXACT structure:

{{
  "topic": "{topic}",
  "content": {{
    "definition": "What is this concept? (1-2 sentences)",
    "formula": "Key formula or N/A",
    "fact": "Key facts or properties",
    "examples": ["Example 1", "Example 2"],
    "completeness_score": 3
  }},
  "source": {{
    "source_url": "{source_url or 'N/A'}",
    "source_type": "web",
    "source_trusted": false,
    "local_file_path": null,
    "local_file_type": null,
    "source_missing": false
  }},
  "relations": {{
    "parent": "Parent topic or null",
    "children": [],
    "depends_on": ["Prerequisite 1"],
    "related_to": ["Related 1"],
    "cites": [],
    "applied_in": ["Application 1"]
  }},
  "citation": {{
    "citation_title": null,
    "citation_authors": [],
    "citation_year": null,
    "citation_venue": null
  }},
  "keywords": ["keyword1", "keyword2"],
  "quality": 7.0,
  "status": "done"
}}

Rules:
- definition: Atomic description (what is it)
- formula: LaTeX or code pattern, or "N/A"
- examples: Concrete instances
- completeness_score: 1-6 based on filled fields
- quality: 0-10 extraction confidence
- status: Always "done" """

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
