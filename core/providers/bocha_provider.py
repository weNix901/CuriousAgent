"""Bocha Search Provider Implementation"""
import json
import os
import subprocess
from typing import Optional

from core.search_provider import SearchProvider
from core.search_quota import get_quota_manager
from core.config import get_config


class BochaSearchProvider(SearchProvider):
    """Bocha AI Search API Provider with quota management"""
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("BOCHA_API_KEY", "")
        self._name = "bocha"
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
        """Execute Bocha search with quota enforcement"""
        if not self._api_key:
            return {"results": [], "result_count": 0, "raw": {"error": "No API key"}}
        
        # Check quota
        quota_cfg = self._get_quota_config()
        quota_mgr = get_quota_manager()
        allowed, status = quota_mgr.check_quota("bocha", quota_cfg.bocha, quota_cfg.enabled)
        if not allowed:
            return {
                "results": [],
                "result_count": 0,
                "raw": {"error": f"Daily quota exceeded ({status.used}/{status.limit})"}
            }
        
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
                # Record successful API call
                get_quota_manager().record_usage("bocha")
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
