# KG Vector Index Design - Neo4j Native Vector Search

**Date**: 2026-04-19  
**Status**: Approved  
**Author**: Sisyphus (AI Agent)

## Problem Statement

The `/api/knowledge/confidence` endpoint uses exact topic matching, causing queries like `"agent上下文管理系统是干嘛的？"` to fail matching KG node `"agent上下文管理系统"` (confidence=0).

**Root Cause**: `check_confidence()` uses `topics.get(topic, {})` - exact key lookup, no semantic matching.

## Solution Overview

Implement **Neo4j native vector indexing** with **combined embedding** approach:

- Combine `topic` + `key_points` + `content` + `keywords` into single embedding
- Create HNSW vector index for semantic retrieval
- Replace exact matching with vector similarity search

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     KG Node (:Knowledge)                         │
│  topic: "agent上下文管理系统"                                     │
│  content: "知识摘要..."                                           │
│  key_points: ["管理上下文窗口", "支持记忆切换"]  ← NEW            │
│  keywords: ["context", "management"]          ← NEW            │
│  embedding: [0.123, 0.456, ...]               ← NEW (1024-dim) │
│  quality: 8.0, confidence: 0.85, status: "done"                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Neo4j Vector Index (knowledge_embeddings)           │
│  • Algorithm: HNSW (Hierarchical Navigable Small World)         │
│  • Similarity: Cosine                                            │
│  • Dimensions: 1024 (BAAI/bge-large-zh-v1.5)                    │
│  • Query: CALL db.index.vector.queryNodes(...)                  │
└─────────────────────────────────────────────────────────────────┘
```

## Combined Embedding Composition

**4-dimensional fusion with weighted emphasis:**

| Component | Weight | Purpose |
|-----------|--------|---------|
| topic | 40% | Primary matching dimension |
| key_points | 30% | High-value semantic content |
| content | 20% | Supplementary context |
| keywords | 10% | Matching enhancement |

**Combined text format:**

```python
combined_text = f"""【主题】{topic}

【关键要点】
{chr(10).join(f'• {p}' for p in key_points[:5])}

【简介】
{content[:300]}

【关键词】
{', '.join(keywords)}
"""

# Example output:
# 【主题】agent上下文管理系统
#
# 【关键要点】
# • 管理Agent的上下文窗口和记忆
# • 支持短期记忆和长期记忆的切换
# • 提供上下文压缩和检索功能
#
# 【简介】
# Agent上下文管理是构建AI Agent的核心能力...
#
# 【关键词】
# context, management, agent, memory
```

## KG Node Property Changes

### New Properties to Add

| Property | Type | Source | Description |
|----------|------|--------|-------------|
| `key_points` | List[String] | LLM extraction | 3-5 key insights |
| `keywords` | List[String] | LLM extraction | 5-10 core concepts |
| `embedding` | List[Float] | EmbeddingService | 1024-dim vector |

### Existing Properties (unchanged)

| Property | Type | Description |
|----------|------|-------------|
| `topic` | String | Node identifier/title |
| `content` | String | Knowledge summary |
| `source_urls` | List[String] | Citation URLs |
| `quality` | Float | Quality score (0-10) |
| `confidence` | Float | Confidence level (0-1) |
| `status` | String | pending/exploring/done/dormant |
| `depth` | Float | Exploration depth |

## Semantic Query Flow

```
User Query: "agent上下文管理系统是干嘛的？"
    │
    ▼
EmbeddingService.embed(query) → query_vector (1024-dim)
    │
    ▼
Neo4j Vector Index Query:
CALL db.index.vector.queryNodes('knowledge_embeddings', 5, $query_vector)
YIELD node, score
WHERE score >= 0.75 AND node.status = 'done'
    │
    ▼
Results: [{"topic": "agent上下文管理系统", "score": 0.89, ...}]
    │
    ▼
