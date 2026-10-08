# next_move_v0.3.6_SSOT — 四 Agent 唯一真源收敛（Single Source of Truth）

> **版本**：v0.3.6-SSOT（对 v0.3.6 的补充批次，不替换原计划）
> **依据**：2026-10-08 全量代码核查（四 Agent 数据源读写实测）
> **决策者**：weNix（2026-10-08：出清单 → 按文档实施与验收）
> **前置**：`docs/plan/next_move_v0.3.6.md`（批1–批8，冲突检测/缺口生成/发现回流）

---

## 〇、为什么要先做这件事（一句话）

> **四个 Agent 不是"没有唯一真源"，而是"真源已定义，但一半的 Agent 还在读一个已被掏空的旧壳子，而且不报错"。**

在做 C2/C3（缺口生成/发现回流）之前，必须先把**读源**统一到 Neo4j。
否则 C1 四态判决器的输入（quality/status/dormant）永远读到的是**空 topics**，
整条 C2→C3→C3-D 链路都建在错误输入上。

---

## 一、实测证据（2026-10-08）

### 1.1 四 Agent 数据源读写矩阵

| Agent | 写入源 | 读取源 | 范式 | 判定 |
|-------|--------|--------|------|------|
| **ExploreAgent** (726行) | Neo4j + queue.db + 行为库 | queue.db | ✅ 新（直查真源） | 健康 |
| **DeepReadAgent** (517行) | Neo4j（add_to_kg, DERIVED_FROM） | 独立队列 | ✅ 新 | 孤立但正确 |
| **DreamAgent** (641行) | queue.db + ops.db | **`state["knowledge"]["topics"]`** | ❌ 旧（state 骨架） | **输入恒空** |
| **SleepPruner** (337行) | **`_save_state()` → ops.db 空 topics** | `state["knowledge"]["topics"]` | ❌ 旧 | **写入静默失效** |

### 1.2 根因：`state.json` 已退场，但"state 骨架"仍在流通

Phase 1 数据治理把 `state.json` 退役，做法是：

```
_load_state()  → 从 ops.db 读（runtime_kv + meta_cognitive），返回 state.json 时代骨架
_save_state()  → 写 ops.db（不再写 state.json）
```

**函数名与返回结构完全没变**，于是：

1. `state["knowledge"]["topics"]` **恒为空**（知识真源是 Neo4j，ops.db 不存 topics）
2. SleepPruner `_mark_dormant_batch()` 写 `state["knowledge"]["topics"][topic]["status"]="dormant"`
   → **空 dict，什么都没标上，且不报错**（静默失效，同 AGENTS.md 记录的四个月零日志病）
3. DreamAgent 的 quality / surprise / cross_domain 三维打分，输入恒为默认值

### 1.3 关键：dormant 状态**没有真源**

| 事实 | 证据 |
|------|------|
| Neo4j **有** `mark_dormant()` 正确实现 | `core/kg/kg_repository.py:455` |
| `knowledge_graph_compat.mark_dormant()` **已接线到 Neo4j** | `knowledge_graph_compat.py:709` |
| 但 SleepPruner **没调它**，走的是失效的 state 路径 | `sleep_pruner.py:290-296` |
| `get_dormant_nodes()` **已从 Neo4j 读**（读侧已对） | `knowledge_graph_compat.py:1246` |

→ **写侧走废壳，读侧已对源**。两侧不闭环，dormant 永远是空集。

### 1.4 旧范式调用点全清单（实测）

**外部调用点**（`_load_state`/`_save_state` 的消费方）：

| 文件:行 | 用途 | 读取键 | 迁移目标 |
|---------|------|--------|---------|
| `daemon/explore_daemon.py:344,349` | 孤儿重激活，改 completed_topics | meta_cognitive | ✅ 保留（ops.db 真源） |
| `sleep_pruner.py:145` | 读 dormant 判定输入 | `knowledge.topics` | ❌ 改 Neo4j |
| `sleep_pruner.py:290,296` | **写 dormant** | `knowledge.topics` | ❌ 改 `mark_dormant()` |
| `curiosity_engine.py:176,195,218` | 打分读 topics；写回 | `knowledge.topics` | ❌ 改 `get_state()`（已对源） |
| `exploration_history.py:20,31,33` | 读写 exploration_history | `exploration_history` | ⚠️ 迁 runtime_kv |
| `meta_cognitive_monitor.py:196,216,238` | 置信区间/证据计数 | `knowledge.topics` | ❌ 改 Neo4j 属性/ops 表 |
| `competence_tracker.py:94` | 能力置信度 | `knowledge.topics` | ❌ 改 ops 表 |
| `scripts/cleanup_test_data.py:117` | 清理脚本 | state | ⚠️ 跟随主逻辑 |

