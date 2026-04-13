"""Serper Google Search Provider Implementation with quota management."""
import json
import os
import subprocess
from typing import Optional

from core.search_provider import SearchProvider
from core.search_quota import get_quota_manager
from core.config import get_config


class SerperProvider(SearchProvider):
    """Serper.dev Google Search API Provider with quota management."""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        self._name = "serper"
        self._quota = None  # Lazy init
    
    @property
    def name(self) -> str:
        return self._name
    
    def _get_quota_config(self):
        if self._quota is None:
            cfg = get_config()
            self._quota = cfg.knowledge.get("search", {}).daily_quota
        return self._quota
    
    async def search(self, query: str) -> dict:
        """Execute Serper search with quota enforcement."""
        if not self._api_key:
            return {"results": [], "result_count": 0, "raw": {"error": "No API key"}}
        
        # Check quota
        quota_cfg = self._get_quota_config()
        quota_mgr = get_quota_manager()
        allowed, status = quota_mgr.check_quota("serper", quota_cfg.serper, quota_cfg.enabled)
        if not allowed:
            return {
                "results": [],
                "result_count": 0,
                "raw": {"error": f"Daily quota exceeded ({status.used}/{status.limit})"}
            }
        
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
                # Record successful API call
                get_quota_manager().record_usage("serper")
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
