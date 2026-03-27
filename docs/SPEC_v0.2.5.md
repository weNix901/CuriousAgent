# SPEC v0.2.5 — KG 根技术追溯能力

> **唯一目标**: 从任意知识点追溯到根技术，并形成完整的因果链
> **发布日期**: TBD

---

## 背景

v0.2.4 的 KG 只能向下分解（parent → children），无法向上回溯（child → parent → root）。

这导致两个问题：
1. **R1D3 无法消费 KG** — 无法回答"metacognitive monitoring 的根技术是什么"
2. **跨子图根技术被埋没** — transformer attention 横跨多个探索分支，但在各分支里都不显眼

v0.2.5 只解决这两个问题。

---

## 架构原则（所有设计决策的出发点）

### 1. 增量优先，重用为本
- **优先扩展**现有模块，而不是新增并行模块
- 新增模块只在"职责边界清晰、现有模块无法承载"时才引入
- 示例：`knowledge_graph.py` 能扩展的，不新建 `xxx_graph.py`

### 2. 高内聚、低耦合
- 每个模块只做一件事
- 模块间通过**事件总线**（event_bus）或**显式接口**通信，不直接调用对方内部状态
- 禁止循环依赖：A → B → C → A

### 3. API 是唯一的事实来源
- UI 和 sync 脚本都只消费 API，不直接读写 state.json
- API 保证双消费者兼容（人类可读 + R1D3 可解析）
- API 返回 JSON；sync 脚本负责格式转换（JSON → markdown）

### 4. 双消费者兼容
```
API (JSON)
  ├── UI 渲染层 → HTML (人类消费)
  └── sync_kg_to_r1d3.py → markdown (R1D3 消费)
```

### 5. 增量开发顺序
```
阶段1（P0）: KG schema 扩展 + Parent Tracker（只改数据层）
阶段2（P0）: Root Tracer API（只读层，不写数据）
阶段3（P0）: sync_kg_to_r1d3.py（R1D3 消费接口）
阶段4（P1）: Cross-Subgraph Detector（写数据，触发根浮现）
阶段5（P1）: Root Technology Writer（管理根候选池）
阶段6（P2）: 可视化层（增量增强，不改数据层）
```

---

## 核心数据结构

### Topic Schema 扩展（不破坏现有字段）

```python
# knowledge/state.json 的 topic 结构变更（字段追加，不删除）
topics[topic_name] = {
    # === 已有字段（保持不变）===
    "known": bool,
    "depth": int,
    "status": "unexplored | partial | complete | explored",
    "children": [],
    "explored_children": [],
    "summary": "",
    "sources": [],
    "quality": float,  # v0.2.4 已有
    
    # === 新增字段（向上关系）===
    "parents": [],           # 谁派生了这个 topic
    "explains": [],          # 这个 topic 解释了哪些 topic
    
    # === 新增字段（溯源元数据）===
    "derived_from": [        # 因果链条目
        {
            "source": "self-reflection mechanisms",
            "relation": "explains",
            "confidence": 0.85
        }
    ],
    "cross_domain_count": 0,  # 跨多少个探索分支
    "is_root_candidate": False,
    
    # === 新增字段（根评分，v0.2.5 核心）===
    "root_score": 0.0,       # 根技术评分（仅 is_root_candidate=True 时有效）
    
    # === 元数据 ===
    "first_observed": timestamp,
    "last_updated": timestamp
}
```

### Root Technology Pool（独立区域）

```python
# state["root_technology_pool"]
state["root_technology_pool"] = {
    "candidates": [
        {
            "name": "transformer attention",
            "root_score": 9.2,
            "cross_domain_count": 7,
            "explains_count": 23,
            "domains": ["LLM", "CV", "NLP", "RL", "Speech", "Recommendation", "TimeSeries"],
            "confidence": 0.91,
            "sources": ["cross_subgraph_detection", "manual_seed"]
        }
    ],
    "last_updated": timestamp
}
```

---

## 组件关系图

```
探索完成
   │
   ▼
add_exploration_result(topic, result, quality, parent_topic)
   │
   ├──► Parent Tracker ──► knowledge_graph.update_parents()
   │                              │
   │                              ▼
   │                      Cross-Subgraph Detector (通过事件总线)
   │                              │
   │                              ▼
   │                      Root Technology Writer
   │                              │
   │                              ▼
   │                      root_technology_pool 更新
   │
   └──► Root Tracer API (只读)
              │
              ├──► /api/kg/trace/<topic>  ──► UI Trace View
              │                              │
              ├──► /api/kg/roots  ──► UI Root Pool View
              │                              │
              ├──► /api/kg/overview ──► UI KG Overview
              │                              │
              └──► sync_kg_to_r1d3.py ──► R1D3 memory/curious/kg/
```

