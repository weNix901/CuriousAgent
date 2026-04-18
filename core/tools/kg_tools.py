"""KG Tools for Knowledge Graph operations."""
from typing import Any
from core.tools.base import Tool


class QueryKGTool(Tool):
    """Query knowledge nodes by topic."""
    
    def __init__(self, repository: Any = None):
        self._repository = repository
    
    @property
    def name(self) -> str:
        return "query_kg"
    
    @property
    def description(self) -> str:
        return "Query knowledge graph nodes by topic keyword"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to search for"},
                "limit": {"type": "integer", "description": "Maximum results to return", "default": 10},
                "include_relations": {"type": "boolean", "description": "Include relations in results", "default": False}
            },
            "required": ["topic"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic", "")
        limit = kwargs.get("limit", 10)
        include_relations = kwargs.get("include_relations", False)
        
        if self._repository:
            results = await self._repository.query_knowledge(
                topic=topic,
                limit=limit,
                include_relations=include_relations
            )
            return str(results)
        return f"Query executed for topic: {topic}"
    
    def to_schema(self) -> dict[str, Any]:
        return super().to_schema()


class QueryKGByStatusTool(Tool):
    """Query knowledge nodes by status."""
    
    def __init__(self, repository: Any = None):
        self._repository = repository
    
    @property
    def name(self) -> str:
        return "query_kg_by_status"
    
    @property
    def description(self) -> str:
        return "Query knowledge graph nodes by status (pending/done/dormant)"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Status to filter by (pending/done/dormant)"},
                "limit": {"type": "integer", "description": "Maximum results to return", "default": 10}
            },
            "required": ["status"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        status = kwargs.get("status", "")
        limit = kwargs.get("limit", 10)
        
        if self._repository:
            results = await self._repository.query_knowledge_by_status(
                status=status,
                limit=limit
            )
            return str(results)
        return f"Query executed for status: {status}"
    
    def to_schema(self) -> dict[str, Any]:
        return super().to_schema()


class QueryKGByHeatTool(Tool):
    """Query knowledge nodes sorted by heat."""
    
    def __init__(self, repository: Any = None):
        self._repository = repository
    
    @property
    def name(self) -> str:
        return "query_kg_by_heat"
    
    @property
    def description(self) -> str:
        return "Query knowledge graph nodes sorted by heat (popularity)"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum results to return", "default": 10}
            }
        }
    
    async def execute(self, **kwargs: Any) -> str:
        limit = kwargs.get("limit", 10)
        
        if self._repository:
            results = await self._repository.query_knowledge_by_heat(limit=limit)
            return str(results)
        return f"Query executed for top {limit} hot topics"
    
    def to_schema(self) -> dict[str, Any]:
        return super().to_schema()


