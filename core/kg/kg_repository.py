"""KG Repository for knowledge graph operations."""
from typing import Any, Dict, List, Optional


class KGRepository:
    """Repository for Knowledge Graph node and relation operations."""

    def __init__(self, neo4j_client: Any):
        self._client = neo4j_client

    async def create_knowledge_node(
        self,
        topic: str,
        content: str = "",
        source_urls: List[str] = None,
        relations: List[Dict[str, str]] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a knowledge node with optional relations."""
        source_urls = source_urls or []
        relations = relations or []
        metadata = metadata or {}

        default_metadata = {
            "heat": 0,
            "quality": 0.0,
            "confidence": 0.0,
            "status": "pending",
            "depth": 5
        }
        for key, value in default_metadata.items():
            if key not in metadata:
                metadata[key] = value

        query = """
        MERGE (n:Knowledge {topic: $topic})
        SET n.content = $content,
            n.source_urls = $source_urls,
            n.heat = $heat,
            n.quality = $quality,
            n.confidence = $confidence,
            n.status = $status,
            n.depth = $depth,
            n.created_at = timestamp()
        RETURN n.topic as id, n.status as status
        """

        result = await self._client.execute_write(
            query,
            topic=topic,
            content=content,
            source_urls=source_urls,
            heat=metadata.get("heat", 0),
            quality=metadata.get("quality", 0.0),
            confidence=metadata.get("confidence", 0.0),
            status=metadata.get("status", "pending"),
            depth=metadata.get("depth", 5)
        )

        for rel in relations:
            await self.add_relation(
                rel.get("parent", ""),
                topic,
                rel.get("type", "IS_CHILD_OF")
            )

        if result:
            return result[0].get("id", topic)
        return topic

    async def query_knowledge(
        self,
        topic: str,
        limit: int = 10,
        include_relations: bool = False
    ) -> List[Dict[str, Any]]:
        """Query knowledge nodes by topic."""
        query = """
        MATCH (n:Knowledge)
        WHERE n.topic CONTAINS $topic OR $topic CONTAINS n.topic
        RETURN n.topic as topic, n.content as content, n.status as status,
               n.heat as heat, n.quality as quality, n.confidence as confidence
        LIMIT $limit
        """

        result = await self._client.execute_query(
            query,
            topic=topic,
            limit=limit
        )
        return result

    async def get_node(self, topic: str) -> Optional[Dict[str, Any]]:
        """Get a single node by exact topic match."""
        query = """
        MATCH (n:Knowledge {topic: $topic})
        RETURN n.topic as topic, n.content as content, n.status as status,
               n.heat as heat, n.quality as quality, n.confidence as confidence,
               n.depth as depth, n.source_urls as source_urls
        """

        result = await self._client.execute_query(query, topic=topic)
        if result:
            return result[0]
        return None

    async def update_status(self, topic: str, status: str) -> bool:
        """Update node status."""
        query = """
        MATCH (n:Knowledge {topic: $topic})
        SET n.status = $status, n.updated_at = timestamp()
        RETURN n.status as status
        """

        result = await self._client.execute_write(query, topic=topic, status=status)
        return len(result) > 0

    async def update_metadata(
        self,
        topic: str,
        heat: Optional[int] = None,
        quality: Optional[float] = None,
        confidence: Optional[float] = None,
        depth: Optional[float] = None
    ) -> bool:
        """Update node metadata fields."""
        updates = []
        params = {"topic": topic}

        if heat is not None:
            updates.append("n.heat = $heat")
            params["heat"] = heat
        if quality is not None:
            updates.append("n.quality = $quality")
            params["quality"] = quality
        if confidence is not None:
            updates.append("n.confidence = $confidence")
            params["confidence"] = confidence
        if depth is not None:
            updates.append("n.depth = $depth")
            params["depth"] = depth

        if not updates:
            return False

        updates.append("n.updated_at = timestamp()")
        query = f"""
        MATCH (n:Knowledge {{topic: $topic}})
        SET {', '.join(updates)}
        RETURN n.heat as heat, n.quality as quality, n.confidence as confidence, n.depth as depth
        """

        result = await self._client.execute_write(**params, query=query)
        return len(result) > 0

    async def get_relations(self, topic: str) -> List[Dict[str, str]]:
        """Get all relations for a topic."""
        query = """
        MATCH (n:Knowledge {topic: $topic})-[r]-(m:Knowledge)
        RETURN 
            CASE WHEN startNode(r) = n THEN m.topic ELSE n.topic END as related_topic,
            type(r) as relation_type,
            CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END as direction
        """

        result = await self._client.execute_query(query, topic=topic)
        return result

    async def add_relation(
        self,
        from_topic: str,
        to_topic: str,
        relation_type: str = "IS_CHILD_OF"
    ) -> bool:
        """Create a relation between two topics."""
        query = """
        MATCH (a:Knowledge {topic: $from_topic})
        MATCH (b:Knowledge {topic: $to_topic})
        MERGE (a)-[r:%s]->(b)
        RETURN created(r) as created
        """ % relation_type

        result = await self._client.execute_write(
            query,
            from_topic=from_topic,
            to_topic=to_topic
        )
        return len(result) > 0

    async def mark_dormant(self, topic: str) -> bool:
        """Mark a node as dormant."""
        return await self.update_status(topic, "dormant")

    async def reactivate(self, topic: str) -> bool:
        """Reactivate a dormant node."""
        return await self.update_status(topic, "pending")

    async def merge_nodes(self, node_ids: List[str], target_topic: str = None) -> bool:
        """Merge multiple nodes into one."""
        if not node_ids:
            return False

        target = target_topic or node_ids[0]
        others = [n for n in node_ids if n != target]

        if not others:
            return True

        query = """
        MATCH (target:Knowledge {topic: $target})
        MATCH (other:Knowledge)
        WHERE other.topic IN $others
        WITH target, other
        SET target.quality = CASE 
            WHEN target.quality > other.quality THEN target.quality 
            ELSE other.quality 
        END
        WITH target, other
        OPTIONAL MATCH (other)-[r]->(m)
        WITH target, other, collect(r) as relations
        FOREACH (rel IN relations | MERGE (target)-[type(rel)]->(endNode(rel)))
        DETACH DELETE other
        RETURN count(other) as merged_count
        """

        result = await self._client.execute_write(
            query,
            target=target,
            others=others
        )
        return len(result) > 0

    async def get_children(self, topic: str) -> List[str]:
        """Get all child topics."""
        query = """
        MATCH (parent:Knowledge {topic: $topic})-[:IS_CHILD_OF]->(child:Knowledge)
        RETURN child.topic as topic
        """

        result = await self._client.execute_query(query, topic=topic)
        return [r["topic"] for r in result]

    async def get_parents(self, topic: str) -> List[str]:
        """Get all parent topics."""
        query = """
        MATCH (child:Knowledge {topic: $topic})<-[:IS_CHILD_OF]-(parent:Knowledge)
        RETURN parent.topic as topic
        """

        result = await self._client.execute_query(query, topic=topic)
        return [r["topic"] for r in result]

    async def get_pending_topics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending topics sorted by priority."""
        query = """
        MATCH (n:Knowledge {status: 'pending'})
        RETURN n.topic as topic, n.heat as heat, n.quality as quality
        ORDER BY n.heat DESC, n.quality DESC
        LIMIT $limit
        """

        result = await self._client.execute_query(limit=limit, query=query)
        return result