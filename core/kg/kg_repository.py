"""KG Repository for knowledge graph operations."""
import logging
from typing import Any, Dict, List, Optional
from core.kg.knowledge_node import KnowledgeNode

logger = logging.getLogger(__name__)


class KGRepository:
    """Repository for Knowledge Graph node and relation operations."""

    def __init__(self, neo4j_client: Any, embedding_service: Optional[Any] = None):
        self._client = neo4j_client
        self._embedding_service = embedding_service

    def _build_combined_text(
        self,
        topic: str,
        content: str,
        key_points: List[str],
        keywords: List[str]
    ) -> str:
        """Build combined text for embedding generation.
        
        Format: 【主题】topic 【关键要点】... 【简介】content 【关键词】...
        """
        key_points_str = ", ".join(key_points) if key_points else ""
        keywords_str = ", ".join(keywords) if keywords else ""
        
        return f"【主题】{topic} 【关键要点】{key_points_str} 【简介】{content} 【关键词】{keywords_str}"

    async def create_knowledge_node(
        self,
        topic: str,
        content: str = "",
        source_urls: List[str] = None,
        relations: List[Dict[str, str]] = None,
        metadata: Dict[str, Any] = None,
        key_points: List[str] = None,
        keywords: List[str] = None
    ) -> str:
        """Create a knowledge node with optional relations and embedding."""
        source_urls = source_urls or []
        relations = relations or []
        metadata = metadata or {}
        key_points = key_points or []
        keywords = keywords or []

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

        embedding = None
        if self._embedding_service is not None:
            try:
                combined_text = self._build_combined_text(topic, content, key_points, keywords)
                embedding = self._embedding_service.embed([combined_text])[0]
            except Exception as e:
                logger.warning(f"Failed to generate embedding for {topic}: {e}")

        query = """
        MERGE (n:Knowledge {topic: $topic})
        SET n.content = $content,
            n.source_urls = $source_urls,
            n.key_points = $key_points,
            n.keywords = $keywords,
            n.heat = $heat,
            n.quality = $quality,
            n.confidence = $confidence,
            n.status = $status,
            n.depth = $depth,
            n.created_at = timestamp(),
            n.definition = $definition,
            n.core = $core,
            n.context = $context,
            n.formula = $formula,
            n.fact = $fact,
            n.examples = $examples,
            n.completeness_score = $completeness_score,
            n.source_url = $source_url,
            n.source_type = $source_type,
            n.source_trusted = $source_trusted,
            n.local_file_path = $local_file_path,
            n.extracted_text_path = $extracted_text_path,
            n.source_missing = $source_missing,
            n.parent_topic = $parent_topic,
            n.deep_read_status = $deep_read_status
        """
        
        if embedding is not None:
            query += "SET n.embedding = $embedding\n"

        query += "RETURN n.topic as id, n.status as status"

        params = {
            "topic": topic,
            "content": content,
            "source_urls": source_urls,
            "key_points": key_points,
            "keywords": keywords,
            "heat": metadata.get("heat", 0),
            "quality": metadata.get("quality", 0.0),
            "confidence": metadata.get("confidence", 0.0),
            "status": metadata.get("status", "pending"),
            "depth": metadata.get("depth", 5),
            "definition": metadata.get("definition"),
            "core": metadata.get("core"),
            "context": metadata.get("context"),
            "formula": metadata.get("formula"),
            "fact": metadata.get("fact"),
            "examples": metadata.get("examples", []),
            "completeness_score": metadata.get("completeness_score", 1),
            "source_url": metadata.get("source_url"),
            "source_type": metadata.get("source_type", "web"),
            "source_trusted": metadata.get("source_trusted", False),
            "local_file_path": metadata.get("local_file_path"),
            "extracted_text_path": metadata.get("extracted_text_path"),
            "source_missing": metadata.get("source_missing", False),
            "parent_topic": metadata.get("parent_topic"),
            "deep_read_status": metadata.get("deep_read_status", "pending"),
        }
        
        if embedding is not None:
            params["embedding"] = embedding

        result = await self._client.execute_write(query, **params)

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

    async def query_knowledge_semantic(
        self,
        query_text: str,
        top_k: int = 5,
        threshold: float = 0.75,
        status_filter: str = "done"
    ) -> List[Dict[str, Any]]:
        """Query knowledge nodes using vector similarity search.
        
        Uses the vector index to find semantically similar nodes.
        Falls back to text search if embedding_service is not available.
        
        Args:
            query_text: The search query text
            top_k: Number of results to return (default: 5)
            threshold: Minimum similarity score threshold (default: 0.75)
            status_filter: Filter by node status (default: "done")
            
        Returns:
            List of matching nodes with topic, content, and score
        """
        # Fallback to text search if no embedding service
        if self._embedding_service is None:
            logger.warning("No embedding service available, falling back to text search")
            return await self.query_knowledge(query_text, limit=top_k)
        
        try:
            # Generate query embedding
            query_embedding = self._embedding_service.embed([query_text])[0]
            
            # Query vector index using db.index.vector.queryNodes
            query = """
            CALL db.index.vector.queryNodes('knowledge_embeddings', $top_k, $embedding)
            YIELD node, score
            WHERE node.status = $status AND score >= $threshold
            RETURN node.topic as topic, node.content as content, 
                   node.heat as heat, node.quality as quality, 
                   node.confidence as confidence, score
            ORDER BY score DESC
            """
            
            result = await self._client.execute_query(
                query,
                top_k=top_k,
                embedding=query_embedding,
                threshold=threshold,
                status=status_filter
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Semantic query failed: {e}")
            # Fallback to text search on error
            logger.warning("Falling back to text search due to error")
            return await self.query_knowledge(query_text, limit=top_k)

    async def get_node(self, topic: str) -> Optional[Dict[str, Any]]:
        """Get a single node by exact topic match including 6-element fields."""
        query = """
        MATCH (n:Knowledge {topic: $topic})
        RETURN n.topic as topic, n.content as content, n.status as status,
               n.heat as heat, n.quality as quality, n.confidence as confidence,
               n.depth as depth, n.source_urls as source_urls,
               n.definition as definition, n.core as core, n.context as context,
               n.examples as examples, n.formula as formula,
               n.completeness_score as completeness_score, n.parent_topic as parent_topic
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

    async def create_knowledge_node_from_model(self, node: KnowledgeNode) -> str:
        """Create a knowledge node from KnowledgeNode Pydantic model.
        
        Converts the composed KnowledgeNode model into the flat metadata dict
        format expected by create_knowledge_node.
        """
        metadata = {
            "heat": node.heat,
            "quality": node.quality,
            "status": node.status,
            "deep_read_status": node.deep_read_status,
            "definition": node.content.definition,
            "formula": node.content.formula,
            "fact": node.content.fact,
            "examples": node.content.examples or [],
            "completeness_score": node.content.completeness_score,
            "source_url": node.source.source_url,
            "source_type": node.source.source_type,
            "source_trusted": node.source.source_trusted,
            "local_file_path": node.source.local_file_path,
            "extracted_text_path": node.source.extracted_text_path,
            "source_missing": node.source.source_missing,
            "parent_topic": node.relations.parent,
            "children": node.relations.children or [],
            "depends_on": node.relations.depends_on or [],
            "related_to": node.relations.related_to or [],
            "keywords": node.keywords or [],
        }
        
        relations = []
        if node.relations.parent:
            relations.append({
                "parent": node.relations.parent,
                "type": "DERIVED_FROM"
            })
        
        return await self.create_knowledge_node(
            topic=node.topic,
            content=node.content.definition,
            source_urls=[node.source.source_url] if node.source.source_url else [],
            metadata=metadata,
            relations=relations,
            key_points=node.content.examples or [],
            keywords=node.keywords or []
        )