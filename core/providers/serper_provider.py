"""Serper Google Search Provider Implementation"""
import json
import os
import subprocess
from typing import Optional

from core.search_provider import SearchProvider


class SerperProvider(SearchProvider):
    """Serper.dev Google Search API Provider"""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        self._name = "serper"
    
    @property
    def name(self) -> str:
        return self._name
    
    async def search(self, query: str) -> dict:
        """Execute Serper search"""
        if not self._api_key:
            return {"results": [], "result_count": 0, "raw": {}}
        
        url = "https://google.serper.dev/search"
        payload = {"q": query, "num": 5}
        
        try:
            result = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", f"X-API-KEY: {self._api_key}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps(payload)],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            
            if isinstance(data, dict):
                organic = data.get("organic", [])
                return {
                    "results": self._parse_results(organic),
                    "result_count": len(organic),
                    "raw": data
                }
        except Exception as e:
            return {"results": [], "result_count": 0, "raw": {"error": str(e)}}
        
        return {"results": [], "result_count": 0, "raw": {}}
    
    def _parse_results(self, items: list) -> list:
        """Parse Serper results to standard format"""
        results = []
        for item in items:
            if isinstance(item, dict):
                results.append({
                    "title": str(item.get("title", ""))[:150],
                    "snippet": str(item.get("snippet", ""))[:400],
                    "url": str(item.get("link", ""))
                })
        return results
    
    async def related_terms(self, query: str) -> list[dict]:
        """Get related terms"""
        return []
