"""Tests for JSON to Neo4j migration script."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json


class TestMigrationScriptImport:
    """Test that migration script can be imported."""

    def test_import_migration_script(self):
        """Should be able to import migrate_json_to_neo4j module."""
        from migrations.migrate_json_to_neo4j import read_json_state
        assert read_json_state is not None


class TestReadJsonState:
    """Test read_json_state function."""

    def test_read_json_state_reads_file(self, tmp_path):
        """read_json_state should read JSON file and return contents."""
        from migrations.migrate_json_to_neo4j import read_json_state
        
        # Create a test JSON file
        test_file = tmp_path / "test_state.json"
        test_data = {
            "version": "1.0",
            "knowledge": {
                "topics": {
                    "topic1": {"name": "topic1", "known": True},
                    "topic2": {"name": "topic2", "known": False}
                }
            }
        }
        test_file.write_text(json.dumps(test_data))
        
        result = read_json_state(str(test_file))
        
        assert result == test_data
        assert "knowledge" in result
        assert "topics" in result["knowledge"]

    def test_read_json_state_raises_on_invalid_json(self, tmp_path):
        """read_json_state should raise on invalid JSON."""
        from migrations.migrate_json_to_neo4j import read_json_state
        
        test_file = tmp_path / "invalid.json"
        test_file.write_text("not valid json")
        
        with pytest.raises(json.JSONDecodeError):
            read_json_state(str(test_file))

    def test_read_json_state_raises_on_missing_file(self):
        """read_json_state should raise on missing file."""
        from migrations.migrate_json_to_neo4j import read_json_state
        
        with pytest.raises(FileNotFoundError):
            read_json_state("/nonexistent/path/state.json")


class TestConvertToNeo4jNodes:
    """Test convert_to_neo4j_nodes function."""

    def test_convert_to_neo4j_nodes_converts_topics(self):
        """convert_to_neo4j_nodes should convert topics to node list."""
        from migrations.migrate_json_to_neo4j import convert_to_neo4j_nodes
        
        state = {
            "knowledge": {
                "topics": {
                    "topic1": {
                        "name": "topic1",
                        "known": True,
                        "status": "complete",
                        "summary": "Test summary 1"
                    },
                    "topic2": {
                        "name": "topic2",
                        "known": False,
                        "status": "pending",
                        "summary": "Test summary 2"
                    }
                }
            }
        }
        
        nodes = convert_to_neo4j_nodes(state)
        
        assert len(nodes) == 2
        assert nodes[0]["topic"] in ["topic1", "topic2"]
        assert nodes[1]["topic"] in ["topic1", "topic2"]
        
        # Check node structure
        for node in nodes:
            assert "topic" in node
            assert "content" in node
            assert "metadata" in node

    def test_convert_to_neo4j_nodes_handles_empty_topics(self):
        """convert_to_neo4j_nodes should handle empty topics dict."""
        from migrations.migrate_json_to_neo4j import convert_to_neo4j_nodes
        
        state = {
            "knowledge": {
                "topics": {}
            }
        }
        
        nodes = convert_to_neo4j_nodes(state)
        
        assert nodes == []

    def test_convert_to_neo4j_nodes_includes_metadata(self):
        """convert_to_neo4j_nodes should include metadata fields."""
        from migrations.migrate_json_to_neo4j import convert_to_neo4j_nodes
        
        state = {
            "knowledge": {
                "topics": {
                    "topic1": {
                        "name": "topic1",
                        "known": True,
                        "status": "complete",
                        "quality": 8.5,
                        "confidence": 0.9,
                        "summary": "Test content"
                    }
                }
            }
        }
        
        nodes = convert_to_neo4j_nodes(state)
        
        assert len(nodes) == 1
        metadata = nodes[0]["metadata"]
        assert metadata["status"] == "complete"
        assert metadata["quality"] == 8.5
        assert metadata["confidence"] == 0.9


class TestValidateMigration:
    """Test validate_migration function."""

    def test_validate_migration_returns_true_on_match(self):
        """validate_migration should return True when counts match."""
        from migrations.migrate_json_to_neo4j import validate_migration
        
        result = validate_migration(source_count=5, target_count=5)
        
        assert result is True

    def test_validate_migration_returns_false_on_mismatch(self):
        """validate_migration should return False when counts don't match."""
        from migrations.migrate_json_to_neo4j import validate_migration
        
        result = validate_migration(source_count=5, target_count=3)
        
        assert result is False

    def test_validate_migration_returns_false_on_zero_source(self):
        """validate_migration should return False when source is zero."""
        from migrations.migrate_json_to_neo4j import validate_migration
        
        result = validate_migration(source_count=0, target_count=0)
        
        assert result is False


class TestRunMigration:
    """Test run_migration function integration."""

    @pytest.mark.asyncio
    async def test_run_migration_orchestrates_full_flow(self):
        """run_migration should orchestrate the full migration process."""
        from migrations.migrate_json_to_neo4j import run_migration
        
        # Mock Neo4j client
        mock_client = AsyncMock()
        mock_client.is_connected.return_value = True
        mock_client.execute_write = AsyncMock(return_value=[{"created": True}])
        
        with patch('migrations.migrate_json_to_neo4j.read_json_state') as mock_read, \
             patch('migrations.migrate_json_to_neo4j.Neo4jClient') as mock_neo4j:
            
            # Setup mocks
            mock_read.return_value = {
                "knowledge": {
                    "topics": {
                        "topic1": {"name": "topic1", "known": True, "status": "complete"},
                        "topic2": {"name": "topic2", "known": False, "status": "pending"}
                    }
                }
            }
            mock_neo4j.return_value = mock_client
            
            result = await run_migration(
                json_path="/fake/path/state.json",
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="test"
            )
            
            assert result["success"] is True
            assert result["nodes_migrated"] == 2
            assert result["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_run_migration_handles_connection_failure(self):
        """run_migration should handle Neo4j connection failure."""
        from migrations.migrate_json_to_neo4j import run_migration
        
        with patch('migrations.migrate_json_to_neo4j.Neo4jClient') as mock_neo4j:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(side_effect=Exception("Connection failed"))
            mock_neo4j.return_value = mock_client
            
            result = await run_migration(
                json_path="/fake/path/state.json",
                neo4j_uri="bolt://localhost:7687",
                neo4j_user="neo4j",
                neo4j_password="test"
            )
            
            assert result["success"] is False
            assert "Connection failed" in result["error"]
