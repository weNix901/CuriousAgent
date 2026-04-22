"""Factory for creating KG Repository instances with async support."""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from .neo4j_client import Neo4jClient
from .kg_repository import KGRepository
from core.config import load_config

logger = logging.getLogger(__name__)


class KGRepositoryFactory:
    """Factory for creating KG Repository with sync wrapper methods."""
    
    _instance: Optional['KGRepositoryFactory'] = None
    
    def __init__(self):
        self._client: Optional[Neo4jClient] = None
        self._repo: Optional[KGRepository] = None
        self._embedding_service: Optional[Any] = None
    
    @classmethod
    def get_instance(cls) -> 'KGRepositoryFactory':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def _ensure_connected(self) -> KGRepository:
        """Ensure client is connected and return repository."""
        if self._repo is None:
            # Load config to trigger .env loading
            config = load_config()
            
            uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
            username = os.environ.get("NEO4J_USERNAME", "neo4j")
            password = os.environ.get("NEO4J_PASSWORD", "")
            
            self._client = Neo4jClient(uri, username, password)
            await self._client.connect()
            
            # Initialize embedding service from config
            try:
                from core.embedding_service import EmbeddingService
                embedding_config = config.knowledge.get("embedding")
                if embedding_config:
                    self._embedding_service = EmbeddingService(embedding_config)
                    logger.info(f"Embedding service initialized: {type(self._embedding_service).__name__}")
            except Exception as e:
                logger.warning(f"Failed to initialize embedding service: {e}")
                self._embedding_service = None
            
            self._repo = KGRepository(self._client, self._embedding_service)
        
        return self._repo
    
    def get_node_sync(self, topic: str) -> Optional[Dict[str, Any]]:
        """Sync wrapper for get_node."""
        async def _get():
            repo = await self._ensure_connected()
            return await repo.get_node(topic)
        return asyncio.run(_get())
    
    async def create_knowledge_node_async(
        self,
        topic: str,
        content: str = "",
        source_urls: Optional[list] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """Async version of create_knowledge_node - for use in async contexts."""
        repo = await self._ensure_connected()
        return await repo.create_knowledge_node(
            topic=topic,
            content=content,
            source_urls=source_urls or [],
            relations=[],
            metadata=metadata or {}
        )
    
    def create_knowledge_node_sync(
        self,
        topic: str,
        content: str = "",
        source_urls: Optional[list] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """Sync wrapper for create_knowledge_node - only for truly sync contexts."""
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

    def get_all_nodes_sync(self, limit: int = 100, offset: int = 0) -> list:
        """获取所有知识节点（分页）"""
        async def _get():
            await self._ensure_connected()
            query = """
            MATCH (k:Knowledge)
            RETURN k.topic as topic, 
                   k.content as summary, 
                   k.source_urls as sources,
                   k.status as status,
                   k.quality as quality, 
                   k.depth as depth,
                   k.definition as definition,
                   k.core as core,
                   k.context as context,
                   k.examples as examples,
                   k.formula as formula,
                   k.completeness_score as completeness_score,
                   k.parent_topic as parent_topic
            ORDER BY k.created_at DESC
            SKIP $offset LIMIT $limit
            """
            results = await self._client.execute_query(query, offset=offset, limit=limit)
            return [dict(r) for r in results]
        return asyncio.run(_get())

    async def get_all_nodes_async(self, limit: int = 100, offset: int = 0) -> list:
        """Async version of get_all_nodes."""
        await self._ensure_connected()
        query = """
        MATCH (k:Knowledge)
        RETURN k.topic as topic, 
               k.content as summary, 
               k.source_urls as sources,
               k.status as status,
               k.quality as quality, 
               k.depth as depth,
               k.definition as definition,
               k.core as core,
               k.context as context,
               k.examples as examples,
               k.formula as formula,
               k.completeness_score as completeness_score,
               k.parent_topic as parent_topic
        ORDER BY k.created_at DESC
        SKIP $offset LIMIT $limit
        """
        results = await self._client.execute_query(query, offset=offset, limit=limit)
        return [dict(r) for r in results]

    def get_all_relations_sync(self) -> list:
        """获取所有关系"""
        async def _get():
            await self._ensure_connected()
            query = """
            MATCH (a:Knowledge)-[r]->(b:Knowledge)
            RETURN a.topic as source, b.topic as target, type(r) as relation_type
            """
            results = await self._client.execute_query(query)
            return [dict(r) for r in results]
        return asyncio.run(_get())

    def get_stats_sync(self) -> dict:
        """获取 KG 统计"""
        async def _get():
            await self._ensure_connected()
            query = """
            MATCH (k:Knowledge)
            RETURN count(k) as total_nodes,
                   sum(CASE WHEN k.status = 'done' THEN 1 ELSE 0 END) as done_count,
                   sum(CASE WHEN k.status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                   sum(CASE WHEN k.status = 'exploring' THEN 1 ELSE 0 END) as exploring_count
            """
            result = await self._client.execute_query(query)
            stats = result[0] if result else {}

            rel_query = "MATCH ()-[r]->() RETURN count(r) as total_relations"
            rel_result = await self._client.execute_query(rel_query)
            stats["total_relations"] = rel_result[0]["total_relations"] if rel_result else 0

            return {
                "total_nodes": stats.get("total_nodes", 0),
                "by_status": {
                    "done": stats.get("done_count", 0),
                    "pending": stats.get("pending_count", 0),
                    "exploring": stats.get("exploring_count", 0)
                },
                "total_relations": stats.get("total_relations", 0),
                "total_edges": stats.get("total_relations", 0)
            }
        return asyncio.run(_get())

    def get_graph_overview_sync(self) -> dict:
        """获取完整图结构（前端显示用）"""
        nodes = self.get_all_nodes_sync(limit=500)
        edges = self.get_all_relations_sync()
        return {"nodes": nodes, "edges": edges}

    def query_knowledge_semantic_sync(
        self,
        query_text: str,
        top_k: int = 5,
        threshold: float = 0.75,
        status_filter: str = "done"
    ) -> list:
        """Sync wrapper for query_knowledge_semantic."""
        async def _query():
            repo = await self._ensure_connected()
            return await repo.query_knowledge_semantic(
                query_text=query_text,
                top_k=top_k,
                threshold=threshold,
                status_filter=status_filter
            )
        return asyncio.run(_query())


def get_kg_factory() -> KGRepositoryFactory:
    """Get KG repository factory singleton."""
    return KGRepositoryFactory.get_instance()
