"""Search tools for Curious Agent."""
import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import aiohttp
import pdfplumber

from core.tools.base import Tool

logger = logging.getLogger(__name__)


class SearchProviderRegistry:
    """Registry for search providers with config-based selection."""
    
    def __init__(self):
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        config_path = Path(__file__).parent.parent.parent / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        return {"search": {}}
    
    def get_provider(self, name: str):
        """Get search provider by name."""
        if name == "bocha":
            from core.providers.bocha_provider import BochaSearchProvider
            return BochaSearchProvider()
        elif name == "serper":
            from core.providers.serper_provider import SerperProvider
            return SerperProvider()
        return None
    
    def get_primary_provider(self):
        """Get primary provider from config."""
        search_config = self._config.get("search", {})
        primary = search_config.get("primary", "serper")
        return self.get_provider(primary)
    
    def get_fallback_provider(self):
        """Get fallback provider from config."""
        search_config = self._config.get("search", {})
        fallback = search_config.get("fallback", "bocha")
        return self.get_provider(fallback)


class SearchWebTool(Tool):
    """Search the web using configured search providers."""
    
    @property
    def name(self) -> str:
        return "search_web"
    
    @property
    def description(self) -> str:
        return "Search the web using Bocha or Serper search providers"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string"
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query", "")
        if not query:
            return "Error: query parameter is required"
        
        registry = SearchProviderRegistry()
        
        provider = registry.get_primary_provider()
        if provider:
            try:
                result = await provider.search(query)
                if result.get("result_count", 0) > 0:
                    return self._format_results(result)
            except Exception as e:
                logger.warning(f"Primary search provider failed for '{query}': {e}", exc_info=True)
        
        fallback = registry.get_fallback_provider()
        if fallback:
            try:
                result = await fallback.search(query)
                return self._format_results(result)
            except Exception as e:
                return f"Error: Search failed - {str(e)}"
        
        return "Error: No search providers available"
    
    def _format_results(self, result: dict) -> str:
        from core.trusted_sources import TrustedSourceManager
        
        results = result.get("results", [])
        count = result.get("result_count", 0)
        
        if count == 0:
            return "No results found"
        
        # Check trusted sources
        trusted_manager = TrustedSourceManager()
        trusted_manager.load()
        
        lines = [f"Found {count} results:"]
        for i, item in enumerate(results, 1):
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            snippet = item.get("snippet", "")[:200]
            
            # Check if URL is from trusted source
            trust_check = trusted_manager.check_url(url)
            trust_marker = " [TRUSTED]" if trust_check["is_trusted"] else ""
            
            lines.append(f"{i}. {title}{trust_marker}\n   URL: {url}\n   {snippet}")
        
        return "\n\n".join(lines)


class FetchPageTool(Tool):
    """Fetch webpage content using async HTTP."""
    
    @property
    def name(self) -> str:
        return "fetch_page"
    
    @property
    def description(self) -> str:
        return "Fetch and extract text content from a webpage URL"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the webpage to fetch"
                }
            },
            "required": ["url"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url", "")
        if not url:
            return "Error: url parameter is required"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        return f"Error: HTTP {response.status}"
                    
                    html = await response.text()
                    text = self._strip_html(html)
                    
                    if not text.strip():
                        return "Warning: Page appears to be empty"
                    
                    return text[:8000]
        except asyncio.TimeoutError:
            return "Error: Request timed out"
        except Exception as e:
            return f"Error: Failed to fetch page - {str(e)}"
    
    def _strip_html(self, html: str) -> str:
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', html)
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class DownloadPaperTool(Tool):
    """Download PDF paper from URL."""
    
    @property
    def name(self) -> str:
        return "download_paper"
    
    @property
    def description(self) -> str:
        return "Download a PDF paper from a URL and optionally save to file"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the PDF to download"
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional path to save the PDF file"
                }
            },
            "required": ["url"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url", "")
        output_path = kwargs.get("output_path", "")
        
        if not url:
            return "Error: url parameter is required"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        return f"Error: HTTP {response.status}"
                    
                    content_type = response.headers.get("Content-Type", "")
                    
                    pdf_bytes = await response.read()
                    
                    if output_path:
                        with open(output_path, "wb") as f:
                            f.write(pdf_bytes)
                        return f"Downloaded PDF to {output_path} ({len(pdf_bytes)} bytes)"
                    
                    return f"Downloaded PDF ({len(pdf_bytes)} bytes) from {url}"
        except asyncio.TimeoutError:
            return "Error: Download timed out"
        except Exception as e:
            return f"Error: Failed to download - {str(e)}"


class ParsePdfTool(Tool):
    """Parse PDF file and extract text."""
    
    @property
    def name(self) -> str:
        return "parse_pdf"
    
    @property
    def description(self) -> str:
        return "Extract text content from a PDF file"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "Path to the PDF file to parse"
                }
            },
            "required": ["pdf_path"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        pdf_path = kwargs.get("pdf_path", "")
        
        if not pdf_path:
            return "Error: pdf_path parameter is required"
        
        if not Path(pdf_path).exists():
            return f"Error: File not found - {pdf_path}"
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_text = []
                for i, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages_text.append(f"--- Page {i} ---\n{text}")
                
                if not pages_text:
                    return "Warning: No text could be extracted from PDF"
                
                return "\n\n".join(pages_text)
        except Exception as e:
            return f"Error: Failed to parse PDF - {str(e)}"


class ProcessPaperTool(Tool):
    """Full pipeline: download PDF, parse, save, and extract text."""
    
    @property
    def name(self) -> str:
        return "process_paper"
    
    @property
    def description(self) -> str:
        return "Download a PDF paper from URL, parse it, save to papers/, and extract text content"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the PDF paper to process"
                },
                "topic": {
                    "type": "string",
                    "description": "Topic name for generating stable file paths"
                }
            },
            "required": ["url", "topic"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        import json
        from core.tools.paper_tools import paper_storage_paths, PAPERS_DIR
        
        url = kwargs.get("url", "")
        topic = kwargs.get("topic", "")
        
        if not url:
            return "Error: url parameter is required"
        if not topic:
            return "Error: topic parameter is required"
        
        # Generate stable paths
        pdf_path, txt_path = paper_storage_paths(topic)
        os.makedirs(PAPERS_DIR, exist_ok=True)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as response:
                    if response.status != 200:
                        return f"Error: HTTP {response.status}"
                    
                    pdf_bytes = await response.read()
                    
                    # Save PDF
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_bytes)
        except asyncio.TimeoutError:
            return "Error: Download timed out"
        except Exception as e:
            return f"Error: Failed to download - {str(e)}"
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_text = []
                for i, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages_text.append(text)
                
                if not pages_text:
                    return json.dumps({
                        "pdf_path": pdf_path,
                        "txt_path": None,
                        "text_length": 0,
                        "warning": "No text could be extracted from PDF"
                    })
                
                full_text = "\n\n".join(pages_text)
                
                # Save TXT
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(full_text)
                
                return json.dumps({
                    "pdf_path": pdf_path,
                    "txt_path": txt_path,
                    "text_length": len(full_text),
                    "summary": full_text[:500]  # Summary can be truncated for display
                })
        except Exception as e:
            return f"Error: Failed to parse PDF - {str(e)}"
