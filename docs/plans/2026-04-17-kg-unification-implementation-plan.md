# KG数据源统一实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将CA项目的KG和Queue系统统一到单一数据源（Neo4j + SQLite），删除遗留的state.json双写架构。

**Architecture:** 废弃Explorer和knowledge_graph.py，统一使用ExploreAgent + KGRepositoryFactory，重构20+API端点，迁移state.json数据到Neo4j。

**Tech Stack:** Python, Neo4j (bolt://localhost:7687), SQLite, Flask, pytest

---

## Phase 1: 基础设施准备

### Task 1: KGRepositoryFactory新增同步方法

**Files:**
- Modify: `core/kg/repository_factory.py:40-76`
- Test: `tests/core/kg/test_repository_factory.py`

**Step 1: Write the failing tests**

```python
# tests/core/kg/test_repository_factory.py 新增测试类

class TestKGRepositoryFactoryAPIMethods:
    """测试为API端点新增的同步方法"""
    
    def test_get_all_nodes_sync_returns_list(self):
        """get_all_nodes_sync应返回节点列表"""
        from core.kg.repository_factory import get_kg_factory
        factory = get_kg_factory()
        nodes = factory.get_all_nodes_sync(limit=10)
        assert isinstance(nodes, list)
    
    def test_get_all_relations_sync_returns_list(self):
        """get_all_relations_sync应返回关系列表"""
        from core.kg.repository_factory import get_kg_factory
        factory = get_kg_factory()
        relations = factory.get_all_relations_sync()
        assert isinstance(relations, list)
    
    def test_get_stats_sync_returns_dict(self):
        """get_stats_sync应返回统计字典"""
        from core.kg.repository_factory import get_kg_factory
        factory = get_kg_factory()
        stats = factory.get_stats_sync()
        assert "total_nodes" in stats
        assert "by_status" in stats
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/kg/test_repository_factory.py::TestKGRepositoryFactoryAPIMethods -v`
Expected: FAIL with "AttributeError: 'KGRepositoryFactory' object has no attribute 'get_all_nodes_sync'"

**Step 3: Write minimal implementation**

```python
# core/kg/repository_factory.py 新增方法

class KGRepositoryFactory:
    # ... 现有方法 ...
    
    def get_all_nodes_sync(self, limit: int = 100, offset: int = 0) -> list:
        """获取所有知识节点（分页）"""
        async def _get():
            repo = await self._ensure_connected()
            query = """
            MATCH (k:Knowledge)
            RETURN k.topic as topic, k.summary as summary, k.status as status, 
                   k.quality as quality, k.depth as depth
            ORDER BY k.created_at DESC
            SKIP $offset LIMIT $limit
            """
            results = await self._client.execute_query(query, offset=offset, limit=limit)
            return [dict(r) for r in results]
        return asyncio.run(_get())
    
    def get_all_relations_sync(self) -> list:
        """获取所有关系"""
        async def _get():
            repo = await self._ensure_connected()
            query = """
            MATCH (a:Knowledge)-[r]->(b:Knowledge)
            RETURN a.topic as source, b.topic as target, type(r) as relation_type
            """
            results = await self._client.execute_query(query)
            return [dict(r) for r in results]
        return asyncio.run(_get())
    
    def get_stats_sync(self) -> dict:
        """获取KG统计"""
        async def _get():
            repo = await self._ensure_connected()
            query = """
            MATCH (k:Knowledge)
            RETURN count(k) as total_nodes,
                   sum(CASE WHEN k.status = 'done' THEN 1 ELSE 0 END) as done_count,
                   sum(CASE WHEN k.status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                   sum(CASE WHEN k.status = 'exploring' THEN 1 ELSE 0 END) as exploring_count
            """
            result = await self._client.execute_query(query)
            stats = result[0] if result else {}
            
            # 获取关系统计
            rel_query = "MATCH ()-[r]->() RETURN count(r) as total_relations"
            rel_result = await self._client.execute_query(rel_query)
            stats["total_relations"] = rel_result[0]["total_relations"] if rel_result else 0
            
            return {
                "total_nodes": stats.get("total_nodes", 0),
                "by_status": {
                    "done": stats.get("done_count", 0),
                    "pending": stats.get("pending_count", 0),
                    "exploring": stats.get("exploring_count", 0)
                },
                "total_relations": stats.get("total_relations", 0)
            }
        return asyncio.run(_get())
    
    def get_graph_overview_sync(self) -> dict:
        """获取完整图结构（前端显示用）"""
        nodes = self.get_all_nodes_sync(limit=500)
        edges = self.get_all_relations_sync()
        return {"nodes": nodes, "edges": edges}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/kg/test_repository_factory.py::TestKGRepositoryFactoryAPIMethods -v`
Expected: PASS (如果Neo4j可用) 或需要mock

**Step 5: Commit**

```bash
git add core/kg/repository_factory.py tests/core/kg/test_repository_factory.py
git commit -m "feat(kg): add sync wrapper methods for API endpoints"
```

---

### Task 2: 新增引用提取工具

**Files:**
- Create: `core/tools/citation_tools.py`
- Modify: `core/tools/__init__.py`
- Test: `tests/tools/test_citation_tools.py`

**Step 1: Write the failing tests**

```python
# tests/tools/test_citation_tools.py

import pytest

class TestExtractPaperCitationsTool:
    """测试论文引用提取工具"""
    
    def test_tool_name_is_correct(self):
        """工具名称应为 extract_paper_citations"""
        from core.tools.citation_tools import ExtractPaperCitationsTool
        tool = ExtractPaperCitationsTool()
        assert tool.name == "extract_paper_citations"
    
    def test_extract_doi_from_content(self):
        """应从内容中提取DOI"""
        from core.tools.citation_tools import ExtractPaperCitationsTool
        tool = ExtractPaperCitationsTool()
        content = "See Smith et al. (2023) doi:10.1234/arxiv.2023.001 for details"
        result = asyncio.run(tool.execute(content=content, topic="test"))
        assert "10.1234/arxiv.2023.001" in result

class TestExtractWebCitationsTool:
    """测试网页引用提取工具"""
    
    def test_tool_name_is_correct(self):
        """工具名称应为 extract_web_citations"""
        from core.tools.citation_tools import ExtractWebCitationsTool
        tool = ExtractWebCitationsTool()
        assert tool.name == "extract_web_citations"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_citation_tools.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'core.tools.citation_tools'"

**Step 3: Create citation_tools.py**

```python
# core/tools/citation_tools.py

"""引用提取工具 - 从论文和网页内容提取引用关系"""

import asyncio
import re
import json
from typing import Any

from core.tools.base import Tool


class ExtractPaperCitationsTool(Tool):
    """从论文内容提取引用关系"""
    
    @property
    def name(self) -> str:
        return "extract_paper_citations"
    
    @property
    def description(self) -> str:
        return "Extract citation relationships (DOI, arxiv IDs) from paper content"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Paper content to analyze"},
                "topic": {"type": "string", "description": "Current topic being explored"}
            },
            "required": ["content"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        content = kwargs.get("content", "")
        topic = kwargs.get("topic", "")
        
        citations = []
        
        # 提取DOI
        doi_pattern = r'doi[:\s]+([10]\.\d{4}/[^\s]+)'
        dois = re.findall(doi_pattern, content, re.IGNORECASE)
        citations.extend [{"type": "doi", "id": doi} for doi in dois]
        
        # 提取Arxiv ID
        arxiv_pattern = r'arxiv[:\s]+(\d{4}\.\d{4,5})'
        arxiv_ids = re.findall(arxiv_pattern, content, re.IGNORECASE)
        citations.extend [{"type": "arxiv", "id": arxiv_id} for arxiv_id in arxiv_ids]
        
        return json.dumps({
            "topic": topic,
            "citations": citations,
            "count": len(citations)
        })


class ExtractWebCitationsTool(Tool):
    """从网页内容提取引用链接"""
    
    @property
    def name(self) -> str:
        return "extract_web_citations"
    
    @property
    def description(self) -> str:
        return "Extract citation links and references from web page content"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Web page content"},
                "topic": {"type": "string", "description": "Current topic"}
            },
            "required": ["content"]
        }
    
    async def execute(self, **kwargs: Any) -> str:
        content = kwargs.get("content", "")
        topic = kwargs.get("topic", "")
        
        # 提取URL链接
        url_pattern = r'https?://[^\s<>"]+'
        urls = re.findall(url_pattern, content)
        
        # 过滤常见域名
        domains_to_skip = ['google.com', 'facebook.com', 'twitter.com', 'linkedin.com']
        filtered_urls = [
            url for url in urls 
            if not any(skip in url for skip in domains_to_skip)
        ]
        
        return json.dumps({
            "topic": topic,
            "links": filtered_urls[:20],
            "count": len(filtered_urls)
        })
