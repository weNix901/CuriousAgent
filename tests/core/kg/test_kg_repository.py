"""
Tests for KGRepository - TDD RED phase
Tests are written BEFORE implementation exists.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from core.kg.knowledge_node import KnowledgeNode, KnowledgeContent, KnowledgeSource, KnowledgeRelations, KnowledgeCitation


class TestKGRepositoryImports:
    """Test that KGRepository can be imported."""

    def test_import_kg_repository(self):
        """Should be able to import KGRepository class."""
        from core.kg.kg_repository import KGRepository
        assert KGRepository is not None

    def test_repository_has_create_knowledge_node(self):
        """KGRepository should have create_knowledge_node method."""
        from core.kg.kg_repository import KGRepository
        repo = KGRepository(MagicMock())
        assert hasattr(repo, 'create_knowledge_node')

    def test_repository_has_query_knowledge(self):
        """KGRepository should have query_knowledge method."""
        from core.kg.kg_repository import KGRepository
        repo = KGRepository(MagicMock())
        assert hasattr(repo, 'query_knowledge')

    def test_repository_has_update_status(self):
        """KGRepository should have update_status method."""
        from core.kg.kg_repository import KGRepository
        repo = KGRepository(MagicMock())
        assert hasattr(repo, 'update_status')

    def test_repository_has_get_relations(self):
        """KGRepository should have get_relations method."""
        from core.kg.kg_repository import KGRepository
        repo = KGRepository(MagicMock())
        assert hasattr(repo, 'get_relations')


class TestKGRepositoryCreateNode:
    """Test create_knowledge_node operation."""

    @pytest.mark.asyncio
    async def test_create_node_returns_node_id(self):
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"id": "node-123", "topic": "test_topic"}
        ])
        
        repo = KGRepository(mock_client)
        node_id = await repo.create_knowledge_node(
            topic="test_topic",
            content="Test content",
            source_urls=["https://example.com"]
        )
        assert node_id is not None

    @pytest.mark.asyncio
    async def test_create_node_with_relations(self):
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(side_effect=[
            [{"id": "node-123"}],
            [{"created": True}]
        ])
        
        repo = KGRepository(mock_client)
        await repo.create_knowledge_node(
            topic="child_topic",
            content="Child content",
            relations=[{"parent": "parent_topic", "type": "IS_CHILD_OF"}]
        )
        mock_client.execute_write.assert_called()

    @pytest.mark.asyncio
    async def test_create_node_sets_defaults(self):
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"id": "node-123", "status": "pending"}
        ])
        
        repo = KGRepository(mock_client)
        await repo.create_knowledge_node(
            topic="new_topic",
            content="New content"
        )
        mock_client.execute_write.assert_called()


class TestKGRepositoryQuery:
    """Test query_knowledge operation."""

    @pytest.mark.asyncio
    async def test_query_by_topic_returns_nodes(self):
        """query_knowledge should return matching nodes."""
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_query = AsyncMock(return_value=[
            {"topic": "agent_memory", "content": "Memory systems", "status": "done"}
        ])
        
        repo = KGRepository(mock_client)
        nodes = await repo.query_knowledge("agent_memory", limit=10)
        assert isinstance(nodes, list)
        assert len(nodes) >= 1

    @pytest.mark.asyncio
    async def test_query_with_limit(self):
        """query_knowledge should respect limit parameter."""
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_query = AsyncMock()
        
        repo = KGRepository(mock_client)
        await repo.query_knowledge("topic", limit=5)
        # Verify limit was passed
        call_args = mock_client.execute_query.call_args
        # Check that limit appears in query or parameters


class TestKGRepositoryUpdate:
    """Test update operations."""

    @pytest.mark.asyncio
    async def test_update_status_changes_status(self):
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"status": "complete"}
        ])
        
        repo = KGRepository(mock_client)
        await repo.update_status("topic", "complete")
        mock_client.execute_write.assert_called()

    @pytest.mark.asyncio
    async def test_update_metadata_sets_fields(self):
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"heat": 5, "quality": 8.5, "confidence": 0.9}
        ])
        
        repo = KGRepository(mock_client)
        await repo.update_metadata("topic", heat=5, quality=8.5, confidence=0.9)
        mock_client.execute_write.assert_called()


class TestKGRepositoryRelations:
    """Test relation operations."""

    @pytest.mark.asyncio
    async def test_get_relations_returns_edges(self):
        """get_relations should return list of relations."""
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_query = AsyncMock(return_value=[
            {"parent": "agent", "child": "agent_memory", "type": "IS_CHILD_OF"}
        ])
        
        repo = KGRepository(mock_client)
        relations = await repo.get_relations("agent_memory")
        assert isinstance(relations, list)

    @pytest.mark.asyncio
    async def test_add_relation_creates_edge(self):
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"created": True}
        ])
        
        repo = KGRepository(mock_client)
        await repo.add_relation("parent_topic", "child_topic", "IS_CHILD_OF")
        mock_client.execute_write.assert_called()


class TestKGRepositoryNodeLifecycle:
    """Test node lifecycle operations."""

    @pytest.mark.asyncio
    async def test_mark_dormant_sets_dormant_status(self):
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"status": "dormant"}
        ])
        
        repo = KGRepository(mock_client)
        await repo.mark_dormant("old_topic")
        mock_client.execute_write.assert_called()

    @pytest.mark.asyncio
    async def test_reactivate_sets_pending_status(self):
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"status": "pending"}
        ])
        
        repo = KGRepository(mock_client)
        await repo.reactivate("dormant_topic")
        mock_client.execute_write.assert_called()


class TestKGRepositoryBatch:
    """Test batch operations."""

    @pytest.mark.asyncio
    async def test_merge_nodes_combines_nodes(self):
        from core.kg.kg_repository import KGRepository
        mock_client = MagicMock()
        mock_client.execute_write = AsyncMock(return_value=[
            {"merged": True, "count": 2}
        ])
        
        repo = KGRepository(mock_client)
        await repo.merge_nodes(["node-1", "node-2"])
        mock_client.execute_write.assert_called()


@pytest.mark.asyncio
async def test_create_knowledge_node_from_model():
    from core.kg.kg_repository import KGRepository
    mock_client = AsyncMock()
    mock_client.execute_write = AsyncMock(return_value=[{"id": "Test Node", "status": "pending"}])
    
    repo = KGRepository(mock_client)
    
    node = KnowledgeNode(
        topic="Test Node",
        content=KnowledgeContent(definition="Test definition"),
        source=KnowledgeSource(source_url="https://example.com", source_type="web"),
        relations=KnowledgeRelations(),
        citation=KnowledgeCitation()
    )
    
    result = await repo.create_knowledge_node_from_model(node)
    assert result == "Test Node"
    mock_client.execute_write.assert_called_once()


@pytest.mark.asyncio
async def test_create_knowledge_node_from_model_with_parent():
    from core.kg.kg_repository import KGRepository
    mock_client = AsyncMock()
    mock_client.execute_write = AsyncMock(return_value=[{"id": "Child Node", "status": "pending"}])
    
    repo = KGRepository(mock_client)
    
    node = KnowledgeNode(
        topic="Child Node",
        content=KnowledgeContent(definition="Child definition"),
        source=KnowledgeSource(source_type="paper"),
        relations=KnowledgeRelations(parent="Parent Node"),
        citation=KnowledgeCitation()
    )
    
    result = await repo.create_knowledge_node_from_model(node)
    assert result == "Child Node"