**compat shim 内部调用点**（`knowledge_graph_compat.py` 自身）：
`mark_dreamed`(1222)、`set_consolidated`(1235)、`has_recent_dreams`(1260)、
`get_recently_dreamed`(1282)、`is_topic_completed`(1139)、`update_meta_exploration`(1166)
等 —— 多数本质是 **meta_cognitive / runtime_kv**（ops.db 真源），保留；
少数误读 `knowledge.topics`（dreamed_at/last_consolidated），需改。

---

## 二、真源裁定表（每个概念一个写入点）

| 概念 | 唯一真源 | 唯一写入口 | 唯一读入口 | 现状 |
|------|---------|-----------|-----------|------|
| 知识 / 质量 / status | **Neo4j** | `add_to_kg` / `update_kg_status` | `get_kg_factory().get_node_sync()` | ✅ 已对 |
| **dormant** | **Neo4j（status='dormant'）** | `kg.mark_dormant()` | `get_dormant_nodes()` | ❌ 写侧走废壳 |
| **dreamed_at / last_consolidated** | **Neo4j 节点属性** | `set_node_metadata()` | `get_node_sync()` | ❌ 走废壳 |
| 探索队列 | **queue.db** | `QueueStorage` | `QueueStorage` | ✅ |
| meta_cognitive（explore_counts 等） | **ops.db.meta_cognitive** | `update_meta_exploration` | `get_meta_cognitive_state` | ✅ |
| 运行时开关（search_exhausted 等） | **ops.db.runtime_kv** | `set_search_exhausted` | `is_search_exhausted` | ✅ |
| exploration_history（共现/预测） | **ops.db.runtime_kv** | `ExplorationHistory` | `ExplorationHistory` | ❌ 走废壳 |
| 缺口 | **ops.db.gaps** | `gap_store` | `gap_store` | ✅ |

**纪律**：同一概念不得有第二条写入路径。任何 state 骨架的 `knowledge.topics` 读写
= **违规**，必须改道。

---

## 三、实施批次（SSOT 批次）

### SSOT-0 — 加"读源一致性护栏"（先做，防静默复发）

**任务**：在 `knowledge_graph_compat._load_state()` 加低开销自检——
若返回的 `knowledge.topics` 为空，但 Neo4j 有节点 → 打 `WARNING`（带调用栈）。

**产出**：`_load_state()` 内嵌 `_warn_if_topics_empty()`。
**验收**：运行一次探索循环，日志出现告警 N 次（证明旧范式仍被调用），
迁移完成后告警归零。

### SSOT-1 — SleepPruner 改走 Neo4j（最高优先）

**改动**（`core/sleep_pruner.py`）：

| 行 | 旧 | 新 |
|----|----|----|
| 145 | `state = kg._load_state(); topics = state["knowledge"]["topics"]` | 用 `kg.get_state()["knowledge"]["topics"]`（已对 Neo4j） |
| 290-296 | 写 `state[...]["status"]="dormant"` → `_save_state` | 逐个 `kg.mark_dormant(topic)` |

**验收**：
- 选 1 个 dormant 候选 → 调 `_mark_dormant_batch()` → 
  `get_dormant_nodes()` 返回该 topic（Neo4j 真读到）。
- **反向验证**：改前跑同一用例 → `get_dormant_nodes()` 为空（证明旧路径失效）。

### SSOT-2 — DreamAgent 改走 Neo4j

**改动**（`core/agents/dream_agent.py`）：
- `:156`、`:194` 的 `state["knowledge"]["topics"]` → `kg.get_state()["knowledge"]["topics"]`
- dormant 检测改用 `kg.get_dormant_nodes()`
- quality / depth / surprise 输入改为 Neo4j 节点属性

**验收**：DreamAgent 的 6 维打分日志中，quality/surprise/cross_domain **不再恒为默认值**
（抽样 3 个候选，值有差异）。

### SSOT-3 — meta_cognitive_monitor + competence_tracker 迁移

**改动**：
- `meta_cognitive_monitor.py:196,216,238`：`confidence_low/high`、`evidence_count`、
  `contradiction_count` 从 `knowledge.topics` 迁至 **ops.db.meta_cognitive**（按 topic 行）。
- `competence_tracker.py:94`：`confidence/quality_history/explore_count` 同上。

**验收**：`update_node_confidence()` 后，值写入 ops.db 并可读回；`knowledge.topics` 不再被写。

### SSOT-4 — exploration_history 迁 runtime_kv

**改动**（`core/exploration_history.py`）：
- `_get_history()` / `_save_history()` 的载体从 `state["exploration_history"]`
  改为 `ops.db.runtime_kv['exploration_history']`。

**验收**：`record_exploration()` 后 `co_occurred()` 能读回同一记录。

### SSOT-5 — curiosity_engine 对齐（读侧已对源，仅清理）

**改动**（`core/curiosity_engine.py`）：
- `:176,195` 的 `state["knowledge"]["topics"]` 迭代 → `kg.get_state()["knowledge"]["topics"]`
  （`get_state()` 已从 Neo4j 拼装）
