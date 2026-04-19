# KG Vector Index Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Neo4j native vector indexing for KG semantic retrieval, enabling queries like "agent上下文管理系统是干嘛的？" to match KG node "agent上下文管理系统".

**Architecture:** Combined embedding approach - store topic + key_points + content + keywords as single 1024-dim vector on Knowledge nodes. Use Neo4j HNSW vector index for semantic retrieval. Whole-query embedding as primary strategy.

**Tech Stack:** Neo4j 5.x vector index, EmbeddingService (BGE-M3/SiliconFlow, 1024-dim), Cypher vector procedures.

---

## Phase 1: KG Repository & Vector Index

### Task 1.1: Add Vector Index Initialization

**Files:**
- Modify: `core/kg/neo4j_client.py`
- Test: `tests/core/kg/test_vector_index.py` (new)

**Step 1: Write the failing test**

```python
# tests/core/kg/test_vector_index.py
import pytest
from core.kg.neo4j_client import Neo4jClient

@pytest.mark.asyncio
async def test_vector_index_exists():
    """Verify knowledge_embeddings vector index exists."""
    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="R1D3researcher2026"
    )
    await client.connect()
    
    result = await client.execute_query("SHOW VECTOR INDEXES")
    index_names = [r.get("name") for r in result]
    
    assert "knowledge_embeddings" in index_names
    await client.disconnect()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/kg/test_vector_index.py -v`
Expected: FAIL - "knowledge_embeddings" not in index_names

**Step 3: Add vector index initialization to neo4j_client.py**

```python
# core/kg/neo4j_client.py - add after connect() method

async def _init_vector_index(self) -> bool:
    """Initialize vector index for Knowledge embeddings."""
    query = """
    CREATE VECTOR INDEX knowledge_embeddings IF NOT EXISTS
    FOR (n:Knowledge) ON n.embedding
    OPTIONS { indexConfig: {
      `vector.dimensions`: 1024,
      `vector.similarity_function`: 'cosine'
    }}
    """
    try:
        await self.execute_write(query)
        logger.info("Vector index 'knowledge_embeddings' created/verified")
        return True
    except Exception as e:
        logger.error(f"Failed to create vector index: {e}")
        return False

async def connect(self) -> bool:
    """Establish connection and initialize vector index."""
    try:
        self._driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
            max_connection_lifetime=self.max_connection_lifetime
        )
        # Initialize vector index
        await self._init_vector_index()
        return True
    except Exception as e:
        raise Exception(f"Failed to connect to Neo4j: {e}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/kg/test_vector_index.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/kg/neo4j_client.py tests/core/kg/test_vector_index.py
git commit -m "feat(kg): add vector index initialization for Knowledge nodes"
```

---

### Task 1.2: Add Semantic Query Method to KG Repository

**Files:**
- Modify: `core/kg/kg_repository.py`
- Test: `tests/core/kg/test_semantic_query.py` (new)

**Step 1: Write the failing test**

```python
# tests/core/kg/test_semantic_query.py
import pytest
from core.kg.kg_repository import KGRepository
from core.kg.neo4j_client import Neo4jClient
from core.embedding_service import EmbeddingService, EmbeddingConfig

@pytest.mark.asyncio
async def test_semantic_query_returns_results():
    """Verify semantic query returns matching nodes."""
    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="R1D3researcher2026"
    )
    await client.connect()
    
    embedding_service = EmbeddingService(EmbeddingConfig())
    repo = KGRepository(client, embedding_service)
    
    # Query for agent context management
    results = await repo.query_knowledge_semantic(
        query_text="agent上下文管理系统是干嘛的？",
        top_k=3,
        threshold=0.70
    )
    
    assert len(results) > 0
    # Should match "agent上下文管理系统"
    matched_topics = [r["topic"] for r in results]
    assert any("agent上下文" in t or "context" in t.lower() for t in matched_topics)
    
    await client.disconnect()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/kg/test_semantic_query.py -v`
Expected: FAIL - AttributeError: 'KGRepository' has no 'query_knowledge_semantic'

**Step 3: Add semantic query method to kg_repository.py**

