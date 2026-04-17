# KG数据源统一设计文档

> 设计日期: 2026-04-17
> 设计者: Sisyphus (基于用户需求)
> 目标: 将KG和Queue系统统一到单一数据源

---

## 1. 问题背景

### 1.1 当前架构问题

CA项目存在**双数据源架构**，导致数据不一致和代码混乱：

| 系统 | 当前数据源 | 问题 |
|------|-----------|------|
| KG (知识图谱) | Neo4j + state.json | 双写不同步 |
| Queue (好奇心队列) | SQLite + state.json | 双写不同步 |

**具体表现**：

- `Explorer` (687行) → 写入 state.json
- `ExploreAgent` (380行) → 写入 Neo4j (通过KG工具)
- OpenClaw Hooks → 查询 Neo4j
- WebUI前端 → 查询 state.json
- API端点 (20+) → 查询 state.json，只有2个查询Neo4j

### 1.2 用户需求

| 需求项 | 选择 |
|--------|------|
| KG主存储 | Neo4j |
| Queue主存储 | SQLite |
| state.json处理 | 迁移并废弃 |
| 前端显示 | 实时查询Neo4j |

---

## 2. 目标架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TARGET: Single Data Source Architecture               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    ExploreAgent (唯一探索器)                          │  │
│   │                    ┌─────────────────────────────────────┐           │  │
│   │                    │   ReAct Loop + Tool Registry        │           │  │
│   │                    │   - search_web                      │           │  │
│   │                    │   - fetch_page                      │           │  │
│   │                    │   - process_paper                   │           │  │
│   │                    │   - extract_citations (新增)        │           │  │
│   │                    │   - query_kg                        │           │  │
│   │                    │   - add_to_kg                       │           │  │
│   │                    │   - claim_queue                     │           │  │
│   │                    │   - mark_done                       │           │  │
│   │                    └─────────────────────────────────────┘           │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    ↓                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         KGRepositoryFactory                          │  │
│   │                         (单入口访问KG)                                │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    ↓                                        │
│   ┌───────────────────────────┐         ┌───────────────────────────┐     │
│   │        Neo4j              │         │      SQLite Queue         │     │
│   │   bolt://localhost:7687   │         │    knowledge/queue.db     │     │
│   │                           │         │                           │     │
│   │   - Knowledge nodes       │         │   - Queue items           │     │
│   │   - Relations             │         │   - Claims                │     │
│   │   - Metadata              │         │   - Status                │     │
│   │   - Confidence            │         │                           │     │
│   └───────────────────────────┘         └───────────────────────────┘     │
│                                                                             │
│   WebUI / API / Hooks / Daemon → 全部通过KGRepositoryFactory访问           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据存储统一

### 3.1 数据类型归属

| 数据类型 | 目标存储 | Neo4j节点/关系 |
|----------|----------|---------------|
| 知识节点 | Neo4j | `Knowledge`节点 |
| 父子关系 | Neo4j | `IS_CHILD_OF`关系 |
| 引用关系 | Neo4j | `CITES`关系 |
| 元数据 (quality, confidence等) | Neo4j | Knowledge节点属性 |
| 队列项 | SQLite | queue_items表 |
| 探索日志 | Neo4j | Knowledge节点属性或ExplorationLog节点 |
| 根技术池 | Neo4j | `RootCandidate`节点 |
| Dream洞察 | Neo4j | `DreamInsight`节点 |

### 3.2 Neo4j Schema设计

```cypher
// Knowledge节点 (主节点)
CREATE (k:Knowledge {
  topic: string,           // 主键
  summary: string,         // 摘要
  status: string,          // pending/exploring/done/dormant
  quality: float,          // 0-10
  confidence: float,       // 0-1
  explore_count: int,      // 探索次数
  depth: int,              // 深度层级
  sources: list<string>,   // 来源URLs
  created_at: timestamp,
  updated_at: timestamp
})

// 关系类型
-[:IS_CHILD_OF]->    // 分解关系
-[:CITES]->          // 引用关系
-[:CITED_BY]->       // 反向引用
-[:EXPLAINS]->       // 解释关系

// 辅助节点
CREATE (r:RootCandidate {
  name: string,
  score: float,
  cross_domain_count: int
})

CREATE (d:DreamInsight {
  topic: string,
  insight: string,
  generated_at: timestamp
})
```

---

## 4. 代码删除计划

### 4.1 删除文件清单

| 文件/目录 | 行数 | 删除原因 |
|-----------|------|----------|
| `core/explorer.py` | 687 | 遗留探索器，写state.json |
| `core/three_phase_explorer.py` | ~200 | Explorer的包装 |
| `core/knowledge_graph.py` | 1699 | 遗留KG操作，写state.json |
| `core/repository/json_repository.py` | ~300 | 遗留JSON仓库 |
| `core/repository/base.py` | ~100 | 仓库基类 |
| `core/repository/__init__.py` | ~50 | 仓库入口 |
| `tests/test_explorer*.py` | ~300 | Explorer测试 |
| `tests/test_knowledge_graph.py` | ~200 | KG测试 |

**总计删除：约3500行代码**

### 4.2 删除顺序

```
Phase 1: 替换引用（不删除文件）
  └── 替换curious_agent.py中Explorer → ExploreAgent
  └── 替换curious_api.py中kg → kg_factory
  └── 运行测试验证

Phase 2: 删除测试
  └── 删除test_explorer*.py
  └── 删除test_knowledge_graph.py
  └── 更新test_integration.py

Phase 3: 删除主文件
  └── 删除core/explorer.py
  └── 删除core/three_phase_explorer.py
  └── 删除core/knowledge_graph.py
  └── 删除core/repository/目录

Phase 4: 清理残留
  └── 检查是否有遗漏import
  └── 运行完整测试
  └── 提交变更
```