class GetNodeRelationsTool(Tool):
    """Get relations for a knowledge node."""
    
    def __init__(self, repository: Any = None):
        self._repository = repository
    
    @property
    def name(self) -> str:
        return "get_node_relations"
    
    @property
    def description(self) -> str:
        return "Get all relations for a specific knowledge node"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to get relations for"}
            },
            "required": ["topic"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic", "")
        
        if self._repository:
            relations = await self._repository.get_node_relations(topic=topic)
            return str(relations)
        return f"Relations retrieved for topic: {topic}"
    
    def to_schema(self) -> dict[str, Any]:
        return super().to_schema()


class AddToKGTool(Tool):
    """Add a new knowledge node to the graph."""
    
    def __init__(self, repository: Any = None):
        self._repository = repository
    
    @property
    def name(self) -> str:
        return "add_to_kg"
    
    @property
    def description(self) -> str:
        return "Add a new knowledge node to the knowledge graph"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic name for the new node"},
                "content": {"type": "string", "description": "Knowledge summary content", "default": ""},
                "source_urls": {"type": "array", "description": "List of source URLs for attribution", "default": []},
                "metadata": {"type": "object", "description": "Metadata (depth, quality, confidence)", "default": {}},
                "relations": {"type": "array", "description": "Relations to other nodes", "default": []}
            },
            "required": ["topic"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic", "")
        content = kwargs.get("content", "")
        source_urls = kwargs.get("source_urls", [])
        metadata = kwargs.get("metadata", {})
        relations = kwargs.get("relations", [])
        
        if self._repository:
            result = await self._repository.add_to_knowledge_graph(
                topic=topic,
                content=content,
                source_urls=source_urls,
                metadata=metadata,
                relations=relations
            )
            return f"Added node with {len(source_urls)} sources: {result}"
        return f"Node added: {topic}"
    
    def to_schema(self) -> dict[str, Any]:
        return super().to_schema()


class UpdateKGStatusTool(Tool):
    """Update the status of a knowledge node."""
    
    def __init__(self, repository: Any = None):
        self._repository = repository
    
    @property
    def name(self) -> str:
        return "update_kg_status"
    
    @property
    def description(self) -> str:
        return "Update the status of a knowledge node (pending/done/dormant)"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to update"},
                "status": {"type": "string", "description": "New status (pending/done/dormant)"}
            },
            "required": ["topic", "status"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic", "")
        status = kwargs.get("status", "")
        
        if self._repository:
            success = await self._repository.update_kg_status(
                topic=topic,
                status=status
            )
            if success:
                return f"Updated status for {topic} to {status}"
            return f"Failed to update status for {topic}"
        return f"Status updated for {topic}: {status}"
    
    def to_schema(self) -> dict[str, Any]:
        return super().to_schema()


class UpdateKGMetadataTool(Tool):
    """Update metadata of a knowledge node."""
    
    def __init__(self, repository: Any = None):
        self._repository = repository
    
    @property
    def name(self) -> str:
        return "update_kg_metadata"
    
    @property
    def description(self) -> str:
        return "Update metadata (heat/quality/confidence) of a knowledge node"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to update"},
                "heat": {"type": "integer", "description": "Heat value", "default": None},
                "quality": {"type": "number", "description": "Quality score (0-1)", "default": None},
                "confidence": {"type": "number", "description": "Confidence score (0-1)", "default": None}
            },
            "required": ["topic"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        topic = kwargs.get("topic", "")
        heat = kwargs.get("heat")
        quality = kwargs.get("quality")
        confidence = kwargs.get("confidence")
        
        if self._repository:
            success = await self._repository.update_kg_metadata(
                topic=topic,
                heat=heat,
                quality=quality,
                confidence=confidence
            )
            if success:
                return f"Updated metadata for {topic}"
            return f"Failed to update metadata for {topic}"
        return f"Metadata updated for {topic}"
    
    def to_schema(self) -> dict[str, Any]:
        return super().to_schema()


class UpdateKGRelationTool(Tool):
    """Add or remove relations between knowledge nodes."""
    
    def __init__(self, repository: Any = None):
        self._repository = repository
    
    @property
    def name(self) -> str:
        return "update_kg_relation"
    
    @property
    def description(self) -> str:
        return "Add or remove a relation between two knowledge nodes"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "from_topic": {"type": "string", "description": "Source topic"},
                "to_topic": {"type": "string", "description": "Target topic"},
                "relation_type": {"type": "string", "description": "Type of relation", "default": "RELATED"},
                "action": {"type": "string", "description": "Action to perform (add/remove)", "default": "add"}
            },
            "required": ["from_topic", "to_topic"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        from_topic = kwargs.get("from_topic", "")
        to_topic = kwargs.get("to_topic", "")
        relation_type = kwargs.get("relation_type", "RELATED")
        action = kwargs.get("action", "add")
        
        if self._repository:
            success = await self._repository.update_kg_relation(
                from_topic=from_topic,
                to_topic=to_topic,
                relation_type=relation_type,
                action=action
            )
            if success:
                return f"{action.capitalize()} relation between {from_topic} and {to_topic}"
            return f"Failed to {action} relation"
        return f"Relation {action}ed between {from_topic} and {to_topic}"
    
    def to_schema(self) -> dict[str, Any]:
        return super().to_schema()


class MergeKGNodesTool(Tool):
    """Merge duplicate knowledge nodes."""
    
    def __init__(self, repository: Any = None):
        self._repository = repository
    
    @property
    def name(self) -> str:
        return "merge_kg_nodes"
    
    @property
    def description(self) -> str:
        return "Merge duplicate knowledge nodes into a single target node"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_topics": {"type": "array", "items": {"type": "string"}, "description": "Topics to merge"},
                "target_topic": {"type": "string", "description": "Target topic to merge into"}
            },
            "required": ["source_topics", "target_topic"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        source_topics = kwargs.get("source_topics", [])
        target_topic = kwargs.get("target_topic", "")
        
        if self._repository:
            success = await self._repository.merge_kg_nodes(
                source_topics=source_topics,
                target_topic=target_topic
            )
            if success:
                return f"Merged {len(source_topics)} nodes into {target_topic}"
            return "Failed to merge nodes"
        return f"Merged {source_topics} into {target_topic}"
    
    def to_schema(self) -> dict[str, Any]:
        return super().to_schema()


__all__ = [
    "QueryKGTool",
    "QueryKGByStatusTool",
    "QueryKGByHeatTool",
    "GetNodeRelationsTool",
    "AddToKGTool",
    "UpdateKGStatusTool",
    "UpdateKGMetadataTool",
    "UpdateKGRelationTool",
    "MergeKGNodesTool"
]