```python
# core/kg/kg_repository.py - modify __init__ and add new method

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class KGRepository:
    """Repository for Knowledge Graph node and relation operations."""

    def __init__(self, neo4j_client: Any, embedding_service: Any = None):
        self._client = neo4j_client
        self._embedding_service = embedding_service

    async def query_knowledge_semantic(
        self,
        query_text: str,
        top_k: int = 5,
        threshold: float = 0.75,
        status_filter: str = "done"
    ) -> List[Dict[str, Any]]:
        """Query KG using semantic vector similarity.
        
        Args:
            query_text: User query (whole sentence)
            top_k: Number of results to return
            threshold: Minimum similarity score (0-1)
            status_filter: Filter by node status
            
        Returns:
            List of matching nodes with similarity scores
        """
        if not self._embedding_service:
            logger.warning("No embedding service available, falling back to text search")
            return await self.query_knowledge(query_text, limit=top_k)
        
        # Generate query embedding
        try:
            embedding = self._embedding_service.embed(query_text)[0]
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return []
        
        # Vector index query with status filter
        query = """
        CALL db.index.vector.queryNodes('knowledge_embeddings', $top_k, $embedding)
        YIELD node, score
        WHERE score >= $threshold AND node.status = $status
        RETURN node.topic as topic, 
               node.content as content,
               node.key_points as key_points,
               node.keywords as keywords,
               node.quality as quality,
               node.confidence as confidence,
               score
        ORDER BY score DESC
        """
        
        try:
            result = await self._client.execute_query(
                query,
                embedding=embedding,
                top_k=top_k * 2,  # Fetch more for filtering
                threshold=threshold,
                status=status_filter
            )
            return result[:top_k]
        except Exception as e:
            logger.error(f"Vector query failed: {e}")
            return []
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/kg/test_semantic_query.py -v`
Expected: PASS (after backfill completes in Phase 3)

**Step 5: Commit**

```bash
git add core/kg/kg_repository.py tests/core/kg/test_semantic_query.py
git commit -m "feat(kg): add semantic query method with vector similarity"
```

---

### Task 1.3: Update Node Creation to Include Embedding

**Files:**
- Modify: `core/kg/kg_repository.py`
- Modify: `core/knowledge_graph_compat.py`
- Test: `tests/core/kg/test_node_embedding.py` (new)

**Step 1: Write the failing test**

```python
# tests/core/kg/test_node_embedding.py
import pytest
from core.kg.kg_repository import KGRepository
from core.kg.neo4j_client import Neo4jClient
from core.embedding_service import EmbeddingService, EmbeddingConfig

@pytest.mark.asyncio
async def test_new_node_has_embedding():
    """Verify new knowledge node has embedding property."""
    client = Neo4jClient(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="R1D3researcher2026"
    )
    await client.connect()
    
    embedding_service = EmbeddingService(EmbeddingConfig())
    repo = KGRepository(client, embedding_service)
    
    # Create test node
    await repo.create_knowledge_node(
        topic="test-embedding-node",
        content="This is test content for embedding verification",
        metadata={"key_points": ["test point 1", "test point 2"], 
                  "keywords": ["test", "embedding"]}
    )
    
    # Verify embedding exists
    node = await repo.get_node("test-embedding-node")
    assert node is not None
    assert "embedding" in node
    assert len(node["embedding"]) == 1024
    
    # Cleanup
    await client.execute_write("MATCH (n:Knowledge {topic: 'test-embedding-node'}) DELETE n")
    await client.disconnect()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/kg/test_node_embedding.py -v`
Expected: FAIL - "embedding" not in node

**Step 3: Modify create_knowledge_node to generate embedding**

```python
# core/kg/kg_repository.py - modify create_knowledge_node

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
    """Create a knowledge node with embedding."""
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

    # Generate combined embedding
    embedding = None
    if self._embedding_service:
        combined_text = self._build_combined_text(topic, key_points, content, keywords)
        try:
            embedding = self._embedding_service.embed(combined_text)[0]
        except Exception as e:
            logger.warning(f"Failed to generate embedding for '{topic}': {e}")

    query = """
    MERGE (n:Knowledge {topic: $topic})
    SET n.content = $content,
        n.source_urls = $source_urls,
        n.key_points = $key_points,
        n.keywords = $keywords,
        n.embedding = $embedding,
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
        key_points=key_points,
        keywords=keywords,
        embedding=embedding,
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

def _build_combined_text(
    self, 
    topic: str, 
    key_points: List[str], 
    content: str, 
    keywords: List[str]
) -> str:
    """Build combined text for embedding generation.
    
    Format: topic(40%) + key_points(30%) + content(20%) + keywords(10%)
    """
    parts = [f"【主题】{topic}"]
    
    if key_points:
        points_text = "\n".join(f"• {p}" for p in key_points[:5])
        parts.append(f"\n【关键要点】\n{points_text}")
    
    if content:
        parts.append(f"\n【简介】\n{content[:300]}")
    
    if keywords:
        parts.append(f"\n【关键词】\n{', '.join(keywords)}")
    
    return "\n".join(parts)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/kg/test_node_embedding.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/kg/kg_repository.py tests/core/kg/test_node_embedding.py
git commit -m "feat(kg): generate embedding on node creation with combined text"
```