---

## 新增/修改组件

### R1: 扩展 knowledge_graph.py（修改现有模块）

**修改内容**：
1. `add_child()` 保持不变
2. 新增 `add_parent(child, parent, relation)` — 双向写入 parents + explains
3. 新增 `get_trace(topic, max_depth=10)` — 向上追溯到根，返回路径列表
4. 新增 `get_root_technologies()` — 读取 root_technology_pool
5. 新增 `update_cross_domain_count(topic, count)` — 更新跨分支计数
6. 新增 `init_root_pool(seeds)` — 初始化根技术池（从 config 注入）

**不新增文件**，直接在现有 `knowledge_graph.py` 里追加方法。

### R2: Parent Tracker（core/parent_tracker.py）— 新增

**职责**：薄封装，在探索结果写入时调用 knowledge_graph.update_parents()

**不独立存储状态**，只做参数校验 + 委托。

```python
def track_parent(child: str, parent: str, relation: str = "derived_from"):
    # 校验 parent 存在于 KG
    # 调用 knowledge_graph.add_parent()
```

**设计理由**：如果直接散在 add_exploration_result 里，parent 逻辑会混入数据写入代码。独立出来后方便测试和复用。

### R3: Root Tracer（core/root_tracer.py）— 新增

**职责**：封装 trace 和 roots 的读取逻辑，供 API 层调用。

```python
def trace_topic(topic: str) -> dict:   # 对应 /api/kg/trace/<topic>
def list_roots() -> list:               # 对应 /api/kg/roots
def get_overview() -> dict:             # 对应 /api/kg/overview
def get_anomalies() -> dict:            # 对应 /api/kg/anomalies
def filter_subgraph(**filters) -> list: # 对应 /api/kg/subgraph
```

**不写数据**，只读。

### R4: Cross-Subgraph Detector（core/cross_subgraph_detector.py）— 新增

**职责**：检测跨探索分支的连接，触发根候选浮现。

**通过事件总线触发**，不直接调用 Root Technology Writer。

```python
def detect(new_topic: str, kg_state: dict) -> list:
    # 1. 提取 new_topic 的关键词（从 summary/sources）
    # 2. 遍历已有 KG，找共享概念的 topic（排除直接父子关系）
    # 3. 返回跨子图连接列表
    
def maybe_elevate_to_root(topic: str, cross_domain_count: int):
    # cross_domain_count >= 3 → 触发事件 root_candidate_elevated
    # 通过事件总线，不直接写 root_technology_pool
```

### R5: Root Technology Writer（core/root_technology_writer.py）— 新增

**职责**：订阅 `root_candidate_elevated` 事件，管理 root_technology_pool 写入。

**与其他组件通过事件通信**，不直接调用 detector 或 tracer。

```python
def on_root_candidate_elevated(topic: str, cross_domain_count: int):
    # 写入 root_technology_pool
    # 计算 root_score = cross_domain_count × 0.4 + explains_count × 0.6

def mark_root_from_seed(seed_name: str):
    # 从 config 的 initial_seeds 初始化时调用
```

### R6: API 层扩展（curious_api.py）— 修改

**不新增文件**，在 `curious_api.py` 里追加 `/api/kg/*` 路由。

```python
@app.route("/api/kg/trace/<topic>")
def api_kg_trace(topic):  # 使用 Root Tracer

@app.route("/api/kg/roots")
def api_kg_roots():

@app.route("/api/kg/overview")
def api_kg_overview():

@app.route("/api/kg/anomalies")
def api_kg_anomalies():

@app.route("/api/kg/subgraph")
def api_kg_subgraph():
```

### R7: sync_kg_to_r1d3.py（scripts/sync_kg_to_r1d3.py）— 新增

**职责**：将 API 输出转换为 R1D3 可读的 markdown 格式。

**不直接读写 state.json**，只调用 API 或 Root Tracer。

```bash
python3 scripts/sync_kg_to_r1d3.py --topic "metacognitive monitoring"
  → memory/curious/kg/trace/metacognitive-monitoring.md

python3 scripts/sync_kg_to_r1d3.py --roots
  → memory/curious/kg/roots.md

python3 scripts/sync_kg_to_r1d3.py --overview
  → memory/curious/kg/overview.md

python3 scripts/sync_kg_to_r1d3.py --all  # 全量同步（可选 cron）
```

