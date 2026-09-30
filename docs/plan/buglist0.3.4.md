# Bug List v0.3.4 — Edge Duplication & Exploration Pipeline

**日期**: 2026-05-25
**诊断人**: R1D3-researcher
**版本**: v0.3.4（修复版）
**状态**: Root cause identified, fix pending

---

## 目录

1. [Bug #1: 边重复创建（根因 Bug）](#bug-1-边重复创建根因-bug)
2. [Bug #2: JSON 仓库 relation key 缺少类型](#bug-2-json-仓库-relation-key-缺少类型)
3. [Bug #3: 探索结果未写入 KG](#bug-3-探索结果未写入-kg)
4. [Bug #4: 同一 topic 被重复探索](#bug-4-同一-topic-被重复探索)
5. [Bug #5: Queue API 状态与 SQLite 不一致](#bug-5-queue-api-状态与-sqlite-不一致)
6. [触发路径分析](#触发路径分析)
7. [修复方案](#修复方案)
8. [验收标准](#验收标准)

---

## Bug #1: 边重复创建（根因 Bug）

### 严重程度: P0 🔴

### 症状
- KG 有 **1605 条边**，但只有 **189 个唯一签名**
- 重复率 **8.5x**，最严重的一条边出现 **109 次**
- 边数随时间持续增长，即使 KG 节点数不增长
- 最严重重复案例：
  - `Group-wise Re-balancing Mechanism → tandfonline related research` (CITES): **109 次**
  - `GitHub - tsinghua-fib-lab/TrajAgent → agent task trojectory` (IS_CHILD_OF): **57 次**
  - `GitHub - MobileLLM/AgentProg → [2512.10371] AgentProg` (IS_CHILD_OF): **57 次**

### 根因

**Neo4j 仓库使用 `CREATE` 而非 `MERGE`**，每次调用都创建新关系，不检查是否已存在。

**文件**: `core/kg/kg_repository.py:311`

```python
# 当前代码（错误）
async def add_relation(
    self,
    from_topic: str,
    to_topic: str,
    relation_type: str = "IS_CHILD_OF"
) -> bool:
    query = f"""
    MATCH (a:Knowledge {{topic: $from_topic}})
    MATCH (b:Knowledge {{topic: $to_topic}})
    CREATE (a)-[r:{relation_type}]->(b)  # ← CREATE 总是创建新关系
    RETURN true as success
    """
    ...
```

### 修复方案

```python
# 正确代码
query = f"""
MATCH (a:Knowledge {{topic: $from_topic}})
MATCH (b:Knowledge {{topic: $to_topic}})
MERGE (a)-[r:{relation_type}]->(b)  # ← MERGE 只在不存在时创建
RETURN true as success
"""
```

### 修复后数据清理

修复代码后，需要清理现有重复边：

```python
# 一次性清理脚本
MATCH (a)-[r]->(b)
WITH a.topic as src, b.topic as tgt, type(r) as rel_type, collect(r) as rels
WHERE size(rels) > 1
FOREACH (r IN rels[1..] | DELETE r)
```

---

## Bug #2: JSON 仓库 relation key 缺少类型

### 严重程度: P1 🟡

### 根因

JSON 仓库的 relation key 不包含 `relation_type`，导致不同关系类型相互覆盖。

**文件**: `core/kg/json_kg_repository.py:197`

```python
# 当前代码（错误）
key = f"{from_topic}|{to_topic}"  # ← 没有包含 relation_type
```

### 影响

- 如果同一对 topic 同时有 `IS_CHILD_OF` 和 `CITES` 两种关系，后者会覆盖前者
- 属于数据丢失而非重复

### 修复方案

```python
# 正确代码
key = f"{from_topic}|{to_topic}|{relation_type}"
```

---

## Bug #3: 探索结果未写入 KG

### 严重程度: P0 🔴

### 症状

所有最近探索的 `kg_nodes_created` 都是空数组 `[]`，`quality_score` 都是 `null`。

Trace 记录示例：
```
trace_id=3265f957, topic=Embodied AI robotics language models 2026,
status=done, total_steps=9, kg_nodes_created=[], quality_score=null,
llm_total_tokens=352283, duration_ms=0
```

### 根因

ExploreAgent 成功运行（9 个 step，消耗了 352k tokens），但没有往 KG 写入任何节点。

可能原因：
1. 工具调用成功但 KG 写入时异常被静默捕获
2. LLM 提取的知识节点为空（所有页面都解析失败）
3. KG 写入路径被损坏（`create_knowledge_node` 返回失败）

### 修复方案

需要检查 `core/agents/explore_agent.py` 中 `create_knowledge_node` 的调用路径，确认：
1. 写入 KG 时是否有异常被静默捕获
2. LLM 提取结果的 validation 是否过于严格
3. 是否需要增加写入成功/失败的明确日志

### 修复优先级: P0

---

## Bug #4: 同一 topic 被重复探索

### 严重程度: P1 🟡

### 症状

"Embodied AI robotics language models 2026" 被探索了 **4 次**：

| 时间 | 状态 | trace_id |
|------|------|----------|
| 2026-05-24 23:43 | done | c16f38f1 |
| 2026-05-24 23:52 | done | e6483f62 |
| 2026-05-25 00:00 | running（卡住） | 16cc9ff5 |
| 2026-05-25 00:05 | done | 3265f957 |

### 根因

探索完成后 queue item 没有被正确删除，导致被重复 claim。

可能原因：
1. `delete_item` 在 KG 验证通过后没有被调用
2. 队列状态更新和 claim 操作不是原子的
3. `claim_item` 的 timeout 逻辑有问题，卡住的 item 没有被正确释放

### 修复优先级: P1

---

## Bug #5: Queue API 状态与 SQLite 不一致

### 严重程度: P2 🟢

### 症状

- API `/api/curious/state` 返回: pending=22, exploring=0, done=0
- SQLite `knowledge/queue.db` 实际: pending=22, failed=17, done=100

### 根因

API 端点读取队列的方式和 ExploreDaemon 使用的 `QueueStorage` 不同步。

API 使用 `kg.list_pending()` 获取队列，但这个方法可能不是直接从 SQLite 读取。

### 修复优先级: P2（低优先级，不影响核心功能）

---

## 触发路径分析

### 边重复创建的完整调用链

```
ExploreDaemon._tick()
  └── pending_items 为空 → _scan_orphan_nodes()
        └── 遍历所有节点，找 quality>=7.0 的孤儿
            └── 对每个孤儿: RelationRepairService._find_relation_candidates()
                  └── 多次调用 kg_factory.create_relation_sync()
                        └── repository_factory.create_relation_sync()
                              └── kg_repository.add_relation()
                                    └── CREATE (a)-[r]->(b)  # 无去重！
```

**关键问题**：`RelationRepairService` 每轮都会重新处理相同的孤儿节点，每次都会调用 `add_relation`，而 `add_relation` 用 `CREATE` 不会检查关系是否已存在。

### 边重复的累积效应

假设：
- 每轮 `_scan_orphan_nodes` 处理 5 个孤儿
- 每个孤儿产生 3 个新关系
- 每 5 分钟跑一轮

则每小时产生 180 条新边，其中大量是重复的。

---

## 修复方案

### 紧急修复（立即执行）

1. **Bug #1**: `CREATE` → `MERGE`（一行代码）
2. **清理脚本**: 删除现有重复边
3. **Bug #3 诊断**: 在 ExploreAgent 的 KG 写入路径增加详细日志

### 中期修复（计划中）

4. **Bug #2**: JSON 仓库 key 加上 relation_type
5. **Bug #4**: 队列 claim/delete 原子性检查
6. **Bug #5**: API 队列状态读取路径统一

### 架构优化（v0.3.5+）

7. `RelationRepairService` 改为记录已修复的孤儿，避免重复处理
8. 增加 KG 健康检查：边数/节点数比例异常时告警

---

## 验收标准

| Bug | 验收条件 |
|-----|---------|
| #1 边重复 | `get_all_relations_sync()` 去重后数量 = 原始数量 |
| #2 JSON key | 同一 topic 对有多种 relation_type 时全部保留 |
| #3 KG写入 | 探索完成后 `kg_nodes_created` 非空，`quality_score` 非 null |
| #4 重复探索 | 同一 topic 只产生 1 条 `done` 状态的 trace |
| #5 API一致 | API 返回的队列状态和 SQLite 查询结果一致 |

---

## 相关文件

- `core/kg/kg_repository.py:311` — Neo4j add_relation（Bug #1）
- `core/kg/json_kg_repository.py:197` — JSON add_relation（Bug #2）
- `core/agents/explore_agent.py` — 探索 agent（Bug #3 相关）
- `core/relation_repair.py` — 关系修复服务（Bug #1 触发点）
- `core/daemon/explore_daemon.py` — 探索 daemon（Bug #4 相关）
- `curious_api.py:511` — API 队列状态读取（Bug #5）
- `ideas/orphan-handling-openspec-v0.3.md` — 孤儿处理架构设计
