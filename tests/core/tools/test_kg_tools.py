"""Tests for KG Tools module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class MockKGRepository:
    """Mock KG Repository for testing."""
    
    def __init__(self):
        self._nodes = {}
        self._relations = []
    
    async def query_knowledge(self, topic, limit=10, include_relations=False):
        """Query knowledge nodes by topic."""
        results = []
        for key, node in self._nodes.items():
            if topic.lower() in key.lower():
                results.append(node)
                if len(results) >= limit:
                    break
        return results
    
    async def query_knowledge_by_status(self, status, limit=10):
        """Query nodes by status."""
        results = []
        for key, node in self._nodes.items():
            if node.get("status") == status:
                results.append(node)
                if len(results) >= limit:
                    break
        return results
    
    async def query_knowledge_by_heat(self, limit=10):
        """Query nodes sorted by heat."""
        sorted_nodes = sorted(
            self._nodes.values(),
            key=lambda x: x.get("heat", 0),
            reverse=True
        )
        return sorted_nodes[:limit]
    
    async def get_node_relations(self, topic):
        """Get relations for a topic."""
        return [r for r in self._relations if r.get("topic") == topic]
    
    async def add_to_knowledge_graph(self, topic, content="", source_urls=None, metadata=None, relations=None):
        """Add new knowledge node."""
        node = {
            "topic": topic,
            "content": content,
            "source_urls": source_urls or [],
            "metadata": metadata or {},
            "relations": relations or []
        }
        self._nodes[topic] = node
        return topic
    
    async def update_kg_status(self, topic, status):
        """Update node status."""
        if topic in self._nodes:
            self._nodes[topic]["status"] = status
            return True
        return False
    
    async def update_kg_metadata(self, topic, heat=None, quality=None, confidence=None):
        """Update node metadata."""
        if topic not in self._nodes:
            return False
        if heat is not None:
            self._nodes[topic]["heat"] = heat
        if quality is not None:
            self._nodes[topic]["quality"] = quality
        if confidence is not None:
            self._nodes[topic]["confidence"] = confidence
        return True
    
    async def update_kg_relation(self, from_topic, to_topic, relation_type="RELATED", action="add"):
        """Add/remove relation."""
        if action == "add":
            self._relations.append({
                "topic": from_topic,
                "related_topic": to_topic,
                "type": relation_type
            })
            return True
        elif action == "remove":
            self._relations = [
                r for r in self._relations
                if not (r.get("topic") == from_topic and r.get("related_topic") == to_topic)
            ]
            return True
        return False
    
    async def merge_kg_nodes(self, source_topics, target_topic):
        """Merge duplicate nodes."""
        if not source_topics or not target_topic:
            return False
        for source in source_topics:
            if source in self._nodes:
                del self._nodes[source]
        return True


class TestQueryKGTool:
    """Tests for query_kg tool."""
    
    @pytest.mark.asyncio
    async def test_query_kg_tool_exists(self):
        """Test that query_kg tool can be imported."""
        from core.tools.kg_tools import QueryKGTool
        tool = QueryKGTool()
        assert tool.name == "query_kg"
    
    @pytest.mark.asyncio
    async def test_query_kg_tool_description(self):
        """Test query_kg tool has proper description."""
        from core.tools.kg_tools import QueryKGTool
        tool = QueryKGTool()
        assert "query" in tool.description.lower()
    
    @pytest.mark.asyncio
    async def test_query_kg_tool_execute(self):
        """Test query_kg tool executes and calls repository."""
        from core.tools.kg_tools import QueryKGTool
        
        mock_repo = MockKGRepository()
        mock_repo._nodes = {
            "test_topic": {"topic": "test_topic", "content": "test content", "status": "done"}
        }
        
        tool = QueryKGTool(repository=mock_repo)
        result = await tool.execute(topic="test", limit=5)
        
        assert "test_topic" in result
    
    @pytest.mark.asyncio
    async def test_query_kg_tool_schema(self):
        """Test query_kg tool has valid schema."""
        from core.tools.kg_tools import QueryKGTool
        tool = QueryKGTool()
        schema = tool.to_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "query_kg"
        assert "topic" in str(schema["function"]["parameters"])


class TestQueryKGByStatusTool:
    """Tests for query_kg_by_status tool."""
    
    @pytest.mark.asyncio
    async def test_query_kg_by_status_tool_exists(self):
        """Test that query_kg_by_status tool can be imported."""
        from core.tools.kg_tools import QueryKGByStatusTool
        tool = QueryKGByStatusTool()
        assert tool.name == "query_kg_by_status"
    
    @pytest.mark.asyncio
    async def test_query_kg_by_status_tool_description(self):
        """Test query_kg_by_status tool has proper description."""
        from core.tools.kg_tools import QueryKGByStatusTool
        tool = QueryKGByStatusTool()
        assert "status" in tool.description.lower()
    
    @pytest.mark.asyncio
    async def test_query_kg_by_status_tool_execute(self):
        """Test query_kg_by_status tool executes and calls repository."""
        from core.tools.kg_tools import QueryKGByStatusTool
        
        mock_repo = MockKGRepository()
        mock_repo._nodes = {
            "pending_topic": {"topic": "pending_topic", "status": "pending"},
            "done_topic": {"topic": "done_topic", "status": "done"}
        }
        
        tool = QueryKGByStatusTool(repository=mock_repo)
        result = await tool.execute(status="pending")
        
        assert "pending_topic" in result
    
    @pytest.mark.asyncio
    async def test_query_kg_by_status_tool_schema(self):
        """Test query_kg_by_status tool has valid schema."""
        from core.tools.kg_tools import QueryKGByStatusTool
        tool = QueryKGByStatusTool()
        schema = tool.to_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "query_kg_by_status"
        assert "status" in str(schema["function"]["parameters"])


class TestQueryKGByHeatTool:
    """Tests for query_kg_by_heat tool."""
    
    @pytest.mark.asyncio
    async def test_query_kg_by_heat_tool_exists(self):
        """Test that query_kg_by_heat tool can be imported."""
        from core.tools.kg_tools import QueryKGByHeatTool
        tool = QueryKGByHeatTool()
        assert tool.name == "query_kg_by_heat"
    
    @pytest.mark.asyncio
    async def test_query_kg_by_heat_tool_description(self):
        """Test query_kg_by_heat tool has proper description."""
        from core.tools.kg_tools import QueryKGByHeatTool
        tool = QueryKGByHeatTool()
        assert "heat" in tool.description.lower()
    
    @pytest.mark.asyncio
    async def test_query_kg_by_heat_tool_execute(self):
        """Test query_kg_by_heat tool executes and calls repository."""
        from core.tools.kg_tools import QueryKGByHeatTool
        
        mock_repo = MockKGRepository()
        mock_repo._nodes = {
            "hot_topic": {"topic": "hot_topic", "heat": 100},
            "cold_topic": {"topic": "cold_topic", "heat": 10}
        }
        
        tool = QueryKGByHeatTool(repository=mock_repo)
        result = await tool.execute(limit=5)
        
        assert "hot_topic" in result
    
    @pytest.mark.asyncio
    async def test_query_kg_by_heat_tool_schema(self):
        """Test query_kg_by_heat tool has valid schema."""
        from core.tools.kg_tools import QueryKGByHeatTool
        tool = QueryKGByHeatTool()
        schema = tool.to_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "query_kg_by_heat"


class TestGetNodeRelationsTool:
    """Tests for get_node_relations tool."""
    
    @pytest.mark.asyncio
    async def test_get_node_relations_tool_exists(self):
        """Test that get_node_relations tool can be imported."""
        from core.tools.kg_tools import GetNodeRelationsTool
        tool = GetNodeRelationsTool()
        assert tool.name == "get_node_relations"
    
    @pytest.mark.asyncio
    async def test_get_node_relations_tool_description(self):
        """Test get_node_relations tool has proper description."""
        from core.tools.kg_tools import GetNodeRelationsTool
        tool = GetNodeRelationsTool()
        assert "relation" in tool.description.lower()
    
    @pytest.mark.asyncio
    async def test_get_node_relations_tool_execute(self):
        """Test get_node_relations tool executes and calls repository."""
        from core.tools.kg_tools import GetNodeRelationsTool
        
        mock_repo = MockKGRepository()
        mock_repo._relations = [
            {"topic": "test_topic", "related_topic": "related_topic", "type": "RELATED"}
        ]
        
        tool = GetNodeRelationsTool(repository=mock_repo)
        result = await tool.execute(topic="test_topic")
        
        assert "related_topic" in result
    
    @pytest.mark.asyncio
    async def test_get_node_relations_tool_schema(self):
        """Test get_node_relations tool has valid schema."""
        from core.tools.kg_tools import GetNodeRelationsTool
        tool = GetNodeRelationsTool()
        schema = tool.to_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "get_node_relations"
        assert "topic" in str(schema["function"]["parameters"])


class TestAddToKGTool:
    """Tests for add_to_kg tool."""
    
    @pytest.mark.asyncio
    async def test_add_to_kg_tool_exists(self):
        """Test that add_to_kg tool can be imported."""
        from core.tools.kg_tools import AddToKGTool
        tool = AddToKGTool()
        assert tool.name == "add_to_kg"
    
    @pytest.mark.asyncio
    async def test_add_to_kg_tool_description(self):
        """Test add_to_kg tool has proper description."""
        from core.tools.kg_tools import AddToKGTool
        tool = AddToKGTool()
        assert "add" in tool.description.lower()
    
    @pytest.mark.asyncio
    async def test_add_to_kg_tool_execute(self):
        """Test add_to_kg tool executes and calls repository."""
        from core.tools.kg_tools import AddToKGTool
        
        mock_repo = MockKGRepository()
        
        tool = AddToKGTool(repository=mock_repo)
        result = await tool.execute(
            topic="new_topic",
            content="new content",
            metadata={"heat": 50}
        )
        
        assert "new_topic" in result
    
    @pytest.mark.asyncio
    async def test_add_to_kg_tool_schema(self):
        """Test add_to_kg tool has valid schema."""
        from core.tools.kg_tools import AddToKGTool
        tool = AddToKGTool()
        schema = tool.to_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "add_to_kg"
        assert "topic" in str(schema["function"]["parameters"])
    
    @pytest.mark.asyncio
    async def test_add_to_kg_tool_6_element_fields(self):
        """Test add_to_kg tool accepts 6-element fields."""
        from core.tools.kg_tools import AddToKGTool
        
        mock_repo = MockKGRepository()
        
        tool = AddToKGTool(repository=mock_repo)
        result = await tool.execute(
            topic="knowledge_point",
            definition="A definition of the concept",
            core="The core mechanism",
            context="Background context",
            examples=["example1", "example2"],
            formula="E = mc^2",
            parent_topic="parent_summary"
        )
        
        assert "knowledge_point" in result
        assert "completeness: 5/5" in result
        node = mock_repo._nodes["knowledge_point"]
        assert node["metadata"]["definition"] == "A definition of the concept"
        assert node["metadata"]["core"] == "The core mechanism"
        assert node["metadata"]["context"] == "Background context"
        assert node["metadata"]["examples"] == ["example1", "example2"]
        assert node["metadata"]["formula"] == "E = mc^2"
        assert node["metadata"]["parent_topic"] == "parent_summary"
        assert node["metadata"]["completeness_score"] == 5
    
    @pytest.mark.asyncio
    async def test_add_to_kg_tool_completeness_score_partial(self):
        """Test completeness score with partial 6-element fields."""
        from core.tools.kg_tools import AddToKGTool
        
        mock_repo = MockKGRepository()
        
        tool = AddToKGTool(repository=mock_repo)
        result = await tool.execute(
            topic="partial_knowledge",
            definition="Only definition",
            core="Only core"
        )
        
        assert "completeness: 2/5" in result
        node = mock_repo._nodes["partial_knowledge"]
        assert node["metadata"]["completeness_score"] == 2
    
    @pytest.mark.asyncio
    async def test_add_to_kg_tool_completeness_score_zero(self):
        """Test completeness score with no 6-element fields."""
        from core.tools.kg_tools import AddToKGTool
        
        mock_repo = MockKGRepository()
        
        tool = AddToKGTool(repository=mock_repo)
        result = await tool.execute(
            topic="no_elements",
            content="Just content"
        )
        
        assert "completeness: 0/5" in result
        node = mock_repo._nodes["no_elements"]
        assert node["metadata"]["completeness_score"] == 0
    
    @pytest.mark.asyncio
    async def test_add_to_kg_tool_schema_has_6_element_params(self):
        """Test schema includes 6-element field parameters."""
        from core.tools.kg_tools import AddToKGTool
        tool = AddToKGTool()
        schema = tool.to_schema()
        
        params = schema["function"]["parameters"]["properties"]
        assert "definition" in params
        assert "core" in params
        assert "context" in params
        assert "examples" in params
        assert "formula" in params
        assert "parent_topic" in params
    
    @pytest.mark.asyncio
    async def test_add_to_kg_tool_without_repository(self):
        """Test add_to_kg tool works without repository."""
        from core.tools.kg_tools import AddToKGTool
        
        tool = AddToKGTool()
        result = await tool.execute(
            topic="test_topic",
            definition="test definition",
            core="test core"
        )
        
        assert "Node added: test_topic" in result
        assert "completeness: 2/5" in result


class TestUpdateKGStatusTool:
    """Tests for update_kg_status tool."""
    
    @pytest.mark.asyncio
    async def test_update_kg_status_tool_exists(self):
        """Test that update_kg_status tool can be imported."""
        from core.tools.kg_tools import UpdateKGStatusTool
        tool = UpdateKGStatusTool()
        assert tool.name == "update_kg_status"
    
    @pytest.mark.asyncio
    async def test_update_kg_status_tool_description(self):
        """Test update_kg_status tool has proper description."""
        from core.tools.kg_tools import UpdateKGStatusTool
        tool = UpdateKGStatusTool()
        assert "status" in tool.description.lower()
    
    @pytest.mark.asyncio
    async def test_update_kg_status_tool_execute(self):
        """Test update_kg_status tool executes and calls repository."""
        from core.tools.kg_tools import UpdateKGStatusTool
        
        mock_repo = MockKGRepository()
        mock_repo._nodes = {"existing_topic": {"topic": "existing_topic", "status": "pending"}}
        
        tool = UpdateKGStatusTool(repository=mock_repo)
        result = await tool.execute(topic="existing_topic", status="done")
        
        assert "updated" in result.lower() or "existing_topic" in result
    
    @pytest.mark.asyncio
    async def test_update_kg_status_tool_schema(self):
        """Test update_kg_status tool has valid schema."""
        from core.tools.kg_tools import UpdateKGStatusTool
        tool = UpdateKGStatusTool()
        schema = tool.to_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "update_kg_status"
        assert "status" in str(schema["function"]["parameters"])


class TestUpdateKGMetadataTool:
    """Tests for update_kg_metadata tool."""
    
    @pytest.mark.asyncio
    async def test_update_kg_metadata_tool_exists(self):
        """Test that update_kg_metadata tool can be imported."""
        from core.tools.kg_tools import UpdateKGMetadataTool
        tool = UpdateKGMetadataTool()
        assert tool.name == "update_kg_metadata"
    
    @pytest.mark.asyncio
    async def test_update_kg_metadata_tool_description(self):
        """Test update_kg_metadata tool has proper description."""
        from core.tools.kg_tools import UpdateKGMetadataTool
        tool = UpdateKGMetadataTool()
        assert "metadata" in tool.description.lower()
    
    @pytest.mark.asyncio
    async def test_update_kg_metadata_tool_execute(self):
        """Test update_kg_metadata tool executes and calls repository."""
        from core.tools.kg_tools import UpdateKGMetadataTool
        
        mock_repo = MockKGRepository()
        mock_repo._nodes = {"existing_topic": {"topic": "existing_topic", "heat": 0}}
        
        tool = UpdateKGMetadataTool(repository=mock_repo)
        result = await tool.execute(topic="existing_topic", heat=100, quality=0.9)
        
        assert "updated" in result.lower() or "existing_topic" in result
    
    @pytest.mark.asyncio
    async def test_update_kg_metadata_tool_schema(self):
        """Test update_kg_metadata tool has valid schema."""
        from core.tools.kg_tools import UpdateKGMetadataTool
        tool = UpdateKGMetadataTool()
        schema = tool.to_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "update_kg_metadata"
        assert "heat" in str(schema["function"]["parameters"]) or "metadata" in str(schema["function"]["parameters"])


class TestUpdateKGRelationTool:
    """Tests for update_kg_relation tool."""
    
    @pytest.mark.asyncio
    async def test_update_kg_relation_tool_exists(self):
        """Test that update_kg_relation tool can be imported."""
        from core.tools.kg_tools import UpdateKGRelationTool
        tool = UpdateKGRelationTool()
        assert tool.name == "update_kg_relation"
    
    @pytest.mark.asyncio
    async def test_update_kg_relation_tool_description(self):
        """Test update_kg_relation tool has proper description."""
        from core.tools.kg_tools import UpdateKGRelationTool
        tool = UpdateKGRelationTool()
        assert "relation" in tool.description.lower()
    
    @pytest.mark.asyncio
    async def test_update_kg_relation_tool_execute_add(self):
        """Test update_kg_relation tool executes add action."""
        from core.tools.kg_tools import UpdateKGRelationTool
        
        mock_repo = MockKGRepository()
        
        tool = UpdateKGRelationTool(repository=mock_repo)
        result = await tool.execute(
            from_topic="topic_a",
            to_topic="topic_b",
            relation_type="RELATED",
            action="add"
        )
        
        assert "added" in result.lower() or "relation" in result.lower()
    
    @pytest.mark.asyncio
    async def test_update_kg_relation_tool_execute_remove(self):
        """Test update_kg_relation tool executes remove action."""
        from core.tools.kg_tools import UpdateKGRelationTool
        
        mock_repo = MockKGRepository()
        mock_repo._relations = [
            {"topic": "topic_a", "related_topic": "topic_b", "type": "RELATED"}
        ]
        
        tool = UpdateKGRelationTool(repository=mock_repo)
        result = await tool.execute(
            from_topic="topic_a",
            to_topic="topic_b",
            action="remove"
        )
        
        assert "removed" in result.lower() or "relation" in result.lower()
    
    @pytest.mark.asyncio
    async def test_update_kg_relation_tool_schema(self):
        """Test update_kg_relation tool has valid schema."""
        from core.tools.kg_tools import UpdateKGRelationTool
        tool = UpdateKGRelationTool()
        schema = tool.to_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "update_kg_relation"
        assert "relation" in str(schema["function"]["parameters"])


class TestMergeKGNodesTool:
    """Tests for merge_kg_nodes tool."""
    
    @pytest.mark.asyncio
    async def test_merge_kg_nodes_tool_exists(self):
        """Test that merge_kg_nodes tool can be imported."""
        from core.tools.kg_tools import MergeKGNodesTool
        tool = MergeKGNodesTool()
        assert tool.name == "merge_kg_nodes"
    
    @pytest.mark.asyncio
    async def test_merge_kg_nodes_tool_description(self):
        """Test merge_kg_nodes tool has proper description."""
        from core.tools.kg_tools import MergeKGNodesTool
        tool = MergeKGNodesTool()
        assert "merge" in tool.description.lower()
    
    @pytest.mark.asyncio
    async def test_merge_kg_nodes_tool_execute(self):
        """Test merge_kg_nodes tool executes and calls repository."""
        from core.tools.kg_tools import MergeKGNodesTool
        
        mock_repo = MockKGRepository()
        mock_repo._nodes = {
            "duplicate_a": {"topic": "duplicate_a"},
            "duplicate_b": {"topic": "duplicate_b"},
            "target": {"topic": "target"}
        }
        
        tool = MergeKGNodesTool(repository=mock_repo)
        result = await tool.execute(
            source_topics=["duplicate_a", "duplicate_b"],
            target_topic="target"
        )
        
        assert "merged" in result.lower() or "target" in result
    
    @pytest.mark.asyncio
    async def test_merge_kg_nodes_tool_schema(self):
        """Test merge_kg_nodes tool has valid schema."""
        from core.tools.kg_tools import MergeKGNodesTool
        tool = MergeKGNodesTool()
        schema = tool.to_schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "merge_kg_nodes"
        assert "source" in str(schema["function"]["parameters"]) or "topic" in str(schema["function"]["parameters"])


class TestKGToolsIntegration:
    """Integration tests for KG Tools."""
    
    @pytest.mark.asyncio
    async def test_all_kg_tools_importable(self):
        """Test that all 9 KG tools can be imported."""
        from core.tools.kg_tools import (
            QueryKGTool,
            QueryKGByStatusTool,
            QueryKGByHeatTool,
            GetNodeRelationsTool,
            AddToKGTool,
            UpdateKGStatusTool,
            UpdateKGMetadataTool,
            UpdateKGRelationTool,
            MergeKGNodesTool
        )
        
        tools = [
            QueryKGTool(),
            QueryKGByStatusTool(),
            QueryKGByHeatTool(),
            GetNodeRelationsTool(),
            AddToKGTool(),
            UpdateKGStatusTool(),
            UpdateKGMetadataTool(),
            UpdateKGRelationTool(),
            MergeKGNodesTool()
        ]
        
        assert len(tools) == 9
    
    @pytest.mark.asyncio
    async def test_all_tools_inherit_from_base(self):
        """Test that all KG tools inherit from Tool base class."""
        from core.tools.base import Tool
        from core.tools.kg_tools import (
            QueryKGTool,
            QueryKGByStatusTool,
            QueryKGByHeatTool,
            GetNodeRelationsTool,
            AddToKGTool,
            UpdateKGStatusTool,
            UpdateKGMetadataTool,
            UpdateKGRelationTool,
            MergeKGNodesTool
        )
        
        tools = [
            QueryKGTool(),
            QueryKGByStatusTool(),
            QueryKGByHeatTool(),
            GetNodeRelationsTool(),
            AddToKGTool(),
            UpdateKGStatusTool(),
            UpdateKGMetadataTool(),
            UpdateKGRelationTool(),
            MergeKGNodesTool()
        ]
        
        for tool in tools:
            assert isinstance(tool, Tool)
    
    @pytest.mark.asyncio
    async def test_all_tools_have_required_properties(self):
        """Test that all KG tools have name, description, parameters."""
        from core.tools.kg_tools import (
            QueryKGTool,
            QueryKGByStatusTool,
            QueryKGByHeatTool,
            GetNodeRelationsTool,
            AddToKGTool,
            UpdateKGStatusTool,
            UpdateKGMetadataTool,
            UpdateKGRelationTool,
            MergeKGNodesTool
        )
        
        tools = [
            QueryKGTool(),
            QueryKGByStatusTool(),
            QueryKGByHeatTool(),
            GetNodeRelationsTool(),
            AddToKGTool(),
            UpdateKGStatusTool(),
            UpdateKGMetadataTool(),
            UpdateKGRelationTool(),
            MergeKGNodesTool()
        ]
        
        for tool in tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "parameters")
            assert callable(tool.execute)
            assert callable(tool.to_schema)
