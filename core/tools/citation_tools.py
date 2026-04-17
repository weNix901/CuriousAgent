"""引用提取工具"""

import asyncio
import re
import json
from typing import Any
from core.tools.base import Tool


class ExtractPaperCitationsTool(Tool):
    @property
    def name(self) -> str:
        return "extract_paper_citations"
    
    @property
    def description(self) -> str:
        return "Extract citation relationships (DOI, arxiv IDs) from paper content"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Paper content"},
                "topic": {"type": "string", "description": "Current topic"}
            },
            "required": ["content"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        content = kwargs.get("content", "")
        topic = kwargs.get("topic", "")
        
        citations = []
        
        # DOI pattern
        doi_pattern = r'doi:\s*(10\.\d{4}/[^\s]+)'
        dois = re.findall(doi_pattern, content, re.IGNORECASE)
        citations.extend([{"type": "doi", "id": doi} for doi in dois])
        
        # Arxiv pattern
        arxiv_pattern = r'arxiv[:\s]+(\d{4}\.\d{4,5})'
        arxiv_ids = re.findall(arxiv_pattern, content, re.IGNORECASE)
        citations.extend([{"type": "arxiv", "id": arxiv_id} for arxiv_id in arxiv_ids])
        
        return json.dumps({"topic": topic, "citations": citations, "count": len(citations)})


class ExtractWebCitationsTool(Tool):
    @property
    def name(self) -> str:
        return "extract_web_citations"
    
    @property
    def description(self) -> str:
        return "Extract citation links from web page content"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Web content"},
                "topic": {"type": "string", "description": "Current topic"}
            },
            "required": ["content"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        content = kwargs.get("content", "")
        topic = kwargs.get("topic", "")
        
        url_pattern = r'https?://[^\s<>"]+'
        urls = re.findall(url_pattern, content)
        
        domains_to_skip = ['google.com', 'facebook.com', 'twitter.com', 'linkedin.com']
        filtered_urls = [url for url in urls if not any(skip in url for skip in domains_to_skip)]
        
        return json.dumps({"topic": topic, "links": filtered_urls[:20], "count": len(filtered_urls)})
