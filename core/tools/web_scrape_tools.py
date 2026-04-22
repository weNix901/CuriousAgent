"""Web scrape tools for DeepReadAgent pipeline."""
import asyncio
import json
import logging
import os
import re
import hashlib
from pathlib import Path
from typing import Any

import aiohttp

from core.tools.base import Tool
from core.tools.queue_tools import QueueStorage

logger = logging.getLogger(__name__)

PAPERS_DIR = Path(__file__).parent.parent.parent / "papers"
TRUSTED_SOURCES_PATH = Path(__file__).parent.parent.parent / "config" / "trusted_sources.json"


class WebScrapeConfig:
    """Configuration for web scraping."""
    
    def __init__(self):
        self._config = self._load_config()
        self._trusted_sources = self._load_trusted_sources()
    
    def _load_config(self) -> dict:
        if TRUSTED_SOURCES_PATH.exists():
            with open(TRUSTED_SOURCES_PATH) as f:
                return json.load(f)
        return {}
    
    def _load_trusted_sources(self) -> dict:
        sources = self._config.get("sources", [])
        return {s["domain"]: s for s in sources if s.get("enabled", True)}
    
    def is_web_scrape_allowed(self, url: str) -> tuple[bool, int, str]:
        """Check if URL is from a trusted source that allows web scraping.
        
        Returns: (allowed, trust_level, source_name)
        """
        for domain, source in self._trusted_sources.items():
            if domain in url:
                if source.get("web_scrape", False):
                    return (True, source.get("trust_level", 3), source.get("name", domain))
                return (False, source.get("trust_level", 3), source.get("name", domain))
        return (False, 0, "unknown")
    
    def get_scrape_config(self) -> dict:
        return self._config.get("web_scrape_config", {
            "max_content_length": 80000,
            "min_content_length": 1000,
            "timeout_seconds": 30
        })


class ScrapeWebForDeepReadTool(Tool):
    """Scrape web content and enqueue for DeepRead processing."""
    
    @property
    def name(self) -> str:
        return "scrape_web_for_deepread"
    
    @property
    def description(self) -> str:
        return "Scrape trusted web content and enqueue for DeepReadAgent 6-element extraction"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to scrape"
                },
                "topic": {
                    "type": "string",
                    "description": "Topic name for the KG node"
                },
                "priority": {
                    "type": "number",
                    "description": "Queue priority (default 8)",
                    "default": 8
                }
            },
            "required": ["url", "topic"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url", "")
        topic = kwargs.get("topic", "")
        priority = kwargs.get("priority", 8)
        
        if not url or not topic:
            return "Error: url and topic are required"
        
        config = WebScrapeConfig()
        allowed, trust_level, source_name = config.is_web_scrape_allowed(url)
        
        if not allowed:
            return f"Error: URL '{url}' is not from a web-scrape-enabled trusted source. Source: {source_name}"
        
        scrape_cfg = config.get_scrape_config()
        
        try:
            content = await self._fetch_and_clean(url, scrape_cfg)
            
            if len(content) < scrape_cfg.get("min_content_length", 1000):
                return f"Error: Content too short ({len(content)} chars), minimum is {scrape_cfg.get('min_content_length', 1000)}"
            
            txt_path = self._save_content(topic, content)
            
            queue_storage = QueueStorage()
            queue_storage.initialize()
            
            queue_storage.add_item(
                topic=topic,
                priority=priority,
                metadata={
                    "task_type": "deep_read",
                    "txt_path": txt_path,
                    "pdf_path": None,
                    "source_url": url,
                    "source_type": "web_scrape",
                    "source_trusted": True,
                    "trust_level": trust_level,
                    "source_name": source_name,
                    "summary_topic": topic
                }
            )
            
            return f"Success: Scraped {len(content)} chars from {source_name}, queued for DeepRead (txt_path={txt_path})"
            
        except asyncio.TimeoutError:
            return f"Error: Request timed out after {scrape_cfg.get('timeout_seconds', 30)}s"
        except Exception as e:
            return f"Error: Failed to scrape - {str(e)}"
    
    async def _fetch_and_clean(self, url: str, config: dict) -> str:
        """Fetch URL and extract clean text."""
        timeout = aiohttp.ClientTimeout(total=config.get("timeout_seconds", 30))
        
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": config.get("user_agent", "CuriousAgent/0.3.3")}
            async with session.get(url, timeout=timeout, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                html = await response.text()
                text = self._strip_html(html)
                return text[:config.get("max_content_length", 80000)]
    
    def _strip_html(self, html: str) -> str:
        """Extract clean text from HTML."""
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<aside[^>]*>.*?</aside>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        text = re.sub(r'<[^>]+>', '', html)
        
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _save_content(self, topic: str, content: str) -> str:
        """Save scraped content to TXT file."""
        PAPERS_DIR.mkdir(parents=True, exist_ok=True)
        
        safe_name = re.sub(r'[^\w\s-]', '', topic)
        safe_name = re.sub(r'\s+', '_', safe_name)[:50]
        
        hash_suffix = hashlib.md5(content.encode()).hexdigest()[:8]
        filename = f"{safe_name}_{hash_suffix}.txt"
        
        txt_path = str(PAPERS_DIR / filename)
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return txt_path


class BatchWebScrapeTool(Tool):
    """Batch scrape multiple URLs for DeepRead."""
    
    @property
    def name(self) -> str:
        return "batch_web_scrape"
    
    @property
    def description(self) -> str:
        return "Batch scrape trusted URLs from KG nodes with source_urls but no completeness"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "number",
                    "description": "Max nodes to process (default 10)",
                    "default": 10
                },
                "min_quality": {
                    "type": "number",
                    "description": "Minimum quality threshold (default 5)",
                    "default": 5
                }
            },
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        limit = kwargs.get("limit", 10)
        min_quality = kwargs.get("min_quality", 5)
        
        from core.kg.repository_factory import KGRepositoryFactory
        
        factory = KGRepositoryFactory()
        await factory._ensure_connected()
        
        query = """
        MATCH (k:Knowledge)
        WHERE k.completeness_score <= 1 
          AND k.source_urls IS NOT NULL 
          AND size(k.source_urls) > 0
          AND k.quality >= $min_quality
        RETURN k.topic as topic, k.source_urls as sources, k.quality as quality
        ORDER BY k.quality DESC
        LIMIT $limit
        """
        
        results = await factory._client.execute_query(query, min_quality=min_quality, limit=limit)
        
        if not results:
            return "No eligible nodes found for web scraping"
        
        scrape_tool = ScrapeWebForDeepReadTool()
        processed = []
        failed = []
        
        for r in results:
            topic = r.get("topic")
            sources = r.get("sources", [])
            
            if isinstance(sources, str):
                try:
                    sources = json.loads(sources)
                except:
                    sources = [sources]
            
            if not sources:
                continue
            
            url = sources[0]
            
            result = await scrape_tool.execute(url=url, topic=topic, priority=8)
            
            if result.startswith("Success"):
                processed.append(topic)
            else:
                failed.append((topic, result.split("Error: ")[-1] if "Error:" in result else result))
        
        return f"Processed {len(processed)} nodes, {len(failed)} failed. Success: {processed[:5]}, Failed: {failed[:3]}"


def register_web_scrape_tools(registry):
    """Register web scrape tools."""
    registry.register(ScrapeWebForDeepReadTool())
    registry.register(BatchWebScrapeTool())