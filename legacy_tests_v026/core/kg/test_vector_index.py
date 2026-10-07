"""Tests for Neo4j vector index initialization."""
import pytest
from core.kg.neo4j_client import Neo4jClient


@pytest.mark.asyncio
async def test_vector_index_exists():
    """Verify knowledge_embeddings vector index exists."""
    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="R1D3researcher2026"
    )
    await client.connect()
    
    result = await client.execute_query("SHOW VECTOR INDEXES")
    index_names = [r.get("name") for r in result]
    
    assert "knowledge_embeddings" in index_names
    await client.disconnect()
