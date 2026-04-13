"""
Tests for Neo4jClient - TDD RED phase
Tests are written BEFORE implementation exists.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


class TestNeo4jClientImports:
    """Test that Neo4jClient can be imported."""

    def test_import_neo4j_client(self):
        """Should be able to import Neo4jClient class."""
        from core.kg.neo4j_client import Neo4jClient
        assert Neo4jClient is not None

    def test_client_has_connect_method(self):
        """Neo4jClient should have connect method."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        assert hasattr(client, 'connect')

    def test_client_has_disconnect_method(self):
        """Neo4jClient should have disconnect method."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        assert hasattr(client, 'disconnect')

    def test_client_has_execute_query_method(self):
        """Neo4jClient should have execute_query method."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        assert hasattr(client, 'execute_query')


class TestNeo4jClientConnection:
    """Test connection lifecycle."""

    def test_client_stores_uri(self):
        """Client should store URI."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        assert client.uri == "bolt://localhost:7687"

    def test_client_stores_username(self):
        """Client should store username."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        assert client.username == "neo4j"

    def test_client_stores_password(self):
        """Client should store password."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "secret")
        assert client.password == "secret"

    @pytest.mark.asyncio
    async def test_connect_returns_true_on_success(self):
        """connect() should return True when connection succeeds."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_driver.return_value = MagicMock()
            result = await client.connect()
            assert result is True

    @pytest.mark.asyncio
    async def test_connect_raises_on_failure(self):
        """connect() should raise exception on connection failure."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://invalid:7687", "neo4j", "test")
        
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_driver.side_effect = Exception("Connection failed")
            with pytest.raises(Exception):
                await client.connect()

    @pytest.mark.asyncio
    async def test_disconnect_closes_driver(self):
        """disconnect() should close the driver."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_session = MagicMock()
            mock_driver.return_value = MagicMock()
            await client.connect()
            await client.disconnect()
            # Verify driver was closed
            assert client._driver is None


class TestNeo4jClientQuery:
    """Test query execution."""

    @pytest.mark.asyncio
    async def test_execute_query_returns_records(self):
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_driver_instance = MagicMock()
            mock_session = MagicMock()
            mock_session.execute_read.return_value = [{"name": "test"}]
            mock_driver_instance.session.return_value = mock_session
            mock_driver.return_value = mock_driver_instance
            
            await client.connect()
            result = await client.execute_query("RETURN $name as name", name="test")
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_execute_query_with_parameters(self):
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_driver_instance = MagicMock()
            mock_session = MagicMock()
            mock_session.execute_write.return_value = [{"created": 1}]
            mock_driver_instance.session.return_value = mock_session
            mock_driver.return_value = mock_driver_instance
            
            await client.connect()
            await client.execute_write("CREATE (n:Node {name: $name})", name="test")
            mock_session.execute_write.assert_called_once()


class TestNeo4jClientHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_connected(self):
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        
        with patch('neo4j.GraphDatabase.driver') as mock_driver:
            mock_driver_instance = MagicMock()
            mock_session = MagicMock()
            mock_session.execute_read.return_value = [{"test": 1}]
            mock_driver_instance.session.return_value = mock_session
            mock_driver.return_value = mock_driver_instance
            
            await client.connect()
            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_when_not_connected(self):
        """health_check should return False when not connected."""
        from core.kg.neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        # Don't connect
        result = await client.health_check()
        assert result is False