**输出格式示例（markdown for R1D3）**：
```markdown
# Trace: metacognitive monitoring in LLM agents
- quality: 10.51

## 因果链
1. metacognitive monitoring in LLM agents (current)
2. → self-reflection mechanisms (derived_from)
3. → ReAct loop (derived_from)
4. → transformer attention ⭐ ROOT (root_score: 9.2)

## 跨子图连接
- RLHF (shared concept: reward signal evaluation)

## 根技术
- transformer attention (root_score: 9.2, confidence: 0.91)
```

---

## 可视化设计（UI 层）

复用 `ui/` 现有框架，逐步增强。

### Trace View（溯源视图）
- 从任意 topic 向上追溯到根（纵向树状图）
- 根节点 gold + 双圈高亮
- 跨子图边用虚线标注

### KG Overview（全图视图）
- 所有 topic 节点按探索分支聚类（domain coloring）
- 根节点特殊边框（双圈）
- 节点大小可切换（quality 或 root_score）

### Root Pool View（根技术池）
- 按 root_score 排序
- 显示 cross_domain_count + explains_count

### Subgraph Filter（筛选器）
- Branch filter / Time slider / Quality threshold / Root only toggle

### Anomaly Detection View（异常检测）
- 孤立节点（红虚线）、高入度低质量（黄警告）、边界根候选（绿脉冲）

**实现顺序**：Trace View → KG Overview → Root Pool → Filter → Anomaly

---

## 实现任务

| Task | 组件 | 类型 | 描述 | 优先级 |
|------|------|------|--------|--------|
| T-1 | knowledge_graph.py schema | 修改 | topic 结构追加 parents/explains/cross_domain_count/root_score | P0 |
| T-2 | knowledge_graph.add_parent() | 修改 | 双向写入 parents + explains | P0 |
| T-3 | knowledge_graph.get_trace() | 修改 | 向上追溯链路 | P0 |
| T-4 | knowledge_graph.init_root_pool() | 修改 | 从 config 注入初始种子 | P0 |
| T-5 | Parent Tracker | 新增 | 探索时记录 parent | P0 |
| T-6 | Root Tracer | 新增 | trace/roots/overview 读取接口 | P0 |
| T-7 | curious_api.py 路由 | 修改 | `/api/kg/trace/<topic>`, `/api/kg/roots`, `/api/kg/overview` | P0 |
| T-8 | sync_kg_to_r1d3.py | 新增 | R1D3 markdown 消费脚本 | P0 |
| T-9 | 迁移脚本 | 新增 | 旧数据迁移到新 schema（补 parents/explains） | P1 |
| T-10 | Cross-Subgraph Detector | 新增 | 检测跨分支连接 | P1 |
| T-11 | Root Technology Writer | 新增 | 管理 root_technology_pool | P1 |
| T-12 | Anomaly Detection API | 修改 | `/api/kg/anomalies` | P1 |
| T-13 | Subgraph Filter API | 修改 | `/api/kg/subgraph` | P1 |
| T-14 | Trace View UI | 修改 | 溯源视图 | P0 |
| T-15 | KG Overview UI | 修改 | 全图视图 | P0 |
| T-16 | Root Pool View UI | 修改 | 根技术池视图 | P1 |
| T-17 | 测试验证 | — | trace 链路 + roots 浮现 + sync 脚本 | P0 |

---

## 验收标准

1. `add_exploration_result(topic, result, quality, parent_topic)` 被调用时，parent 信息写入 `topics[topic]["parents"]` 和 `topics[parent]["explains"]`
2. `/api/kg/trace/metacognitive%20monitoring` 返回完整向上链路（至少含 level 0 ~ root）
3. `/api/kg/roots` 返回按 root_score 降序排列的根技术列表
4. transformer attention 从 initial_seeds 注入后在 root_technology_pool 中可见
5. `sync_kg_to_r1d3.py --topic X` 输出 markdown 格式的 trace 到 `memory/curious/kg/trace/`
6. 已有 KG 数据通过 T-9 迁移脚本后能显示父子关系（不要求完整，但要有边）
7. Cross-Subgraph Detector 在 cross_domain_count ≥ 3 时触发 root_candidate_elevated 事件

---

## 不在 v0.2.5 范围内

- 新建独立的 KG 服务进程
- 3D 图、Force-directed animation、复杂粒子效果
- 新的探索策略
- 多 Provider 并行优化

---

_Last updated: 2026-03-27 by R1D3_
_v0.2.5 principles: incremental-first, reuse existing, high-cohesion-low-coupling, dual-consumer compatible_