Confidence Calculation: score * node.quality / 10 = 0.89 * 8.0 / 10 = 0.71
```

## Implementation Components

### File Changes

| File | Changes |
|------|---------|
| `core/kg/kg_repository.py` | Add `key_points`, `keywords`, `embedding` properties; add semantic query method |
| `core/kg/neo4j_client.py` | Initialize vector index on startup |
| `core/api/host_agent_integration.py` | Replace exact match with semantic query |
| `curious_api.py` | Add `/api/knowledge/semantic` endpoint; fix `/api/knowledge/confidence` |
| `core/knowledge_graph_compat.py` | Update `add_knowledge()` to generate embedding |
| `scripts/backfill_kg_embeddings.py` | NEW - Batch generate embeddings for existing nodes |

### Vector Index Creation (Cypher)

```cypher
CREATE VECTOR INDEX knowledge_embeddings IF NOT EXISTS
FOR (n:Knowledge) ON n.embedding
OPTIONS { indexConfig: {
  `vector.dimensions`: 1024,
  `vector.similarity_function`: 'cosine'
}};
```

### Semantic Query Method (Python)

```python
async def query_knowledge_semantic(
    self,
    query_text: str,
    top_k: int = 5,
    threshold: float = 0.75,
    status_filter: str = "done"
) -> List[Dict[str, Any]]:
    """Query KG using semantic vector similarity."""
    
    # Generate query embedding
    embedding = self._embedding_service.embed(query_text)[0]
    
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
           score
    ORDER BY score DESC
    """
    
    return await self._client.execute_query(
        query,
        embedding=embedding,
        top_k=top_k * 2,  # Fetch more for filtering
        threshold=threshold,
        status=status_filter
    )
```

## Key Points & Keywords Extraction

### Reuse Existing Extraction Logic

**Key Points** - from `reasoning_compressor._extract_key_points()`:
```python
def _extract_key_points(self, text: str, max_points: int = 5) -> List[str]:
    """Extract key points from content."""
    # Parse markdown sections or first paragraphs
    # Return top max_points insights
```

**Keywords** - from `meta_cognitive_monitor._extract_keywords()`:
```python
def _extract_keywords(self, text: str) -> List[str]:
    """Extract keywords using LLM (5-10 core concepts)."""
    prompt = f"""Extract 5-10 core concept keywords from: {text[:500]}"""
    # Return comma-separated keywords
```

### Extraction on Node Creation

```python
async def create_knowledge_node(self, topic, content, ...):
    # Extract key_points and keywords
    key_points = self._extract_key_points(content)
    keywords = self._extract_keywords(content)
    
    # Generate combined embedding
    combined_text = self._build_combined_text(topic, key_points, content, keywords)
    embedding = self._embedding_service.embed(combined_text)[0]
    
    # Store in Neo4j
    query = """
    MERGE (n:Knowledge {topic: $topic})
    SET n.content = $content,
        n.key_points = $key_points,
        n.keywords = $keywords,
        n.embedding = $embedding,
        ...
    """
```

## Data Migration (Backfill)

### Steps

1. Create vector index `knowledge_embeddings`
2. Fetch all existing `done` status nodes
3. For each node:
   - Extract `key_points` from content (LLM)
   - Extract `keywords` from content (LLM)
   - Build combined text
   - Generate embedding (EmbeddingService)
   - Update node with new properties
4. Verify vector index populated

### Estimated Volume

- ~7 existing `done` nodes
- ~100ms per embedding generation (SiliconFlow API)
- Total backfill time: ~1-2 minutes

## Query Processing Strategy

### Research-Based Recommendation

Based on RAG best practices research (EMNLP 2024, LevelRAG, Milvus benchmarks):

| Strategy | Recommendation | Evidence |
|----------|---------------|----------|
| **Whole-query embedding** | ✅ **Primary** | Modern multilingual models (BGE-M3) handle Chinese naturally, 0.99+ cross-lingual accuracy |
| **Pre-segmentation to keywords** | ❌ **Avoid** | Destroys semantic coherence; token-level decomposition happens internally in transformers |
| **Hybrid (Dense + BM25)** | ⚠️ **Optional** | Production standard, but requires separate BM25 index (not yet in CA) |
| **Query decomposition** | ⚠️ **Complex queries only** | Multi-hop reasoning queries; not typical for CA KG queries |

### Implementation

```python
def semantic_query(query_text: str) -> List[Dict]:
    """Primary strategy: Whole-query embedding.
    
    CA KG combined embedding (topic + key_points + content + keywords) 
    already contains multi-dimensional info, so whole-query naturally matches.
    """
    # Step 1: Whole-query embedding (primary)
    query_embedding = embedding_service.embed(query_text)[0]
    
    # Step 2: Vector index search
    results = await kg_repository.query_knowledge_semantic(
        query_embedding=query_embedding,
        top_k=5,
        threshold=0.75
    )
    
    # Step 3: Optional enhancement - extract core concepts for fallback
    if not results or results[0]['score'] < 0.75:
        core_concepts = concept_normalizer.extract_core_concepts(query_text)
        if core_concepts:
            # Use extracted concepts as simplified query
            concept_text = " ".join(core_concepts)
            concept_embedding = embedding_service.embed(concept_text)[0]
            fallback_results = await kg_repository.query_knowledge_semantic(
                query_embedding=concept_embedding,
                top_k=3,
                threshold=0.70
            )
            results = merge_and_deduplicate(results, fallback_results)
    
    return results
```

### Why Whole-Query Works for CA KG

1. **Combined embedding richness**: KG nodes store `topic + key_points + content + keywords` combined embedding, which captures multi-dimensional semantics
2. **Query naturally matches**: User query "agent上下文管理系统是干嘛的？" contains core concept "agent上下文管理系统" which will match the topic portion of combined embedding
3. **Embedding model handles noise**: BGE-M3 naturally handles question words ("是干嘛的", "怎么样") as part of semantic context, not noise
4. **No segmentation error propagation**: Avoids Chinese word segmentation mistakes that could break matching

### Future Enhancement: Hybrid Search

When CA adds BM25/Full-text index capability:

```python
# Future: Hybrid Dense + Sparse retrieval
def hybrid_search(query: str):
    # Parallel execution
    dense_results = vector_index.search(query_embedding, k=10)
    sparse_results = bm25_index.search(jieba_tokenize(query), k=10)
    
    # Reciprocal Rank Fusion
    return rrf_fusion(dense_results, sparse_results, weights=[0.7, 0.3])
```

---

## Success Criteria

| Criteria | Verification |
|----------|--------------|
| Vector index created | `SHOW VECTOR INDEXES` returns `knowledge_embeddings` |
| Existing nodes have embedding | `MATCH (n:Knowledge) WHERE n.embedding IS NOT NULL RETURN count(n)` >= 7 |
| Semantic query returns matches | Query `"agent上下文管理系统是干嘛的"` matches `"agent上下文管理系统"` with score > 0.75 |
| Confidence endpoint returns correct value | `/api/knowledge/confidence?topic=agent上下文...` returns confidence > 0.5 |
| API endpoint `/api/knowledge/semantic` works | Returns semantic matches with scores |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Embedding API latency | Cache embeddings; use batch API for backfill |
| Key_points extraction fails | Fallback to content-first-paragraph |
| Keywords empty | Fallback to concept_normalizer.extract_core_concepts() |
| Vector index not available | Check Neo4j version >= 5.11; fallback to vector.similarity.cosine() |
| Query drift (semantic vs intent) | Add threshold tuning; combine with status/quality filters |

## Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Neo4j native vector index** | Unified storage; graph+vector queries; ACID | Requires backfill | ✅ Selected |
| **FAISS separate index** | High performance; existing template | Two systems to sync | ❌ Rejected |
| **Runtime cosine similarity** | No backfill needed | O(n) performance | ❌ Rejected |
| **Multi-vector (separate indexes)** | Higher precision | Complex fusion; 3x embeddings | ❌ Rejected (use combined) |

## References

- [Neo4j Vector Indexes - Cypher Manual](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)
- [Neo4j Vector Functions](https://neo4j.com/docs/cypher-manual/current/functions/vector/)
- CA existing: `core/embedding_service.py`, `core/concept_normalizer.py`, `core/reasoning_compressor.py`

---

## Next Steps

1. Invoke `writing-plans` skill to create detailed implementation plan
2. Execute implementation in phases:
   - Phase 1: Vector index creation + repository changes
   - Phase 2: API endpoint updates
   - Phase 3: Backfill script + execution
   - Phase 4: Testing & verification