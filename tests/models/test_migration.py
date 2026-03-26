import pytest


class TestSchemaDetection:
    def test_detect_v1_schema(self):
        from core.models.migration import detect_schema_version
        
        v1_state = {
            "version": "1.0",
            "knowledge": {"topics": {}}
        }
        
        version = detect_schema_version(v1_state)
        assert version == "1.0"
    
    def test_detect_v2_schema(self):
        from core.models.migration import detect_schema_version
        
        v2_state = {
            "version": "1.0",
            "schema_version": "2.0",
            "knowledge": {"topics": {}}
        }
        
        version = detect_schema_version(v2_state)
        assert version == "2.0"


class TestMigrationV1ToV2:
    def test_migration_adds_schema_version(self):
        from core.models.migration import migrate_state_v1_to_v2
        
        v1_state = {
            "version": "1.0",
            "knowledge": {
                "topics": {
                    "topic1": {"name": "topic1", "known": True}
                }
            }
        }
        
        v2_state = migrate_state_v1_to_v2(v1_state)
        
        assert v2_state["schema_version"] == "2.0"
    
    def test_migration_adds_graph_fields(self):
        from core.models.migration import migrate_state_v1_to_v2
        
        v1_state = {
            "version": "1.0",
            "knowledge": {
                "topics": {
                    "topic1": {"name": "topic1", "known": True}
                }
            }
        }
        
        v2_state = migrate_state_v1_to_v2(v1_state)
        topic = v2_state["knowledge"]["topics"]["topic1"]
        
        assert "parents" in topic
        assert "relations" in topic
        assert "explored_by" in topic
        assert "fully_explored" in topic
    
    def test_migration_converts_single_parent(self):
        from core.models.migration import migrate_state_v1_to_v2
        
        v1_state = {
            "version": "1.0",
            "knowledge": {
                "topics": {
                    "child": {
                        "name": "child",
                        "parent": "parent_topic"
                    }
                }
            }
        }
        
        v2_state = migrate_state_v1_to_v2(v1_state)
        topic = v2_state["knowledge"]["topics"]["child"]
        
        assert topic["parents"] == ["parent_topic"]
        assert "parent" not in topic