```

**Step 4: Register tools**

```python
# core/tools/__init__.py 添加

from core.tools.citation_tools import ExtractPaperCitationsTool, ExtractWebCitationsTool

ALL_TOOLS = [
    # ... 现有工具 ...
    ExtractPaperCitationsTool,
    ExtractWebCitationsTool,
]
```

**Step 5: Run test**

Run: `pytest tests/tools/test_citation_tools.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add core/tools/citation_tools.py core/tools/__init__.py tests/tools/test_citation_tools.py
git commit -m "feat(tools): add citation extraction tools for ExploreAgent"
```

---

### Task 3: 更新ExploreAgent工具列表

**Files:**
- Modify: `core/agents/explore_agent.py:52-67`

**Step 1: Add new tools to DEFAULT_TOOLS**

```python
# core/agents/explore_agent.py

DEFAULT_TOOLS = [
    "search_web",
    "query_kg",
    "add_to_kg",
    "claim_queue",
    "mark_done",
    "get_queue",
    "llm_analyze",
    "llm_summarize",
    "fetch_page",
    "process_paper",
    "extract_paper_citations",  # 新增
    "extract_web_citations",    # 新增
    "update_kg_status",
    "update_kg_metadata",
    "get_node_relations",
    "add_to_queue",
]
```

**Step 2: Verify import works**

Run: `python3 -c "from core.agents.explore_agent import DEFAULT_TOOLS; print(len(DEFAULT_TOOLS))"`
Expected: 16

**Step 3: Commit**

```bash
git add core/agents/explore_agent.py
git commit -m "feat(explore-agent): add citation extraction tools to tool list"
```

---

## Phase 2: 数据迁移脚本

### Task 4: 创建迁移脚本

**Files:**
- Create: `scripts/migrate_state_to_neo4j.py`
- Create: `scripts/rollback_migration.py`

**Step 1: Write migration script**

```python
# scripts/migrate_state_to_neo4j.py