---

## Phase 2: API Endpoints

### Task 2.1: Add Semantic Query Endpoint

**Files:**
- Modify: `curious_api.py`
- Test: `tests/api/test_semantic_endpoint.py` (new)

**Step 1: Write the failing test**

```python
# tests/api/test_semantic_endpoint.py
import pytest
from fastapi.testclient import TestClient
from curious_api import app

client = TestClient(app)

def test_semantic_endpoint_returns_matches():
    """Test /api/knowledge/semantic endpoint."""
    response = client.get(
        "/api/knowledge/semantic",
        params={"query": "agent上下文管理系统是干嘛的？", "top_k": 3}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0
    
    # Check result structure
    result = data["results"][0]
    assert "topic" in result
    assert "score" in result
    assert result["score"] >= 0.70
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_semantic_endpoint.py -v`
Expected: FAIL - 404 Not Found

**Step 3: Add semantic endpoint to curious_api.py**

```python
# curious_api.py - add new endpoint

@app.get("/api/knowledge/semantic")
async def semantic_query(
    query: str,
    top_k: int = 5,
    threshold: float = 0.75,
    status: str = "done"
):
    """Semantic search for knowledge using vector similarity.
    
    Args:
        query: User query text (natural language)
        top_k: Number of results to return
        threshold: Minimum similarity threshold (0-1)
        status: Filter by node status
        
    Returns:
        List of matching knowledge nodes with similarity scores
    """
    results = await kg_repository.query_knowledge_semantic(
        query_text=query,
        top_k=top_k,
        threshold=threshold,
        status_filter=status
    )
    
    return {
        "query": query,
        "results": results,
        "count": len(results)
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_semantic_endpoint.py -v`
Expected: PASS (after backfill)

**Step 5: Commit**

```bash
git add curious_api.py tests/api/test_semantic_endpoint.py
git commit -m "feat(api): add /api/knowledge/semantic endpoint for vector search"
```

---

### Task 2.2: Fix Confidence Endpoint

**Files:**
- Modify: `core/api/host_agent_integration.py`
- Test: `tests/api/test_confidence_semantic.py` (new)

**Step 1: Write the failing test**

```python
# tests/api/test_confidence_semantic.py
import pytest

def test_confidence_returns_nonzero_for_similar_query():
    """Test confidence endpoint uses semantic matching."""
    from core.api.host_agent_integration import HostAgentIntegration
    
    integration = HostAgentIntegration(
        kg_repository=kg_repository,
        embedding_service=embedding_service
    )
    
    # Query with question suffix should match exact topic
    result = integration.check_confidence("agent上下文管理系统是干嘛的？")
    
    assert result["confidence"] > 0.0
    assert result["topic"] != "agent上下文管理系统是干嘛的？"  # Should return actual KG topic
    assert "agent上下文" in result["topic"] or "context" in result["topic"].lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_confidence_semantic.py -v`
Expected: FAIL - confidence = 0.0

**Step 3: Modify check_confidence to use semantic query**

