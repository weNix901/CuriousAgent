"""Search Provider Abstract Interface"""
from abc import ABC, abstractmethod


class SearchProvider(ABC):
    """Abstract interface for search providers"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier"""
        pass
    
    @abstractmethod
    async def search(self, query: str) -> dict:
        """
        Execute search query
        
        Returns:
            {
                "results": list[dict],
                "result_count": int,
                "raw": dict  # Provider-specific raw response
            }
        """
        pass
    
    @abstractmethod
    async def related_terms(self, query: str) -> list[dict]:
        """
        Get related search terms
        
        Returns:
            [{"term": str, "query_count": int}, ...]
        """
        pass
