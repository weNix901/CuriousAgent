"""Factory for creating KG Repository instances with async support."""

import asyncio
import os
from typing import Any, Dict, Optional

from .neo4j_client import Neo4jClient
from .kg_repository import KGRepository


class KGRepositoryFactory:
    """Factory for creating KG Repository with sync wrapper methods."""
    
    _instance: Optional['KGRepositoryFactory'] = None
    
    def __init__(self):
        self._client: Optional[Neo4jClient] = None
        self._repo: Optional[KGRepository] = None
    
    @classmethod
    def get_instance(cls) -> 'KGRepositoryFactory':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def _ensure_connected(self) -> KGRepository:
        """Ensure client is connected and return repository."""
        if self._repo is None:
            uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
            username = os.environ.get("NEO4J_USERNAME", "neo4j")
            password = os.environ.get("NEO4J_PASSWORD", "")
            
            self._client = Neo4jClient(uri, username, password)
            await self._client.connect()
            self._repo = KGRepository(self._client)
        
        return self._repo
    
    def get_node_sync(self, topic: str) -> Optional[Dict[str, Any]]:
        """Sync wrapper for get_node."""
        async def _get():
            repo = await self._ensure_connected()
            return await repo.get_node(topic)
        return asyncio.run(_get())
    
    def create_knowledge_node_sync(
        self,
        topic: str,
        content: str = "",
        source_urls: list = None,
        metadata: dict = None
    ) -> str:
        """Sync wrapper for create_knowledge_node."""
        async def _create():
            repo = await self._ensure_connected()
            return await repo.create_knowledge_node(
                topic=topic,
                content=content,
                source_urls=source_urls or [],
                relations=[],
                metadata=metadata or {}
            )
        return asyncio.run(_create())
    
    def query_knowledge_sync(self, topic: str, limit: int = 10) -> list:
        """Sync wrapper for query_knowledge."""
        async def _query():
            repo = await self._ensure_connected()
            return await repo.query_knowledge(topic, limit)
        return asyncio.run(_query())


def get_kg_factory() -> KGRepositoryFactory:
    """Get KG repository factory singleton."""
    return KGRepositoryFactory.get_instance()
