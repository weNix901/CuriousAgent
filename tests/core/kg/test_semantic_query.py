"""
Tests for query_knowledge_semantic - TDD RED phase
Tests are written BEFORE implementation exists.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestSemanticQueryMethodExists:
    """Test that query_knowledge_semantic method exists."""

    def test_method_exists(self):
        """KGRepository should have query_knowledge_semantic method."""
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_embedding = MagicMock()
        repo = KGRepository(mock_client, mock_embedding)
        assert hasattr(repo, 'query_knowledge_semantic')

    def test_method_is_callable(self):
        """query_knowledge_semantic should be callable."""
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_embedding = MagicMock()
        repo = KGRepository(mock_client, mock_embedding)
        assert callable(getattr(repo, 'query_knowledge_semantic', None))


class TestSemanticQueryReturnsResults:
    """Test semantic query returns matching nodes."""

    @pytest.mark.asyncio
    async def test_semantic_query_returns_results(self):
        """Verify semantic query returns matching nodes."""
        from core.kg.kg_repository import KGRepository
        from core.kg.neo4j_client import Neo4jClient
        from core.embedding_service import EmbeddingService, EmbeddingConfig

        # Use mock client for unit test
        mock_client = MagicMock()
        mock_client.execute_query = AsyncMock(return_value=[
            {
                "topic": "agent 上下文管理系统",
                "content": "Manages agent context windows",
                "score": 0.85
            },
            {
                "topic": "context management",
                "content": "General context handling",
                "score": 0.78
            }
        ])

        # Create embedding service with mock config
        mock_config = MagicMock(spec=EmbeddingConfig)
        mock_config.batch_size = 32
        mock_config.cache_size = 1000
        mock_config.fallback_chain = ["siliconflow", "volcengine", "llm"]
        mock_embedding = MagicMock(spec=EmbeddingService)
        mock_embedding.embed = MagicMock(return_value=[[0.1] * 768])

        repo = KGRepository(mock_client, mock_embedding)

        # Query for agent context management
        results = await repo.query_knowledge_semantic(
            query_text="agent 上下文管理系统是干嘛的？",
            top_k=3,
            threshold=0.70
        )

        assert len(results) > 0
        # Should match "agent 上下文管理系统"
        matched_topics = [r["topic"] for r in results]
        assert any("agent 上下文" in t or "context" in t.lower() for t in matched_topics)

    @pytest.mark.asyncio
    async def test_semantic_query_with_default_threshold(self):
        """Verify semantic query works with default threshold."""
        from core.kg.kg_repository import KGRepository

        mock_client = MagicMock()
        mock_client.execute_query = AsyncMock(return_value=[
            {"topic": "test topic", "content": "test content", "score": 0.80}
        ])

        mock_embedding = MagicMock()
        mock_embedding.embed = MagicMock(return_value=[[0.1] * 768])

        repo = KGRepository(mock_client, mock_embedding)

        results = await repo.query_knowledge_semantic(
            query_text="test query",
            top_k=5
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_semantic_query_empty_results(self):
        """Verify semantic query handles empty results."""
        from core.kg.kg_repository import KGRepository

        mock_client = MagicMock()
        mock_client.execute_query = AsyncMock(return_value=[])

        mock_embedding = MagicMock()
        mock_embedding.embed = MagicMock(return_value=[[0.1] * 768])

        repo = KGRepository(mock_client, mock_embedding)

        results = await repo.query_knowledge_semantic(
            query_text="nonexistent topic xyz",
            top_k=3,
            threshold=0.95
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_semantic_query_without_embedding_service(self):
        """Verify semantic query falls back to text search when embedding_service is None."""
        from core.kg.kg_repository import KGRepository

        mock_client = MagicMock()
        mock_client.execute_query = AsyncMock(return_value=[
            {"topic": "fallback topic", "content": "fallback content"}
        ])

        # No embedding service
        repo = KGRepository(mock_client, None)

        results = await repo.query_knowledge_semantic(
            query_text="fallback test",
            top_k=3
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_semantic_query_calls_vector_index(self):
        """Verify semantic query uses vector index queryNodes."""
        from core.kg.kg_repository import KGRepository

        mock_client = MagicMock()
        mock_client.execute_query = AsyncMock(return_value=[
            {"topic": "test", "content": "content", "score": 0.85}
        ])

        mock_embedding = MagicMock()
        mock_embedding.embed = MagicMock(return_value=[[0.1] * 768])

        repo = KGRepository(mock_client, mock_embedding)

        await repo.query_knowledge_semantic(
            query_text="test query",
            top_k=3,
            threshold=0.75
        )

        # Verify embedding was called
        mock_embedding.embed.assert_called_once()
        # Verify query was executed
        mock_client.execute_query.assert_called_once()
