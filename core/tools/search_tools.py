"""Search tools for Curious Agent."""
import asyncio
import json
import re
from pathlib import Path
from typing import Any

import aiohttp
import pdfplumber

from core.tools.base import Tool


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
        primary = search_config.get("primary", "bocha")
        return self.get_provider(primary)
    
    def get_fallback_provider(self):
        """Get fallback provider from config."""
        search_config = self._config.get("search", {})
        fallback = search_config.get("bocha_fallback", "serper_empty")
        if fallback == "serper_empty":
            return self.get_provider("serper")
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
            except Exception:
                pass
        
        fallback = registry.get_fallback_provider()
        if fallback:
            try:
                result = await fallback.search(query)
                return self._format_results(result)
            except Exception as e:
                return f"Error: Search failed - {str(e)}"
        
        return "Error: No search providers available"
    
    def _format_results(self, result: dict) -> str:
        results = result.get("results", [])
        count = result.get("result_count", 0)
        
        if count == 0:
            return "No results found"
        
        lines = [f"Found {count} results:"]
        for i, item in enumerate(results, 1):
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            snippet = item.get("snippet", "")[:200]
            lines.append(f"{i}. {title}\n   URL: {url}\n   {snippet}")
        
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
    """Full pipeline: download PDF, parse, and extract text."""
    
    @property
    def name(self) -> str:
        return "process_paper"
    
    @property
    def description(self) -> str:
        return "Download a PDF paper from URL, parse it, and extract text content"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the PDF paper to process"
                },
                "temp_path": {
                    "type": "string",
                    "description": "Optional temporary path for downloaded PDF"
                }
            },
            "required": ["url"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url", "")
        temp_path = kwargs.get("temp_path", "/tmp/temp_paper.pdf")
        
        if not url:
            return "Error: url parameter is required"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        return f"Error: HTTP {response.status}"
                    
                    pdf_bytes = await response.read()
                    
                    with open(temp_path, "wb") as f:
                        f.write(pdf_bytes)
        except asyncio.TimeoutError:
            return "Error: Download timed out"
        except Exception as e:
            return f"Error: Failed to download - {str(e)}"
        
        try:
            with pdfplumber.open(temp_path) as pdf:
                pages_text = []
                for i, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages_text.append(text)
                
                try:
                    Path(temp_path).unlink()
                except Exception:
                    pass
                
                if not pages_text:
                    return "Warning: No text could be extracted from PDF"
                
                full_text = "\n\n".join(pages_text)
                return f"Extracted from {url}:\n\n{full_text[:8000]}"
        except Exception as e:
            try:
                Path(temp_path).unlink()
            except Exception:
                pass
            return f"Error: Failed to parse PDF - {str(e)}"
