# Bug List v0.3.4 — Comprehensive Analysis & Radical Fix Plan

**日期**: 2026-05-25  
**分析人**: Sisyphus (基于 R1D3-researcher 原诊断 + 架构/错误处理/测试覆盖深度分析)  
**版本**: v0.3.4  
**状态**: Root causes identified for all bugs, comprehensive fix plan drafted

---

## 目录

1. [Bug 分类总览](#bug-分类总览)
2. [P0 级 Bug（立即修复）](#p0-级-bug立即修复)
3. [P1 级 Bug（中期修复）](#p1-级-bug中期修复)
4. [P2 级 Bug（低优先级）](#p2-级-bug低优先级)
5. [系统性架构问题](#系统性架构问题)
6. [彻底修复方案](#彻底修复方案)
7. [验收标准](#验收标准)
8. [修复执行顺序](#修复执行顺序)

---

## Bug 分类总览

| Bug ID | 严重级别 | 类型 | 根因来源 | 影响范围 |
|--------|---------|------|---------|---------|
| #1 | P0 🔴 | 数据完整性 | kg_repository.py:315 | KG 边重复 8.5x |
| #6 | P0 🔴 | 数据完整性 | explore_agent.py + trace | Trace 日志丢失 KG 信息 |
| #7 | P0 🔴 | 数据完整性 | relation_repair.py:22-84 | 边重复的触发根源 |
| #3 | P0 🔴 | 数据丢失 | explore_agent.py KG 写入路径 | 探索结果丢失 |
| #2 | P1 🟡 | 数据完整性 | json_kg_repository.py:204 | JSON 关系覆盖 |
| #4 | P1 🟡 | 重复执行 | explore_daemon.py + queue | 同 topic 重复探索 |
| #8 | P1 🟡 | 错误处理 | 全代码库 | 静默失败 77+ 处 |
| #11 | P1 🟡 | 并发问题 | knowledge_graph_compat.py | async/sync 边界 |
| #9 | P1 🟡 | 测试覆盖 | 16 个核心文件 | 隐藏 bug |
| #5 | P2 🟢 | 状态不一致 | curious_api.py:528 | API 状态显示 |
| #10 | P2 🟢 | 可观测性 | 全代码库 | 日志分散 |
| #12 | P2 🟢 | 并发问题 | QueueStorage singleton | SQLite 线程安全 |

---

## P0 级 Bug（立即修复）

### Bug #1: 边重复创建（CREATE vs MERGE）

**严重程度**: P0 🔴  
**影响**: KG 有 1605 条边但只有 189 个唯一签名，重复率 8.5x

**根因（三层）**:

1. **直接根因**: `kg_repository.py:315` 使用 `CREATE` 而非 `MERGE`
```python
# 错误代码
query = f"""
MATCH (a:Knowledge {{topic: $from_topic}})
MATCH (b:Knowledge {{topic: $to_topic}})
CREATE (a)-[r:{relation_type}]->(b)  # ← CREATE 不检查存在性
RETURN true as success
"""
```

2. **触发根因**: `relation_repair.py:70` 每轮 `scan_and_repair()` 都调用 `create_relation_sync()`，但不记录已修复的孤儿

3. **架构根因**: `RelationRepairService` 缺少「已修复孤儿」状态记录，每轮 `_scan_orphan_nodes` 都会重新处理

**彻底修复方案**:

```python
# 方案 A: kg_repository.py 改用 MERGE（立即）
query = f"""
MATCH (a:Knowledge {{topic: $from_topic}})
MATCH (b:Knowledge {{topic: $to_topic}})
MERGE (a)-[r:{relation_type}]->(b)  # ← MERGE 去重
RETURN true as success
"""

# 方案 B: RelationRepairService 增加已修复记录（根治）
class RelationRepairService:
    def __init__(self, ...):
        self._repaired_orphans: Set[str] = set()  # 记录已修复的孤儿 topic
        self._repair_history_file = "knowledge/repaired_orphans.json"
        self._load_repair_history()
    
    def scan_and_repair(self) -> Dict[str, int]:
        for node in all_nodes:
            topic = node.get("topic", "")
            if topic in self._repaired_orphans:
                continue  # ← 跳过已修复的孤儿
            ...
            if relation_created:
                self._repaired_orphans.add(topic)
                self._save_repair_history()
```

---

### Bug #6: Trace 日志不记录 KG 写入结果

**严重程度**: P0 🔴  
**影响**: Bug #3 诊断困难，trace 表 `kg_nodes_created=[]` `quality_score=null`

**根因**:

`explore_agent.py` 有两处调用 `trace_writer.finish_trace()`:
- 278-284 行（正常结束）
- 401-407 行（达到 max_iterations）

两处都**没有传递 `kg_nodes_created` 和 `quality_score` 参数**:

```python
# explore_agent.py:278-284 (错误)
trace_writer.finish_trace(
    trace_id=trace_id,
    status="done",
    total_steps=iterations,
    tools_used=list(tools_used_set),
    duration_ms=total_duration,
    # ← 缺少 kg_nodes_created
    # ← 缺少 quality_score
)
```

而 KG 写入发生在 finish_trace **之后** (308-339 行)，结果无法记录到 trace。

**彻底修复方案**:

```python
# 方案: 在 KG 写入完成后，调用 finish_trace 并传递写入结果
# 重构 explore_agent._react_loop() 逻辑顺序:

# 1. 先执行 KG 写入
add_result = await add_tool.execute(...)
kg_nodes_created = [topic] if add_result else []
quality_score = metadata.get("quality", 5.0)

# 2. 再调用 finish_trace（带结果）
trace_writer.finish_trace(
    trace_id=trace_id,
    status="done",
    total_steps=iterations,
    tools_used=list(tools_used_set),
    kg_nodes_created=kg_nodes_created,  # ← 添加
    quality_score=quality_score,        # ← 添加
    duration_ms=total_duration,
)
```

---

### Bug #7: RelationRepairService 每轮重复处理同一孤儿

**严重程度**: P0 🔴  
**影响**: 这是 Bug #1 边重复的**架构根源**

**根因分析**:

`relation_repair.py:22-84` 的 `scan_and_repair()`:
1. 每轮扫描所有节点（最多 500 个）
2. 对每个孤儿调用 `_find_relation_candidates()` 和 `create_relation_sync()`
3. **没有记录已处理状态**，下轮继续处理同一孤儿
4. 配合 Bug #1 的 `CREATE`（不去重），边数爆炸式增长

触发路径（来自 buglist 原分析）:
```
ExploreDaemon._tick()
  └── pending_items 为空 → _scan_orphan_nodes()
        └── RelationRepairService.scan_and_repair()
              └── 多次调用 kg_factory.create_relation_sync()
                    └── repository_factory.create_relation_sync()
                          └── kg_repository.add_relation()
                                └── CREATE (a)-[r]->(b)  # ← Bug #1
```

**彻底修复方案**:

在 `RelationRepairService` 增加「已修复孤儿」持久化状态:

```python
class RelationRepairService:
    REPAIR_HISTORY_FILE = "knowledge/repaired_orphans.json"
    
    def __init__(self, ...):
        self._repaired_orphans: Set[str] = set()
        self._load_history()
    
    def _load_history(self):
        if os.path.exists(self.REPAIR_HISTORY_FILE):
            with open(self.REPAIR_HISTORY_FILE) as f:
                self._repaired_orphans = set(json.load(f).get("repaired", []))
    
    def _save_history(self):
        with open(self.REPAIR_HISTORY_FILE, "w") as f:
            json.dump({"repaired": list(self._repaired_orphans), 
                       "last_updated": datetime.now().isoformat()}, f)
    
    def scan_and_repair(self) -> Dict[str, int]:
        stats = {"scanned": 0, "orphan_found": 0, "relations_created": 0, "skipped_already_repaired": 0}
        
        for node in all_nodes:
            topic = node.get("topic", "")
            
            # ← 新增: 跳过已修复的孤儿
            if topic in self._repaired_orphans:
                stats["skipped_already_repaired"] += 1
                continue
            
            # 检查是否孤儿...
            if relations > 0:
                continue
            
            stats["orphan_found"] += 1
            
            # 尝试修复...
            if self._verify_relation(topic, candidate["topic"], ...):
                kg_factory.create_relation_sync(...)
                stats["relations_created"] += 1
                
                # ← 新增: 记录已修复
                self._repaired_orphans.add(topic)
                self._save_history()
        
        return stats
    
    def reset_history(self):
        """管理员可调用，重置修复历史（重新扫描所有孤儿）"""
        self._repaired_orphans.clear()
        self._save_history()
```

---

### Bug #3: 探索结果未写入 KG

**严重程度**: P0 🔴  
**影响**: ExploreAgent 运行成功但 KG 节点为空

**根因分析（需要诊断确认）**:

`explore_agent.py:308-339` 的 KG 写入路径可能有以下问题:

1. **AddToKGTool 执行失败但异常被静默捕获**
   - `kg_tools.py:233-249` 的 `AddToKGTool.execute()` 调用 `create_knowledge_node()`
   - 如果 Neo4j 连接失败，异常可能在某个层级被 `except Exception: pass`

2. **kg_repository.py 的 create_knowledge_node 有静默失败路径**
   - line 143-145: `if result: return result[0].get("id", topic); return topic`
   - 即使 Neo4j 返回空结果，也返回 topic（假装成功）

3. **ExploreDaemon 的 KG 验证逻辑问题**
   - `explore_daemon.py:140-153`: 验证 `node.get('content')` 是否 > 10 字符
   - 如果 KG 写入失败，content 为空，会「keep claimed」等待 timeout
   - 但 timeout 后不会 retry，而是直接 delete

**诊断步骤**:

1. 在 `kg_tools.py:AddToKGTool.execute()` 增加:
```python
async def execute(self, **kwargs: Any) -> str:
    ...
    if self._repository:
        try:
            result = await self._repository.create_knowledge_node(...)
            logger.info(f"[KGWrite] Created node: {topic}, result={result}")
            return f"Added node: {topic}"
        except Exception as e:
            logger.error(f"[KGWrite] FAILED to create node: {topic}, error={e}")
            raise  # ← 不静默捕获
```

2. 在 `kg_repository.py:create_knowledge_node()` 增加:
```python
result = await self._client.execute_write(query, **params)
if not result:
    logger.warning(f"[KG] create_knowledge_node returned empty result for {topic}")
    return None  # ← 明确返回 None 表示失败
return result[0].get("id", topic)
```

3. 在 `explore_agent.py` 的 KG 写入处检查返回值:
```python
add_result = await add_tool.execute(...)
if not add_result or "FAILED" in add_result:
    logger.error(f"[ExploreAgent] KG write failed for {topic}")
    # 不应该假装成功
```

**彻底修复方案**:

```python
# 方案: 建立 KG 写入的完整错误传播链

# 1. kg_repository.py: 返回明确结果（成功/失败）
async def create_knowledge_node(...) -> Optional[str]:
    ...
    result = await self._client.execute_write(query, **params)
    if not result:
        logger.error(f"[KG] Neo4j write returned empty for {topic}")
        return None
    return result[0].get("id", topic)

# 2. kg_tools.py: 传播异常，不静默捕获
async def execute(self, **kwargs) -> str:
    ...
    result = await self._repository.create_knowledge_node(...)
    if result is None:
        return f"ERROR: Failed to create KG node for {topic}"
    return f"Added node: {result}"

# 3. explore_agent.py: 检查返回值，失败时记录到 trace
add_result = await add_tool.execute(...)
kg_nodes_created = [topic] if "Added" in add_result else []
quality_score = metadata.get("quality", 5.0) if kg_nodes_created else None

trace_writer.finish_trace(
    ...
    kg_nodes_created=kg_nodes_created,
    quality_score=quality_score,
)
```

---

## P1 级 Bug（中期修复）

### Bug #2: JSON 仓库 relation key 缺少类型

**严重程度**: P1 🟡  
**影响**: 同一对 topic 的不同关系类型会互相覆盖

**根因**: `json_kg_repository.py:204`
```python
# 错误
key = f"{from_topic}|{to_topic}"  # ← 没有 relation_type
```

**彻底修复**:
```python
key = f"{from_topic}|{to_topic}|{relation_type}"
```

---

### Bug #4: 同一 topic 被重复探索

**严重程度**: P1 🟡  
**影响**: 同 topic 多次进入队列，重复执行探索

**根因分析**:

1. `explore_daemon.py:145-152` 的 KG 验证后删除逻辑:
   - KG 写入成功 → `delete_item()` 删除队列项
   - KG 验证失败 → 保持 `claimed` 状态，等待 timeout
   - Timeout 后 → `release_expired_claims()` 释放为 pending

2. 释放机制可能有问题:
   - 如果 daemon 在 KG 验证时崩溃，item 保持 claimed 状态
   - Timeout 后被释放，但 topic 已经被探索过（KG 已有内容）
   - Dedup 检查 `check_duplicate_topic()` 可能没有检查 KG 中已存在的节点

**彻底修复方案**:

```python
# 方案 A: 加强 dedup 检查（在 add_item 时检查 KG）
def check_duplicate_topic(self, topic: str) -> Optional[...]:
    # 1. 检查队列中的 pending/done
    ...
    
    # 2. ← 新增: 检查 KG 中已存在的节点
    kg_factory = get_kg_factory()
    existing_node = kg_factory.get_node_sync(topic)
    if existing_node and existing_node.get("content"):
        return (topic, 1.0, "already_in_kg")  # ← KG 已有内容，拒绝

# 方案 B: ExploreDaemon 在 delete 后更新 meta_cognitive
def _tick(self):
    ...
    self.queue_storage.delete_item(item_id, ...)
    # ← 新增: 标记为已完成
    kg_compat.mark_topic_done(topic, "exploration_complete")
```

---

### Bug #8: 关键模块缺少错误类型体系

**严重程度**: P1 🟡  
**影响**: 77+ 处 `except Exception: pass` 阻止错误传播

**根因分析**:

1. 全代码库只有 2 个自定义异常 (`core/exceptions.py`):
   - `EmbeddingError` (embedding_service.py)
   - `ClarificationNeeded` (exceptions.py)

2. 错误分类系统 `error_classifier.py` 只用于 API/L3 调用，不用于 KG/Queue/内部操作

3. KG 操作失败时返回 `None`/`[]`/`False`，调用者无法区分「正常空」和「失败」

**彻底修复方案**:

```python
# 创建 core/kg_errors.py
class KGError(Exception):
    """Knowledge Graph 操作失败"""
    def __init__(self, operation: str, topic: str, reason: str):
        self.operation = operation
        self.topic = topic
        self.reason = reason
        super().__init__(f"[KG] {operation} failed for '{topic}': {reason}")

class KGConnectionError(KGError):
    """Neo4j 连接失败"""
    pass

class KGNodeNotFound(KGError):
    """节点不存在"""
    pass

class KGConstraintError(KGError):
    """约束冲突（如重复关系）"""
    pass

# 创建 core/queue_errors.py
class QueueError(Exception):
    """队列操作失败"""
    pass

class QueueClaimError(QueueError):
    """Claim 失败"""
    pass

# 创建 core/search_errors.py
class SearchError(Exception):
    """搜索操作失败"""
    pass

# 替换 knowledge_graph_compat.py 中的 except Exception: pass
async def add_relation(from_topic: str, to_topic: str, relation_type: str) -> bool:
    try:
        repo = await kg_factory._ensure_connected()
        result = await repo.add_relation(from_topic, to_topic, relation_type)
        return result
    except Neo4jConnectionError as e:
        raise KGConnectionError("add_relation", from_topic, str(e))
    except Exception as e:
        raise KGError("add_relation", from_topic, str(e))
```

---

### Bug #11: Sync/Async 边界问题

**严重程度**: P1 🟡  
**影响**: asyncio.run() 在已有 event loop 时可能失败

**根因分析**:

`knowledge_graph_compat.py` 大量使用 `asyncio.run()` 在同步函数中:
- `get_children()` (line 607): `asyncio.run(_get_children())`
- `mark_dormant()` (line 620): `asyncio.run(_mark())`
- `get_relations_count()` (line 1214): `asyncio.run(_count())`

`ExploreDaemon` 使用 `nest_asyncio.apply()` (line 87)，允许嵌套调用。

但某些调用路径（如从 Flask API）可能在已有 event loop 的环境中调用这些函数。

**彻底修复方案**:

```python
# 方案: 使用统一的 async wrapper，检测是否在 event loop 中
import asyncio
from typing import TypeVar, Callable

T = TypeVar('T')

def run_async(coro: Callable[..., T]) -> T:
    """安全地在同步环境运行 async 函数"""
    try:
        loop = asyncio.get_running_loop()
        # 已有 loop → 使用 nest_asyncio 或返回 Future
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # 没有 running loop → 创建新 loop
        return asyncio.run(coro)

# 替换 knowledge_graph_compat.py 中的 asyncio.run()
def get_children(topic: str) -> list:
    async def _get():
        repo = await kg_factory._ensure_connected()
        return await repo.get_children(topic)
    return run_async(_get())
```

---

### Bug #9: 核心模块缺少测试覆盖

**严重程度**: P1 🟡  
**影响**: Bug 隐藏在无测试的核心代码中

**根因分析**:

16 个核心文件**完全没有测试**:
- `knowledge_graph_compat.py` (1481 行)
- `curious_api.py` (2960 行)
- `curious_agent.py` (1132 行)
- `web_scrape_tools.py` (281 行)
- `json_kg_repository.py` (445 行)
- `concept_normalizer.py` (410 行)

**彻底修复方案**:

创建以下测试文件:
```
tests/core/test_knowledge_graph_compat.py      # KG compat 层单元测试
tests/core/test_web_scrape_tools.py            # v0.3.3 web scraping 测试
tests/core/kg/test_json_kg_repository.py       # JSON KG 测试
tests/core/test_concept_normalizer.py          # 概念标准化测试
tests/api/test_curious_api_inject.py           # inject 端点复杂逻辑测试
tests/test_curious_agent_daemon.py             # daemon_mode 测试
```

---

## P2 级 Bug（低优先级）

### Bug #5: Queue API 状态与 SQLite 不一致

**严重程度**: P2 🟢  

**根因**: `curious_api.py:528` 使用 `kg.list_pending()`
而 `list_pending()` 正确使用 `QueueStorage.get_pending_items()`

**验证**: 此 bug 可能是数据显示问题，需要确认 API 和 SQLite 是否真的不一致。

---

### Bug #10: 日志系统分散

**严重程度**: P2 🟢  
**影响**: 运行时错误难以追踪

**根因**:
- 5 文件用 loguru，31+ 文件用标准 logging
- `curious_api.py` 和 `curious_agent.py` 只用 print

**彻底修复方案**:
```python
# 创建 core/logging_config.py
import logging
from loguru import logger

# 统一配置
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )
    # loguru 也输出到同一 sink
    logger.add(sys.stdout, level="INFO")

# 在 curious_api.py 和 curious_agent.py 开头调用
from core.logging_config import setup_logging
setup_logging()
```

---

### Bug #12: SQLite singleton 线程安全

**严重程度**: P2 🟢  

**根因**: `knowledge_graph_compat.py:64-70` 的 `_queue_storage` singleton 在多线程环境下共享

**修复**: 每次使用时创建新连接，或使用线程安全的 SQLite 配置。

---

## 系统性架构问题

### 问题 A: 数据分离规则不一致

**现象**: 
- Neo4j 应只存 `status=done` 的节点
- SQLite queue 应存 `pending` 的节点
- 但 `knowledge_graph_compat.py` 中 `_get_queue_storage()` 和 KG 操作混在一起

**建议**: 建立明确的数据边界文档，审查所有数据操作是否符合分离规则。

### 问题 B: ExploreAgent KG 写入时机错误

**现象**: KG 写入发生在 `finish_trace()` 之后，导致 trace 无法记录写入结果。

**建议**: 重构 `_react_loop()` 流程，KG 写入 -> finish_trace。

### 问题 C: RelationRepair 缺少持久化状态

**现象**: 每轮扫描重复处理同一孤儿。

**建议**: 增加 `repaired_orphans.json` 持久化文件。

---

## 彻底修复方案

### Phase 1: P0 紧急修复（立即执行）

1. **Bug #1**: `kg_repository.py:315` CREATE → MERGE（1 行改动）
2. **Bug #7**: `RelationRepairService` 增加已修复孤儿记录（根治）
3. **Bug #6**: `explore_agent.py` finish_trace 增加 kg_nodes_created/quality_score
4. **Bug #3 诊断**: KG 写入路径增加详细日志

### Phase 2: P1 中期修复（计划中）

5. **Bug #2**: JSON repository key 增加 relation_type
6. **Bug #4**: 队列 dedup 检查 KG 已存在节点
7. **Bug #8**: 创建 KGError/QueueError/SearchError 异常类型
8. **Bug #11**: 统一 async/sync 边界处理
9. **Bug #9**: 创建核心模块测试文件

### Phase 3: P2 架构优化

10. **Bug #5**: API 状态读取路径验证
11. **Bug #10**: 统一日志配置
12. **Bug #12**: SQLite 线程安全审计

---

## 验收标准

| Bug | 验收条件 | 测试方法 |
|-----|---------|---------|
| #1 边重复 | MERGE 后无重复边，关系数稳定 | Neo4j query: `MATCH ()-[r]->() RETURN count(r)` |
| #6 Trace | kg_nodes_created 非空，quality_score 非 null | SQLite query: `SELECT kg_nodes_created FROM explorer_traces WHERE status='done'` |
| #7 孤儿重复 | repaired_orphans.json 存在且正确更新 | 检查文件内容 |
| #3 KG写入 | 探索后 KG 节点有 content | Neo4j query: `MATCH (k:Knowledge {topic: $topic}) RETURN k.content` |
| #2 JSON key | 同 topic 多关系类型全部保留 | JSON KG inspection |
| #4 重复探索 | 同 topic 只产生 1 条 done trace | SQLite trace count |
| #8 错误类型 | KGError/QueueError 可被正确捕获 | 单元测试 |

---

## 修复执行顺序

```
Week 1 (P0):
  Day 1-2: Bug #1 CREATE → MERGE + 清理脚本
  Day 3-4: Bug #7 RelationRepair 已修复记录
  Day 5:   Bug #6 Trace 参数修复

Week 2 (P0 继续):
  Day 1-3: Bug #3 KG 写入路径诊断 + 日志增强
  Day 4-5: Bug #3 KG 写入错误传播修复

Week 3-4 (P1):
  Bug #2, #4, #8, #11, #9 分批修复

Week 5+ (P2):
  Bug #5, #10, #12 架构优化
```

---

## 相关文件索引

| Bug | 主要文件 | 代码行 |
|-----|---------|-------|
| #1 | `core/kg/kg_repository.py` | 315 |
| #2 | `core/kg/json_kg_repository.py` | 204 |
| #3 | `core/agents/explore_agent.py` | 308-339 |
| #4 | `core/daemon/explore_daemon.py` | 140-152 |
| #5 | `curious_api.py` | 528 |
| #6 | `core/agents/explore_agent.py` | 278-284, 401-407 |
| #7 | `core/relation_repair.py` | 22-84 |
| #8 | `core/exceptions.py`, `core/knowledge_graph_compat.py` | 全文件 |
| #9 | `tests/` 目录结构 | 多文件缺失 |
| #10 | `curious_api.py`, `curious_agent.py` | logging 调用 |
| #11 | `core/knowledge_graph_compat.py` | asyncio.run() |
| #12 | `core/tools/queue_tools.py` | 64-70 |

---

## 附录: 原 Buglist 参考

参见 `/docs/plan/buglist0.3.4.md` 原诊断文档。

---

**文档状态**: Draft  
**下一步**: 按 Phase 1 执行 P0 修复