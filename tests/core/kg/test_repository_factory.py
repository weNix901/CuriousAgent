"""
Tests for KGRepositoryFactory - singleton pattern and sync wrappers.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestKGRepositoryFactorySingleton:
    """Test singleton pattern for KGRepositoryFactory."""

    def teardown_method(self):
        """Reset singleton instance after each test."""
        from core.kg.repository_factory import KGRepositoryFactory
        KGRepositoryFactory._instance = None

    def test_get_instance_returns_singleton(self):
        """get_instance should return the same instance on multiple calls."""
        from core.kg.repository_factory import KGRepositoryFactory
        
        f1 = KGRepositoryFactory.get_instance()
        f2 = KGRepositoryFactory.get_instance()
        
        assert f1 is f2

    def test_get_instance_creates_new_instance_first_time(self):
        """First call to get_instance should create a new instance."""
        from core.kg.repository_factory import KGRepositoryFactory
        
        instance = KGRepositoryFactory.get_instance()
        
        assert instance is not None
        assert isinstance(instance, KGRepositoryFactory)

    def test_get_kg_factory_function_returns_singleton(self):
        """get_kg_factory() should return the singleton instance."""
        from core.kg.repository_factory import get_kg_factory, KGRepositoryFactory
        
        factory1 = get_kg_factory()
        factory2 = get_kg_factory()
        
        assert factory1 is factory2
        assert isinstance(factory1, KGRepositoryFactory)


class TestKGRepositoryFactorySyncWrappers:
    """Test sync wrapper methods (skipped - require Neo4j connection)."""

    @pytest.mark.skip(reason="Requires actual Neo4j connection")
    def test_get_node_sync_returns_node(self):
        """get_node_sync should return node data for existing topic."""
        from core.kg.repository_factory import get_kg_factory
        
        factory = get_kg_factory()
        result = factory.get_node_sync("test_topic")
        
        # This test requires Neo4j to be running with test data
        assert result is None or isinstance(result, dict)

    @pytest.mark.skip(reason="Requires actual Neo4j connection")
    def test_create_knowledge_node_sync_returns_id(self):
        """create_knowledge_node_sync should return node ID."""
        from core.kg.repository_factory import get_kg_factory
        
        factory = get_kg_factory()
        node_id = factory.create_knowledge_node_sync(
            topic="test_sync_node",
            content="Test content",
            source_urls=["https://example.com"],
            metadata={"test": True}
        )
        
        assert isinstance(node_id, str)

    @pytest.mark.skip(reason="Requires actual Neo4j connection")
    def test_query_knowledge_sync_returns_list(self):
        """query_knowledge_sync should return list of nodes."""
        from core.kg.repository_factory import get_kg_factory
        
        factory = get_kg_factory()
        results = factory.query_knowledge_sync("test", limit=5)
        
        assert isinstance(results, list)


class TestKGRepositoryFactoryEnsureConnected:
    """Test _ensure_connected method (skipped - requires Neo4j)."""

    @pytest.mark.skip(reason="Requires actual Neo4j connection")
    @pytest.mark.asyncio
    async def test_ensure_connected_creates_client_and_repo(self):
        """_ensure_connected should create Neo4jClient and KGRepository."""
        from core.kg.repository_factory import KGRepositoryFactory
        
        factory = KGRepositoryFactory.get_instance()
        repo = await factory._ensure_connected()
        
        assert repo is not None
        assert factory._client is not None
        assert factory._repo is not None