```python
# core/api/host_agent_integration.py - modify check_confidence method

def check_confidence(self, topic: str) -> dict:
    """Check confidence level for a topic using semantic matching.
    
    Args:
        topic: User query (may include question suffix)
        
    Returns:
        Dict with confidence, matched_topic, level, gaps
    """
    # Try semantic query first
    semantic_results = self._kg_repository.query_knowledge_semantic(
        query_text=topic,
        top_k=3,
        threshold=0.75,
        status_filter="done"
    )
    
    if not semantic_results:
        return {
            "confidence": 0.0,
            "explore_count": 0,
            "gaps": ["No matching knowledge found"],
            "level": "novice",
            "topic": topic
        }
    
    # Use best match
    best_match = semantic_results[0]
    matched_topic = best_match["topic"]
    similarity_score = best_match["score"]
    quality = best_match.get("quality", 0.0) or 0.0
    
    # Calculate confidence: similarity * quality_normalized
    confidence = similarity_score * (quality / 10.0)
    
    # Determine level based on confidence
    if confidence >= 0.8:
        level = "expert"
    elif confidence >= 0.5:
        level = "intermediate"
    else:
        level = "beginner"
    
    return {
        "confidence": confidence,
        "matched_topic": matched_topic,
        "similarity": similarity_score,
        "quality": quality,
        "level": level,
        "gaps": [],
        "topic": topic
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_confidence_semantic.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/api/host_agent_integration.py tests/api/test_confidence_semantic.py
git commit -m "fix(api): use semantic matching for confidence endpoint"
```

---

## Phase 3: Backfill Existing Nodes

### Task 3.1: Create Backfill Script

**Files:**
- Create: `scripts/backfill_kg_embeddings.py`
- Test: Manual execution

**Step 1: Create backfill script**

```python
# scripts/backfill_kg_embeddings.py
"""Backfill embeddings for existing KG nodes."""
import asyncio
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from pathlib import Path
from core.kg.neo4j_client import Neo4jClient
from core.embedding_service import EmbeddingService, EmbeddingConfig
from core.config import load_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def extract_key_points(content: str, llm_client, max_points: int = 5) -> list:
    """Extract key points from content using LLM."""
    if not content or len(content) < 50:
        return []
    
    prompt = f"""Extract 3-5 key points from the following content. Return as JSON array.

Content: {content[:1000]}

Return format: ["point 1", "point 2", ...]"""
    
    try:
        response = llm_client.generate(prompt, max_tokens=200)
        # Parse JSON array from response
        import json
        import re
        match = re.search(r'\[.*\]', response)
        if match:
            return json.loads(match.group())[:max_points]
    except Exception as e:
        logger.warning(f"Failed to extract key points: {e}")
    
    # Fallback: extract first sentences
    sentences = content.split("\n")[:max_points]
    return [s.strip()[:100] for s in sentences if s.strip()]


async def extract_keywords(content: str, llm_client, max_keywords: int = 10) -> list:
    """Extract keywords from content using LLM."""
    if not content or len(content) < 50:
        return []
    
    prompt = f"""Extract 5-10 core concept keywords from: {content[:500]}
Return comma-separated keywords only."""
    
    try:
        response = llm_client.generate(prompt, max_tokens=100)
        keywords = [k.strip().lower() for k in response.split(",") if k.strip()]
        return keywords[:max_keywords]
    except Exception:
        # Fallback: use concept_normalizer
        from core.concept_normalizer import ConceptNormalizer
        normalizer = ConceptNormalizer()
        return normalizer.extract_core_concepts(content)[:max_keywords]


async def backfill_embeddings():
    """Backfill embeddings for all existing KG nodes."""
    config = load_config()
    
    # Initialize clients
    neo4j_client = Neo4jClient(
        uri=config.neo4j.uri,
        username=config.neo4j.username,
        password=config.neo4j.password
    )
    await neo4j_client.connect()
    
    embedding_service = EmbeddingService(config.knowledge.get("embedding"))
    
    # Get all nodes without embeddings
    query = """
    MATCH (n:Knowledge)
    WHERE n.embedding IS NULL OR n.status = 'done'
    RETURN n.topic as topic, n.content as content, n.status as status
    """
    nodes = await neo4j_client.execute_query(query)
    
    logger.info(f"Found {len(nodes)} nodes to backfill")
    
    for node in nodes:
        topic = node["topic"]
        content = node.get("content", "")
        
        if not content:
            logger.warning(f"Skipping '{topic}' - no content")
            continue
        
        logger.info(f"Processing: {topic}")
        
        # Extract key_points and keywords (simplified - could use LLM)
        from core.concept_normalizer import ConceptNormalizer
        normalizer = ConceptNormalizer()
        keywords = normalizer.extract_core_concepts(topic + " " + content)[:10]
        key_points = content.split("\n")[:5]  # Simple extraction
        
        # Build combined text
        combined_text = f"【主题】{topic}\n【简介】{content[:300]}\n【关键词】{', '.join(keywords)}"
        
        # Generate embedding
        try:
            embedding = embedding_service.embed(combined_text)[0]
        except Exception as e:
            logger.error(f"Failed to embed '{topic}': {e}")
            continue
        
        # Update node
        update_query = """
        MATCH (n:Knowledge {topic: $topic})
        SET n.embedding = $embedding,
            n.key_points = $key_points,
            n.keywords = $keywords,
            n.updated_at = timestamp()
        """
        await neo4j_client.execute_write(
            update_query,
            topic=topic,
            embedding=embedding,
            key_points=key_points,
            keywords=keywords
        )
        
        logger.info(f"Updated: {topic}")
    
    await neo4j_client.disconnect()
    logger.info("Backfill complete!")


if __name__ == "__main__":
    asyncio.run(backfill_embeddings())
```