"""
一次性迁移: knowledge/state.json → Neo4j

用法:
    python scripts/migrate_state_to_neo4j.py --dry-run  # 预览
    python scripts/migrate_state_to_neo4j.py --execute  # 执行
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
from neo4j import GraphDatabase


class StateToNeo4jMigrator:
    def __init__(self, uri: str, user: str, password: str, state_file: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.state_file = Path(state_file)
        
    def load_state(self) -> dict:
        """加载state.json"""
        if not self.state_file.exists():
            raise FileNotFoundError(f"State file not found: {self.state_file}")
        with open(self.state_file) as f:
            return json.load(f)
    
    def migrate_topics(self, topics: dict) -> int:
        """迁移知识节点"""
        count = 0
        with self.driver.session() as session:
            for topic_name, node_data in topics.items():
                session.execute_write(self._create_node, topic_name, node_data)
                count += 1
        return count
    
    def _create_node(self, tx, topic: str, data: dict):
        """创建单个Knowledge节点"""
        query = """
        MERGE (k:Knowledge {topic: $topic})
        SET k.summary = $summary,
            k.status = $status,
            k.quality = $quality,
            k.depth = $depth,
            k.sources = $sources,
            k.explore_count = $explore_count,
            k.created_at = datetime(),
            k.updated_at = datetime()
        """
        tx.run(query, {
            "topic": topic,
            "summary": data.get("summary", ""),
            "status": data.get("status", "unexplored"),
            "quality": data.get("quality", 0) or 0,
            "depth": data.get("depth", 0) or 0,
            "sources": data.get("sources", []),
            "explore_count": data.get("explore_count", 0) or 0
        })
    
    def migrate_relations(self, topics: dict) -> int:
        """迁移关系"""
        count = 0
        with self.driver.session() as session:
            for parent, data in topics.items():
                # 父子关系
                for child in data.get("children", []):
                    if child in topics:  # 确保目标节点存在
                        session.execute_write(self._create_relation, parent, child, "IS_CHILD_OF")
                        count += 1
                # 引用关系
                for cited in data.get("cites", []):
                    if cited in topics:
                        session.execute_write(self._create_relation, parent, cited, "CITES")
                        count += 1
        return count
    
    def _create_relation(self, tx, source: str, target: str, rel_type: str):
        """创建关系"""
        query = f"""
        MATCH (a:Knowledge {{topic: $source}})
        MATCH (b:Knowledge {{topic: $target}})
        MERGE (a)-[:{rel_type}]->(b)
        """
        tx.run(query, {"source": source, "target": target})
    
    def migrate_queue(self, queue: list) -> int:
        """迁移队列到SQLite"""
        from core.tools.queue_tools import QueueStorage
        storage = QueueStorage()
        storage.initialize()
        
        count = 0
        for item in queue:
            if item.get("status") != "done":  # 只迁移未完成的
                storage.add_item(
                    topic=item["topic"],
                    priority=item.get("score", 5.0),
                    metadata={"reason": item.get("reason", "")}
                )
                count += 1
        return count
    
    def verify(self, expected_topics: int) -> dict:
        """验证迁移"""
        with self.driver.session() as session:
            result = session.execute_read(lambda tx: 
                tx.run("MATCH (k:Knowledge) RETURN count(k) as count").single())
            neo4j_count = result["count"]
        
        return {
            "expected": expected_topics,
            "actual": neo4j_count,
            "success": neo4j_count == expected_topics
        }
    
    def close(self):
        self.driver.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate state.json to Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--execute", action="store_true", help="Execute migration")
    parser.add_argument("--neo4j-uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.environ.get("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.environ.get("NEO4J_PASSWORD", ""))
    parser.add_argument("--state-file", default="knowledge/state.json")
    args = parser.parse_args()
    
    migrator = StateToNeo4jMigrator(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password,
        state_file=args.state_file
    )
    
    try:
        state = migrator.load_state()
        topics = state.get("knowledge", {}).get("topics", {})
        queue = state.get("curiosity_queue", [])
        
        print(f"📊 Topics to migrate: {len(topics)}")
        print(f"📊 Queue items to migrate: {len(queue)}")
        
        if args.dry_run:
            print("✅ Dry run complete - no changes made")
            return
        
        if not args.execute:
            print("❌ Must specify --execute or --dry-run")
            return
        
        # 执行迁移
        print("🔄 Migrating topics...")
        topic_count = migrator.migrate_topics(topics)
        print(f"✅ Migrated {topic_count} topics")
        
        print("🔄 Migrating relations...")
        rel_count = migrator.migrate_relations(topics)
        print(f"✅ Migrated {rel_count} relations")
        
        print("🔄 Migrating queue...")
        queue_count = migrator.migrate_queue(queue)
        print(f"✅ Migrated {queue_count} queue items")
        
        # 验证
        print("🔍 Verifying...")
        verification = migrator.verify(len(topics))
        if verification["success"]:
            print(f"✅ Verification passed: {verification['actual']} nodes in Neo4j")
        else:
            print(f"❌ Verification failed: expected {verification['expected']}, got {verification['actual']}")
        
        print("✅ Migration complete")
        
    finally:
        migrator.close()


if __name__ == "__main__":
    main()
```

**Step 2: Write rollback script**

```python
# scripts/rollback_migration.py

"""回滚迁移: 从Neo4j恢复到state.json"""

import json
import os
from pathlib import Path
from neo4j import GraphDatabase


def rollback():
    """从Neo4j导出数据恢复到state.json"""
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    try:
        with driver.session() as session:
            # 导出所有节点
            nodes_result = session.execute_read(lambda tx:
                tx.run("MATCH (k:Knowledge) RETURN k").values())
            
            topics = {}
            for row in nodes_result:
                node = row[0]
                topics[node["topic"]] = {
                    "summary": node.get("summary", ""),
                    "status": node.get("status", "unexplored"),
                    "quality": node.get("quality", 0),
                    "depth": node.get("depth", 0),
                    "sources": node.get("sources", []),
                    "explore_count": node.get("explore_count", 0),
                    "children": [],
                    "cites": []
                }
            
            # 导出关系
            rels_result = session.execute_read(lambda tx:
                tx.run("""
                MATCH (a:Knowledge)-[r]->(b:Knowledge)
                RETURN a.topic as source, b.topic as target, type(r) as rel_type
                """).values())
            
            for row in rels_result:
                source, target, rel_type = row
                if source in topics:
                    if rel_type == "IS_CHILD_OF":
                        topics[source]["children"].append(target)
                    elif rel_type == "CITES":
                        topics[source]["cites"].append(target)
            
            # 写入state.json
            state = {
                "version": "1.0",
                "knowledge": {"topics": topics},
                "curiosity_queue": [],
                "exploration_log": []
            }
            
            backup_path = Path("knowledge/state.json.rollback")
            with open(backup_path, "w") as f:
                json.dump(state, f, indent=2)
            
            print(f"✅ Rollback complete: {backup_path}")
            print(f"📊 Restored {len(topics)} topics")
            
    finally:
        driver.close()


if __name__ == "__main__":
    rollback()
```

**Step 3: Test migration script (dry-run)**

Run: `python scripts/migrate_state_to_neo4j.py --dry-run`
Expected: 显示预览数据

**Step 4: Commit**

```bash
git add scripts/migrate_state_to_neo4j.py scripts/rollback_migration.py
git commit -m "feat(migration): add state.json to Neo4j migration scripts"
```

---

## Phase 3: API端点重构

### Task 5: 重构 /api/kg/stats

**Files:**
- Modify: `curious_api.py:1428-1467`

**Step 1: Write failing test**

```python
# tests/api/test_kg_api.py 新增

class TestKGStatsEndpoint:
    """测试KG统计端点"""
    
    def test_stats_returns_neo4j_data(self, client):
        """stats端点应返回Neo4j数据"""
        response = client.get('/api/kg/stats')
        assert response.status_code == 200
        data = response.get_json()
        assert "total_nodes" in data
        assert "by_status" in data
```

**Step 2: Refactor endpoint**

```python
# curious_api.py 替换 line 1428-1467

@app.route("/api/kg/stats")
def api_kg_stats():
    """Get KG statistics summary from Neo4j."""
    try:
        from core.kg.repository_factory import get_kg_factory
        
        kg_factory = get_kg_factory()
        stats = kg_factory.get_stats_sync()
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

**Step 3: Run test**

Run: `pytest tests/api/test_kg_api.py::TestKGStatsEndpoint -v`

**Step 4: Commit**

```bash
git add curious_api.py tests/api/test_kg_api.py
git commit -m "refactor(api): /api/kg/stats now queries Neo4j"
```

---

### Task 6: 重构 /api/kg/overview

**Files:**
- Modify: `curious_api.py:1118-1130`

**Step 1: Refactor endpoint**

```python
# curious_api.py 替换 line 1118-1130

@app.route("/api/kg/overview")
def api_kg_overview():
    """Get KG overview for frontend visualization."""
    try:
        from core.kg.repository_factory import get_kg_factory
        
        kg_factory = get_kg_factory()
        overview = kg_factory.get_graph_overview_sync()
        
        return jsonify({
            "status": "ok",
            "nodes": overview["nodes"],
            "edges": overview["edges"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

**Step 2: Test**

Run: `curl http://localhost:4848/api/kg/overview`

**Step 3: Commit**

```bash
git add curious_api.py
git commit -m "refactor(api): /api/kg/overview now queries Neo4j"
```

---

### Task 7-15: 批量重构其他KG端点

**按照相同模式重构以下端点：**

| Task | 端点 | 新实现 |
|------|------|--------|
| 7 | `/api/kg/nodes` | `kg_factory.get_all_nodes_sync()` |
| 8 | `/api/kg/nodes/<id>` | `kg_factory.get_node_sync(id)` |
| 9 | `/api/kg/edges` | `kg_factory.get_all_relations_sync()` |
| 10 | `/api/kg/dormant` | `kg_factory.query_by_status_sync("dormant")` |
| 11 | `/api/kg/confidence/<topic>` | `kg_factory.get_node_sync(topic)` |
| 12 | `/api/kg/frontier` | 新增方法 |
| 13 | `/api/knowledge/confidence` | 替换R1D3ToolHandler为kg_factory |
| 14 | `/api/curious/queue/pending` | 使用QueueStorage |
| 15 | 废弃 `/api/curious/state` | 返回提示或合并到overview |

**每个端点单独commit：**

```bash
git commit -m "refactor(api): /api/kg/nodes now queries Neo4j"
git commit -m "refactor(api): /api/kg/edges now queries Neo4j"
# ... 等等
```

---

## Phase 4: 探索器统一

### Task 16: 替换curious_agent.py中的Explorer

**Files:**
- Modify: `curious_agent.py:25, 92, 161, 167`

**Step 1: Replace Explorer import**

```python
# curious_agent.py line 25 替换

# 旧: from core.explorer import Explorer
# 新: from core.agents.explore_agent import ExploreAgent, ExploreAgentConfig
```

**Step 2: Replace Explorer usage in run_explore**

```python
# curious_agent.py line 92 替换

# 旧: parent_explorer = Explorer(exploration_depth=depth)
#     parent_result = parent_explorer.explore(...)
# 新: 使用ExploreAgent或直接用kg_factory
```

**Step 3: Verify imports work**

Run: `python3 -c "from curious_agent import run_explore"`

**Step 4: Commit**

```bash
git add curious_agent.py
git commit -m "refactor(agent): replace Explorer with ExploreAgent in curious_agent.py"
```

---

## Phase 5: 清理遗留代码

### Task 17: 删除knowledge_graph.py

**Files:**
- Delete: `core/knowledge_graph.py`
- Delete: `tests/test_knowledge_graph.py`

**Step 1: Verify no remaining imports**

Run: `grep -rn "from core import knowledge_graph\|import knowledge_graph" --include="*.py" | grep -v "^tests/" | grep -v "^scripts/"`

Expected: 无匹配（或仅迁移脚本）

**Step 2: Delete files**

```bash
rm core/knowledge_graph.py tests/test_knowledge_graph.py
```

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: delete legacy knowledge_graph.py (~1700 lines)"
```

---

### Task 18: 删除Explorer相关文件

**Files:**
- Delete: `core/explorer.py`
- Delete: `core/three_phase_explorer.py`
- Delete: `core/async_explorer.py`
- Delete: `tests/test_explorer_layers.py`

**Step 1: Delete files**

```bash
rm core/explorer.py core/three_phase_explorer.py core/async_explorer.py tests/test_explorer_layers.py
```

**Step 2: Commit**

```bash
git add -A
git commit -m "chore: delete legacy Explorer (~900 lines total)"
```

---

### Task 19: 删除遗留仓库系统

**Files:**
- Delete: `core/repository/` 目录

**Step 1: Delete directory**

```bash
rm -rf core/repository/
```

**Step 2: Commit**

```bash
git add -A
git commit -m "chore: delete legacy repository directory (~500 lines)"
```

---

## Phase 6: 上线验证

### Task 20: 运行完整测试套件

**Step 1: Run all tests**

Run: `pytest tests/ -x --ignore=tests/integration --ignore=tests/e2e -v`

Expected: 所有测试通过

**Step 2: Run migration**

Run: `python scripts/migrate_state_to_neo4j.py --execute`

**Step 3: Test daemon mode**

Run: `python curious_agent.py --daemon --interval 60` (短间隔测试)

**Step 4: Test API endpoints**

Run: `curl http://localhost:4848/api/kg/stats`
Run: `curl http://localhost:4848/api/kg/overview`

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat(kg): complete unification - Neo4j single data source"
```

---

## 执行选择

**计划完成并保存到 `docs/plans/2026-04-17-kg-unification-implementation-plan.md`。**

**两种执行方式：**

1. **Subagent-Driven (本session)** - 每个Task派发新subagent，任务间review，快速迭代

2. **Parallel Session (新session)** - 在worktree中开新session，批量执行带checkpoint

**您选择哪种方式？**