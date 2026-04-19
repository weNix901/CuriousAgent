# ExploreAgent KG Writing Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix ExploreAgent to write meaningful knowledge summaries with real sources to KG, not ReAct loop logs.

**Architecture:** 
- ExploreAgent collects sources during ReAct loop, generates summary via llm_summarize at end
- ExploreDaemon removes duplicate KG write, only handles queue mark_done
- AddToKGTool gains source_urls parameter for proper attribution

**Tech Stack:** Python async, Neo4j, SQLite, LLM tools

---

## Problem Summary

| Issue | Current Behavior | Target Behavior |
|-------|-----------------|-----------------|
| Content | Writes `Action/Observation` logs | Writes LLM-generated summary |
| Sources | `sources=[]` always empty | Collects URLs from `fetch_page` calls |
| Quality | Fixed `quality=5.0` | Evaluated by `llm_analyze` |
| Write Location | Both ExploreAgent + ExploreDaemon | Only ExploreAgent |
| Duplicate | Two writes conflict | Single write |

---

## Task 1: Add source_urls Parameter to AddToKGTool

**Files:**
- Modify: `core/tools/kg_tools.py:162-206`
- Modify: `core/knowledge_graph_compat.py:add_knowledge_async`

**Step 1: Update AddToKGTool parameters**

```python
# core/tools/kg_tools.py AddToKGTool.parameters property
@property
def parameters(self) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Topic name for the new node"},
            "content": {"type": "string", "description": "Knowledge summary content", "default": ""},
            "source_urls": {"type": "array", "description": "List of source URLs", "default": []},
            "metadata": {"type": "object", "description": "Metadata (depth, quality, confidence)", "default": {}},
            "relations": {"type": "array", "description": "Relations to other nodes", "default": []}
        },
        "required": ["topic"]
    }
```

**Step 2: Update AddToKGTool.execute to pass source_urls**

```python
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
```

**Step 3: Run syntax check**

Run: `python3 -m py_compile core/tools/kg_tools.py`
Expected: No errors

**Step 4: Commit**

```bash
git add core/tools/kg_tools.py
git commit -m "feat: AddToKGTool now supports source_urls parameter"
```

---

## Task 2: Update knowledge_graph_compat.add_knowledge_async for source_urls

**Files:**
- Modify: `core/knowledge_graph_compat.py:add_knowledge_async`

**Step 1: Add source_urls parameter to add_knowledge_async**

```python
async def add_knowledge_async(
    topic: str, 
    depth: int = 5, 
    summary: str = "", 
    sources: Optional[list] = None, 
    quality: Optional[float] = None
) -> None:
    kg_factory = _get_kg_factory()
    
    metadata = {
        "depth": depth,
        "quality": quality if quality is not None else 0,
        "status": "done"
    }
    
    await kg_factory.create_knowledge_node_async(
        topic=topic,
        content=summary,
        source_urls=sources or [],  # Changed: now passes to KG
        metadata=metadata
    )
```

**Step 2: Verify KGRepository.create_knowledge_node_async already accepts source_urls**

Run: `grep -n "source_urls" core/kg/kg_repository.py`
Expected: Already has `source_urls: List[str]` parameter (line 15)

**Step 3: Commit**

```bash
git add core/knowledge_graph_compat.py
git commit -m "fix: add_knowledge_async now passes source_urls to KG"
```

---

## Task 3: Modify ExploreAgent._react_loop to Collect Sources

**Files:**
- Modify: `core/agents/explore_agent.py:150-330`

**Step 1: Add sources collection tracking in _react_loop**

```python
# In _react_loop method, after initializing variables:
async def _react_loop(self, topic: str) -> dict[str, Any]:
    messages = []
    iterations = 0
    observations = []
    content_parts = []
    tools_used_set = set()
    
    # NEW: Track collected sources
    collected_sources: list[str] = []
    useful_content_parts: list[str] = []
```

**Step 2: Extract sources from fetch_page observations**

```python
# After executing action (around line 297), add:
observation = await self._execute_action(action, action_input)
tools_used_set.add(action)

# NEW: Extract URLs from fetch_page results
if action == "fetch_page" and "url" in str(action_input):
    try:
        url = action_input.get("url") if isinstance(action_input, dict) else None
        if url and observation and "ERROR" not in observation:
            collected_sources.append(url)
    except Exception:
        pass

# NEW: Track useful content for summary (from llm_analyze positive results)
if action == "llm_analyze" and "useful" in observation.lower() or "relevant" in observation.lower():
    useful_content_parts.append(observation)
```

**Step 3: Generate proper summary at loop end with llm_summarize**

