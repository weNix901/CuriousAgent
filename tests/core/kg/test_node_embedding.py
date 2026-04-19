"""
Tests for node embedding generation in KGRepository - TDD RED phase
Tests are written BEFORE implementation exists.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


class TestNodeEmbeddingGeneration:
    """Test that create_knowledge_node generates embeddings for new nodes."""

    @pytest.mark.asyncio
    async def test_new_node_has_embedding_with_mock_service(self):
        """Verify new knowledge node has embedding property when embedding service is provided."""
        from core.kg.kg_repository import KGRepository
        
        # Mock Neo4j client
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"id": "test-embedding-node-12345", "status": "pending"}
        ])
        
        # Mock embedding service
        mock_embedding_service = MagicMock()
        mock_embedding_service.embed = MagicMock(return_value=[[0.1] * 1024])
        
        repo = KGRepository(mock_client, mock_embedding_service)
        
        # Create test node with new parameters
        await repo.create_knowledge_node(
            topic="test-embedding-node-12345",
            content="This is test content for embedding verification",
            key_points=["test point 1", "test point 2"],
            keywords=["test", "embedding"]
        )
        
        # Verify embedding was generated
        mock_embedding_service.embed.assert_called_once()
        call_args = mock_embedding_service.embed.call_args[0][0]
        assert isinstance(call_args, list)
        assert len(call_args) == 1
        # Combined text should contain topic, key_points, content, and keywords
        combined_text = call_args[0]
        assert "test-embedding-node-12345" in combined_text
        assert "test point 1" in combined_text
        assert "This is test content for embedding verification" in combined_text
        assert "test" in combined_text

    @pytest.mark.asyncio
    async def test_create_node_without_embedding_service(self):
        """Verify node creation works when embedding_service is None."""
        from core.kg.kg_repository import KGRepository
        
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"id": "test-no-embedding", "status": "pending"}
        ])
        
        # No embedding service provided
        repo = KGRepository(mock_client, None)
        
        # Should not raise error
        node_id = await repo.create_knowledge_node(
            topic="test-no-embedding",
            content="Test content without embedding",
            key_points=["point 1"],
            keywords=["test"]
        )
        
        assert node_id == "test-no-embedding"

    @pytest.mark.asyncio
    async def test_combined_text_format(self):
        """Verify the combined text follows the expected format."""
        from core.kg.kg_repository import KGRepository
        
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"id": "test-format", "status": "pending"}
        ])
        
        mock_embedding_service = MagicMock()
        mock_embedding_service.embed = MagicMock(return_value=[[0.1] * 1024])
        
        repo = KGRepository(mock_client, mock_embedding_service)
        
        await repo.create_knowledge_node(
            topic="test-topic",
            content="test content",
            key_points=["point1", "point2"],
            keywords=["kw1", "kw2"]
        )
        
        combined_text = mock_embedding_service.embed.call_args[0][0][0]
        # Check format markers
        assert "【主题】" in combined_text or "topic" in combined_text.lower()
        assert "【关键要点】" in combined_text or "key point" in combined_text.lower()
        assert "【简介】" in combined_text or "content" in combined_text.lower()
        assert "【关键词】" in combined_text or "keyword" in combined_text.lower()

    @pytest.mark.asyncio
    async def test_embedding_stored_in_neo4j(self):
        """Verify embedding is included in the Cypher SET clause."""
        from core.kg.kg_repository import KGRepository
        
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"id": "test-store", "status": "pending"}
        ])
        
        mock_embedding_service = MagicMock()
        mock_embedding_service.embed = MagicMock(return_value=[[0.5] * 1024])
        
        repo = KGRepository(mock_client, mock_embedding_service)
        
        await repo.create_knowledge_node(
            topic="test-store",
            content="test content",
            key_points=["point"],
            keywords=["kw"]
        )
        
        # Verify execute_write was called with embedding parameter
        call_kwargs = mock_client.execute_write.call_args[1]
        assert "embedding" in call_kwargs
        assert call_kwargs["embedding"] == [0.5] * 1024

    @pytest.mark.asyncio
    async def test_key_points_and_keywords_stored(self):
        """Verify key_points and keywords are stored in Neo4j."""
        from core.kg.kg_repository import KGRepository
        
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"id": "test-meta", "status": "pending"}
        ])
        
        mock_embedding_service = MagicMock()
        mock_embedding_service.embed = MagicMock(return_value=[[0.1] * 1024])
        
        repo = KGRepository(mock_client, mock_embedding_service)
        
        test_key_points = ["important point 1", "important point 2"]
        test_keywords = ["ml", "nlp", "embedding"]
        
        await repo.create_knowledge_node(
            topic="test-meta",
            content="test content",
            key_points=test_key_points,
            keywords=test_keywords
        )
        
        call_kwargs = mock_client.execute_write.call_args[1]
        assert "key_points" in call_kwargs
        assert "keywords" in call_kwargs
        assert call_kwargs["key_points"] == test_key_points
        assert call_kwargs["keywords"] == test_keywords

    @pytest.mark.asyncio
    async def test_empty_key_points_and_keywords_handled(self):
        """Verify None/empty key_points and keywords are handled gracefully."""
        from core.kg.kg_repository import KGRepository
        
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"id": "test-empty", "status": "pending"}
        ])
        
        mock_embedding_service = MagicMock()
        mock_embedding_service.embed = MagicMock(return_value=[[0.1] * 1024])
        
        repo = KGRepository(mock_client, mock_embedding_service)
        
        # Test with None values
        await repo.create_knowledge_node(
            topic="test-empty",
            content="test content"
            # key_points and keywords default to None
        )
        
        # Should not raise error
        call_kwargs = mock_client.execute_write.call_args[1]
        assert "key_points" in call_kwargs
        assert "keywords" in call_kwargs
