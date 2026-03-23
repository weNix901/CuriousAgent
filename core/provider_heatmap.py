"""Provider Coverage Heatmap - Track which providers work best for which domains"""
from collections import defaultdict
from typing import Optional


class ProviderHeatmap:
    """
    Emergent heatmap of Provider coverage by (language, domain)
    Built incrementally from verification logs
    """
    
    def __init__(self):
        self._heatmap = defaultdict(lambda: defaultdict(int))
        self._verification_count = defaultdict(int)
    
    def record_verification(self, language: str, domain: str, provider_results: dict):
        """Record a verification result"""
        key = (language, domain)
        self._verification_count[key] += 1
        
        for provider, count in provider_results.items():
            self._heatmap[key][provider] += count
    
    def get_coverage(self, language: str, domain: str) -> dict:
        """Get coverage stats for a (language, domain) pair"""
        return dict(self._heatmap.get((language, domain), {}))
    
    def get_best_providers(self, language: str, domain: str) -> list:
        """Get providers sorted by coverage for a domain"""
        coverage = self.get_coverage(language, domain)
        if not coverage:
            return []
        return sorted(coverage.keys(), key=lambda p: coverage[p], reverse=True)


_heatmap_instance: Optional[ProviderHeatmap] = None


def get_heatmap() -> ProviderHeatmap:
    """Get global heatmap instance"""
    global _heatmap_instance
    if _heatmap_instance is None:
        _heatmap_instance = ProviderHeatmap()
    return _heatmap_instance
