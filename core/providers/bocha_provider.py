"""Bocha Search Provider Implementation"""
import json
import os
import subprocess
from typing import Optional

from core.search_provider import SearchProvider


class BochaSearchProvider(SearchProvider):
    """Bocha AI Search API Provider"""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("BOCHA_API_KEY", "")
        self._name = "bocha"
    
    @property
    def name(self) -> str:
        return self._name
    
    async def search(self, query: str) -> dict:
        """Execute Bocha search"""
        if not self._api_key:
            return {"results": [], "result_count": 0, "raw": {}}
        
        url = "https://api.bochaai.com/v1/web-search"
        payload = {"query": query, "count": 5}
        
        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", f"Authorization: Bearer {self._api_key}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps(payload)],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            
            if isinstance(data, dict) and data.get("code") == 200:
                web_pages = data.get("data", {}).get("webPages", {})
                items = web_pages.get("value", [])
                return {
                    "results": self._parse_results(items),
                    "result_count": len(items),
                    "raw": data
                }
        except Exception as e:
            return {"results": [], "result_count": 0, "raw": {"error": str(e)}}
        
        return {"results": [], "result_count": 0, "raw": {}}
    
    def _parse_results(self, items: list) -> list:
        """Parse Bocha results to standard format"""
        results = []
        for item in items:
            if isinstance(item, dict):
                results.append({
                    "title": str(item.get("name", ""))[:150],
                    "snippet": str(item.get("snippet", ""))[:400],
                    "url": str(item.get("url", ""))
                })
        return results
    
    async def related_terms(self, query: str) -> list[dict]:
        """Get related terms (Bocha doesn't support directly, return empty)"""
        return []