**Step 2: Run backfill manually**

Run: `python scripts/backfill_kg_embeddings.py`
Expected: "Backfill complete!" with ~7 nodes updated

**Step 3: Verify embeddings exist**

Run: `curl -s "http://localhost:4848/api/curious/state" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Nodes with embedding:', sum(1 for n in d['knowledge']['topics'].values() if n.get('embedding')))"`
Expected: Nodes with embedding: 7+

**Step 4: Commit**

```bash
git add scripts/backfill_kg_embeddings.py
git commit -m "feat(scripts): add backfill script for KG embeddings"
```

---

### Task 3.2: Run Integration Test

**Files:**
- Test: Manual via API

**Step 1: Test semantic query**

Run: `curl -s "http://localhost:4848/api/knowledge/semantic?query=agent上下文管理系统是干嘛的？&top_k=3"`
Expected: JSON with results containing "agent上下文管理系统" with score > 0.75

**Step 2: Test confidence endpoint**

Run: `curl -s "http://localhost:4848/api/knowledge/confidence?topic=agent上下文管理系统是干嘛的？"`
Expected: JSON with confidence > 0.0, matched_topic = "agent上下文管理系统"

**Step 3: Verify in Neo4j**

Run Neo4j Browser query:
```cypher
MATCH (n:Knowledge)
WHERE n.embedding IS NOT NULL
RETURN n.topic, n.keywords, n.key_points, size(n.embedding) as embedding_size
```
Expected: 7+ nodes with embedding_size = 1024

---

## Phase 4: Documentation & Cleanup

### Task 4.1: Update ARCHITECTURE.md

**Files:**
- Modify: `ARCHITECTURE.md`

**Step 1: Add vector index section**

```markdown
## Vector Index Architecture

### Neo4j Vector Index

CA uses Neo4j 5.x native vector indexing for semantic retrieval:

- **Index Name**: `knowledge_embeddings`
- **Algorithm**: HNSW (Hierarchical Navigable Small World)
- **Similarity**: Cosine
- **Dimensions**: 1024 (BAAI/bge-large-zh-v1.5)

### Combined Embedding

KG nodes store a combined embedding of:
- `topic` (40%) - Node title/identifier
- `key_points` (30%) - Extracted key insights
- `content` (20%) - Knowledge summary
- `keywords` (10%) - Core concepts

### Semantic Query Flow

1. User query → EmbeddingService.embed()
2. Vector index search → db.index.vector.queryNodes()
3. Filter by status/quality threshold
4. Return matched nodes with similarity scores
```

**Step 2: Commit**

```bash
git add ARCHITECTURE.md
git commit -m "docs: add vector index architecture documentation"
```

---

### Task 4.2: Final Verification

**Step 1: Run all tests**

Run: `pytest tests/core/kg/ tests/api/ -v`
Expected: All tests PASS

**Step 2: Push to remote**

```bash
git push origin main
```

**Step 3: Create tag**

```bash
git tag -a v0.3.2 -m "feat: KG vector index for semantic retrieval"
git push origin v0.3.2
```

---

## Summary

| Phase | Tasks | Files Changed |
|-------|-------|---------------|
| Phase 1 | 3 tasks | neo4j_client.py, kg_repository.py, 3 tests |
| Phase 2 | 2 tasks | curious_api.py, host_agent_integration.py, 2 tests |
| Phase 3 | 2 tasks | backfill_kg_embeddings.py |
| Phase 4 | 2 tasks | ARCHITECTURE.md, final tests |

**Estimated Time**: 2-3 hours

---

Plan complete and saved to `docs/plans/2026-04-19-kg-vector-index-impl-plan.md`.

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**