---

## 5. 功能迁移

### 5.1 引用提取器迁移

| 源文件 | 功能 | 目标 |
|--------|------|------|
| `core/paper_citation_extractor.py` | 论文引用提取 | 新工具 `extract_paper_citations` |
| `core/web_citation_extractor.py` | 网页引用提取 | 新工具 `extract_web_citations` |

### 5.2 新增工具

**新文件: `core/tools/citation_tools.py`**

```python
class ExtractPaperCitationsTool(Tool):
    """从PDF内容提取论文引用关系"""
    name = "extract_paper_citations"
    
class ExtractWebCitationsTool(Tool):
    """从网页内容提取引用链接"""
    name = "extract_web_citations"
```

### 5.3 ExploreAgent工具集更新

```python
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

---

## 6. API端点重构

### 6.1 KG端点重构

| 端点 | 当前实现 | 新实现 |
|------|----------|--------|
| `GET /api/kg/nodes` | `kg.get_state()["topics"]` | `kg_factory.query_knowledge_sync()` |
| `GET /api/kg/nodes/<id>` | `state["topics"][id]` | `kg_factory.get_node_sync(id)` |
| `GET /api/kg/edges` | 遍历topics.children | `kg_factory.get_all_relations_sync()` |
| `GET /api/kg/overview` | `kg.get_kg_overview()` | `kg_factory.get_graph_overview_sync()` |
| `GET /api/kg/stats` | 遍历topics统计 | `kg_factory.get_stats_sync()` |
| `GET /api/kg/confidence/<topic>` | `kg.get_meta_cognitive()` | `kg_factory.get_confidence_sync(topic)` |

### 6.2 KGRepositoryFactory新增方法

```python
# 新增同步包装方法
def get_all_nodes_sync(paginate, limit) -> list
def get_all_relations_sync() -> list
def get_graph_overview_sync() -> dict
def get_stats_sync() -> dict
def get_subgraph_sync(root, depth) -> dict
def get_activation_trace_sync(topic) -> dict
def get_root_candidates_sync() -> list
def query_by_status_sync(status) -> list
def get_confidence_sync(topic) -> dict
def get_frontier_sync() -> list
def promote_root_sync(topic) -> bool
def get_dream_insights_sync() -> list
def add_relation_sync(parent, child, type) -> bool
```

### 6.3 废弃端点

| 端点 | 处理方式 |
|------|----------|
| `GET /api/curious/state` | 废弃或合并到`/api/kg/overview` |
| `GET /api/kg/calibration` | 废弃 |

---

## 7. 数据迁移脚本

### 7.1 迁移流程

```
Step 1: 备份现有数据
  ├── cp knowledge/state.json knowledge/state.json.backup

Step 2: 确认Neo4j可用
  ├── python scripts/check_neo4j_connection.py

Step 3: 运行迁移
  ├── python scripts/migrate_state_to_neo4j.py
  ├── 观察进度日志
  ├── 验证迁移结果

Step 4: 清理旧数据（可选）
  ├── mv knowledge/state.json knowledge/state.json.migrated
```

### 7.2 迁移脚本使用

```bash
# 预览
python scripts/migrate_state_to_neo4j.py --dry-run

# 执行
python scripts/migrate_state_to_neo4j.py --execute
```

### 7.3 回滚方案

```bash
python scripts/rollback_migration.py
```

---

## 8. 测试更新

### 8.1 需删除的测试

- `tests/test_explorer_layers.py`
- `tests/test_knowledge_graph.py`
- `tests/test_arxiv_analyzer.py`

### 8.2 需新增的测试

- `tests/tools/test_citation_tools.py`
- `tests/api/test_kg_api.py`
- `tests/kg/test_repository_factory_api.py`
- `tests/integration/test_explore_agent_flow.py`

### 8.3 测试策略

- 使用Neo4j测试容器或JSONKGRepository fallback
- 取消现有测试的skip标记
- 去掉MockKGRepository，使用真实实现

---

## 9. 实施策略

### 9.1 实施阶段

| 阶段 | 内容 | 时间 |
|------|------|------|
| Phase 1 | 基础设施准备（KGRepositoryFactory新方法、引用工具） | Day 1-2 |
| Phase 2 | 数据迁移 | Day 3 |
| Phase 3 | API重构 | Day 4-5 |
| Phase 4 | 探索器统一 | Day 6-7 |
| Phase 5 | 清理遗留代码 | Day 8 |
| Phase 6 | 上线验证 | Day 9 |

### 9.2 版本控制策略

```
main
  │
  ├── feature/kg-unification (开发分支)
  │     │
  │     ├── phase-1-infrastructure
  │     ├── phase-2-migration
  │     ├── phase-3-api-refactor
  │     ├── phase-4-explorer-unify
  │     ├── phase-5-cleanup
  │     │
  │     └── → merge到main (Phase 6后)
```

### 9.3 发布检查清单

- [ ] Neo4j服务运行正常
- [ ] 数据迁移完成并验证
- [ ] 所有API端点返回正确
- [ ] ExploreAgent探索成功
- [ ] 前端KG图谱显示正常
- [ ] Hook集成测试通过
- [ ] 无遗留import错误
- [ ] 测试覆盖完整
- [ ] 回滚脚本准备好

---

## 10. 总结

| 项目 | 内容 |
|------|------|
| 目标 | KG+Queue数据源统一到Neo4j |
| 删除代码 | ~3500行 |
| 新增功能 | 2个引用工具，15个KGRepositoryFactory方法 |
| 重构端点 | 20+个API端点 |
| 实施周期 | 9天分6阶段 |