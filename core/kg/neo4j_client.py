"""Neo4j client wrapper for KG operations."""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Wrapper for Neo4j database operations."""

    def __init__(self, uri: str, username: str, password: str, max_connection_lifetime: int = 3600):
        self.uri = uri
        self.username = username
        self.password = password
        self.max_connection_lifetime = max_connection_lifetime
        self._driver: Optional[Any] = None

    async def connect(self) -> bool:
        """Establish connection to Neo4j database."""
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_lifetime=self.max_connection_lifetime
            )
            return True
        except Exception as e:
            raise Exception(f"Failed to connect to Neo4j: {e}")

    async def disconnect(self) -> None:
        """Close connection to Neo4j database."""
        if self._driver:
            self._driver.close()
            self._driver = None

    async def execute_query(self, query: str, **parameters) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        if not self._driver:
            raise RuntimeError("Not connected to Neo4j")

        def _run_query(tx):
            result = tx.run(query, **parameters)
            return [record.data() for record in result]

        loop = asyncio.get_event_loop()
        session = self._driver.session()
        try:
            result = await loop.run_in_executor(None, lambda: session.execute_read(_run_query))
            return result
        finally:
            session.close()

    async def execute_write(self, query: str, **parameters) -> List[Dict[str, Any]]:
        """Execute a write Cypher query."""
        if not self._driver:
            raise RuntimeError("Not connected to Neo4j")

        def _run_write(tx):
            result = tx.run(query, **parameters)
            return [record.data() for record in result]

        loop = asyncio.get_event_loop()
        session = self._driver.session()
        try:
            result = await loop.run_in_executor(None, lambda: session.execute_write(_run_write))
            return result
        finally:
            session.close()

    async def health_check(self) -> bool:
        """Check if connection is healthy."""
        if not self._driver:
            return False
        try:
            result = await self.execute_query("RETURN 1 as test")
            return len(result) > 0
        except Exception as e:
            logger.warning(f"Neo4j health check failed: {e}", exc_info=True)
            return False

    def is_connected(self) -> bool:
        """Check if driver is initialized."""
        return self._driver is not None