- `:218` `rescore_all()` 写回 → 走 `update_curiosity_score()`（queue.db 真源）

**验收**：`rescore_all()` 后，queue.db 中 pending 项 score 变化可查。

### SSOT-6 — 文档与命名

**改动**：
- `_load_state()` docstring 明确"仅用于 meta_cognitive/runtime_kv，**知识一律走 Neo4j**"
- 重命名候选：`_load_runtime_state()` / `_save_runtime_state()`（保留旧名别名过渡）

**验收**：grep `state["knowledge"]["topics"]` 在 `core/`（除 json_kg_repository 的
JSON fallback 后端）**零命中**。

---

## 四、依赖图与执行顺序

```
SSOT-0 护栏（无依赖，先做）
   │
   ├─► SSOT-1 SleepPruner（dormant → Neo4j）  ← 最高优先
   ├─► SSOT-2 DreamAgent（读 topics → Neo4j）
   ├─► SSOT-3 meta_cognitive_monitor + competence_tracker
   ├─► SSOT-4 exploration_history → runtime_kv
   └─► SSOT-5 curiosity_engine 清理
   │
   └─► SSOT-6 文档/命名收尾
```

| 批 | 任务 | 依赖 | 风险 |
|---|------|------|------|
| SSOT-0 | 读源一致性护栏 | 无 | 🟢 |
| SSOT-1 | SleepPruner → Neo4j | SSOT-0 | 🟡 dormant 语义变更 |
| SSOT-2 | DreamAgent → Neo4j | SSOT-0 | 🟡 打分基线变化 |
| SSOT-3 | meta_cognitive 迁移 | SSOT-0 | 🟡 表结构新增 |
| SSOT-4 | exploration_history → runtime_kv | SSOT-0 | 🟢 |
| SSOT-5 | curiosity_engine 清理 | SSOT-0 | 🟢 |
| SSOT-6 | 文档/命名 | SSOT-1..5 | 🟢 |

---

## 五、整体验收标准

| # | 标准 | 验证方式 |
|---|------|---------|
| 1 | **零静默失效** | SSOT-0 告警在迁移后归零 |
| 2 | **dormant 闭环** | `_mark_dormant_batch()` → `get_dormant_nodes()` 真读到 |
| 3 | **DreamAgent 输入非空** | 6 维打分 quality/surprise/cross_domain 有差异 |
| 4 | **单一写入路径** | grep `knowledge.topics` 写入点在 `core/` 仅剩 JSON fallback |
| 5 | **四 Agent 同源** | ExploreAgent/DreamAgent/DeepReadAgent/SleepPruner 读的 status/quality 来自同一 Neo4j 查询 |
| 6 | **C2/C3 前置就绪** | C1 四态判决器能读到 dormant/status/quality 真值 |

---

## 六、与 v0.3.6 原计划的关系

```
原 v0.3.6 链路：
  批1 provider 一致性 → 批2 C1-B → 批4 C2 缺口 → 批5 C3-C → 批6 C3-D

本 SSOT 批次：
  必须在 批4 C2 之前完成
  理由：C2 缺口的来源 = C1 unknown/void；C1 四态依赖 Neo4j 的 status/quality/dormant
        若 dormant 恒空、topics 恒空 → C1 判定输入失真 → C2 缺口是噪声 → C3/C3-D 空转
```

**修正后的全局顺序**：

```
SSOT-0..6（本档）  ──►  批3 标注集复核（已有 20/20）  ──►  批4 C2 缺口
                                                        │
                                                        └─► 批5 C3-C ─► 批6 C3-D（重定向）
```

---

## 七、风险与纪律

| # | 风险 | 缓解 |
|---|------|------|
| R1 | 改 SleepPruner 写入语义后，历史 state 里的 dormant 丢失 | 现状 = **空集**，无损失；Neo4j 侧从零开始正确 |
| R2 | DreamAgent 打分基线变化 → 产出 topic 变化 | 先只读验证（对比改前后 3 个候选的分数），确认合理后再放开 |
| R3 | ops 表新增列/表 | 走 `CREATE TABLE IF NOT EXISTS`，不动既有数据 |
| R4 | 迁移中两侧并行写入 | **禁止双写**；一方改道后旧路径立即失效（配 SSOT-0 告警验证） |

**纪律（同 AGENTS.md）**：
- 每个改动必须**有反向验证**（改前失效、改后生效），不接受"看起来对了"
- 静默失败 = 最贵的失败；新增路径必须配告警

---

_本档基于 2026-10-08 全量代码核查写成。_
_数据源：`core/knowledge_graph_compat.py`、`core/sleep_pruner.py`、_
_`core/agents/dream_agent.py`、`core/agents/explore_agent.py`、_
_`core/meta_cognitive_monitor.py`、`core/competence_tracker.py`、_
_`core/exploration_history.py`、`core/curiosity_engine.py`、`knowledge/ops.db`。_
