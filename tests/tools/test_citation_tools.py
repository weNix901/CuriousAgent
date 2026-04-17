"""Tests for citation extraction tools."""

import pytest
import asyncio


class TestExtractPaperCitationsTool:
    def test_tool_name_is_correct(self):
        from core.tools.citation_tools import ExtractPaperCitationsTool
        tool = ExtractPaperCitationsTool()
        assert tool.name == "extract_paper_citations"
    
    def test_extract_doi_from_content(self):
        from core.tools.citation_tools import ExtractPaperCitationsTool
        tool = ExtractPaperCitationsTool()
        content = "See Smith et al. (2023) doi:10.1234/arxiv.2023.001 for details"
        result = asyncio.run(tool.execute(content=content, topic="test"))
        assert "10.1234/arxiv.2023.001" in result


class TestExtractWebCitationsTool:
    def test_tool_name_is_correct(self):
        from core.tools.citation_tools import ExtractWebCitationsTool
        tool = ExtractWebCitationsTool()
        assert tool.name == "extract_web_citations"