```python
# Replace the KG write section (lines 261-269 and 316-324) with:
# At loop completion:
if collected_sources or useful_content_parts:
    # Use llm_summarize to generate proper summary
    summarize_tool = self.tool_registry.get("llm_summarize")
    if summarize_tool:
        content_to_summarize = "\n".join(useful_content_parts[-5:])  # Last 5 useful observations
        summary_result = await summarize_tool.execute(
            content=content_to_summarize,
            topic=topic
        )
        final_summary = summary_result if isinstance(summary_result, str) else str(summary_result)
    else:
        final_summary = f"Explored {topic} with {len(collected_sources)} sources"
    
    # Write to KG with proper summary and sources
    add_tool = self.tool_registry.get("add_to_kg")
    if add_tool:
        await add_tool.execute(
            topic=topic,
            content=final_summary[:2000],
            source_urls=collected_sources,
            metadata={"depth": 5, "quality": 5.0 + len(collected_sources)}
        )
```

**Step 4: Remove duplicate KG write at max iterations**

Delete lines 316-324 (the second add_tool.execute call at max iterations).

**Step 5: Commit**

```bash
git add core/agents/explore_agent.py
git commit -m "fix: ExploreAgent collects sources and uses llm_summarize for KG write"
```

---

## Task 4: Remove Duplicate KG Write from ExploreDaemon

**Files:**
- Modify: `core/daemon/explore_daemon.py:105-123`

**Step 1: Remove KG write from ExploreDaemon**

```python
# Change lines 108-123 from:
if result.success:
    self.queue_storage.mark_done(item_id, self.explore_agent.holder_id)
    try:
        import core.knowledge_graph_compat as kg
        await kg.add_knowledge_async(...)  # REMOVE THIS
    except Exception as kg_err:
        ...
    return

# To:
if result.success:
    self.queue_storage.mark_done(item_id, self.explore_agent.holder_id)
    # KG write now handled by ExploreAgent internally
    logger.info(f"ExploreDaemon: completed item {item_id}")
    return
```

**Step 2: Verify no asyncio.run() needed**

The ExploreAgent._react_loop handles KG write via add_to_kg tool, no need for daemon to write.

**Step 3: Commit**

```bash
git add core/daemon/explore_daemon.py
git commit -m "refactor: Remove duplicate KG write from ExploreDaemon (handled by ExploreAgent)"
```

---

## Task 5: Update ExploreAgent System Prompt

**Files:**
- Modify: `core/agents/explore_agent.py:15-50`

**Step 1: Update prompt to emphasize source collection and summary generation**

```python
DEFAULT_SYSTEM_PROMPT = """You are an ExploreAgent that autonomously explores knowledge topics.

Your workflow for each topic:
1. Search the web for the topic using search_web
2. For each promising URL, use fetch_page to get full content
3. Use llm_analyze to judge if content is useful for this topic
4. Collect useful source URLs for attribution
5. At the end, use llm_summarize to generate a knowledge summary
6. The system will automatically write to KG with your collected sources

Available tools:
- search_web: Search the web (returns title, snippet, URL)
- fetch_page: Fetch full content from a URL (track this URL as a source!)
- llm_analyze: Analyze content quality and relevance
- llm_summarize: Summarize collected content into knowledge
- query_kg: Query existing knowledge

Important rules:
- ALWAYS fetch_page for URLs that look relevant before judging
- Track URLs from successful fetch_page calls (these become sources)
- Use llm_analyze to judge content usefulness
- If no useful content found, report what you tried
- DO NOT hallucinate knowledge without sources

The system will write your summary to KG with collected sources when done.
"""
```

**Step 2: Commit**

```bash
git add core/agents/explore_agent.py
git commit -m "docs: Update ExploreAgent prompt for source collection workflow"
```

---

## Task 6: Integration Test

**Files:**
- Create: Manual test via API

**Step 1: Restart services**

```bash
bash start.sh
```

**Step 2: Inject test topic**

```bash
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"Python asyncio best practices"}'
```

**Step 3: Wait for exploration and verify KG node**

```bash
sleep 60
curl http://localhost:4848/api/kg/nodes/Python%20asyncio%20best%20practices
```

**Expected:** Node should have:
- `content`: A proper summary (not "Thought: I need to...")
- `source_urls`: At least 1-2 URLs from fetch_page calls
- `quality`: > 5.0 (based on source count)

**Step 4: Verify via Neo4j direct query**

```python
python3 -c "
import asyncio
from core.kg.neo4j_client import Neo4jClient
import os

async def check():
    client = Neo4jClient('bolt://localhost:7687', 'neo4j', os.environ.get('NEO4J_PASSWORD'))
    await client.connect()
    result = await client.execute_query('MATCH (n:Knowledge) WHERE n.topic CONTAINS \"asyncio\" RETURN n.topic, n.content, n.source_urls')
    for r in result:
        print(f'Topic: {r[\"n.topic\"]}')
        print(f'Content: {r[\"n.content\"][:100]}...')
        print(f'Sources: {r[\"n.source_urls\"]}')
    await client.disconnect()

asyncio.run(check())
"
```

**Step 5: Final commit if tests pass**

```bash
git push origin main
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | AddToKGTool gains source_urls parameter |
| 2 | add_knowledge_async passes sources to KG |
| 3 | ExploreAgent collects sources during loop |
| 4 | Remove duplicate write from ExploreDaemon |
| 5 | Update system prompt |
| 6 | Integration test |

**Estimated effort:** 6 tasks, ~30 minutes each