# SPEC v0.2.6 — 记忆巩固 & 关键重组

> **唯一目标**: 让 CA 的知识图谱从"数据存储"进化为"活的知识网络"
> **架构原则**: 独立线程运行，不阻塞探索主循环，不改变现有探索逻辑，API 为单一事实来源

---

## 变更概览

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/consolidation_engine.py` | 新增 | 记忆巩固引擎 |
| `core/reorganization_engine.py` | 新增 | 关键重组引擎 |
| `core/sleep_pruner.py` | 新增 | 突触修剪器（仅处理孤立节点） |
| `core/knowledge_graph.py` | 修改 | 新增 dormant 状态、连接强化 API |
| `core/curious_api.py` | 修改 | 新增 consolidation/reorganization 控制 API |
| `curious_agent.py` | 修改 | 启动时初始化三个后台线程 |

**新增模块数：3 个**（consolidation_engine, reorganization_engine, sleep_pruner）

---

## 一、核心概念定义

### 1.1 记忆巩固（Memory Consolidation）

**定义**：把新探索的"孤立知识点"整合进已有知识网络，强化节点间的连接。

**类比**：人类睡眠时，短时记忆被转移到海马体，与已有的长时记忆建立连接。

**CA 的实现**：
- 新 topic 入 KG 后，每隔 N 分钟，consolidation_engine 检查它和已有节点的关系
- 共同出现的 parent/children → 强化连接权重
- 接近的语义 topic → 主动建立关联

### 1.2 关键重组（Key Reorganization）

**定义**：无目的的自由联想，在远距离节点间强制建立可能的关联。

**类比**：人类梦境中两个完全不相关的东西产生奇怪的连接。

**CA 的实现**：
- reorganization_engine 定期从 KG 抽取远距离节点对
- 强制让 LLM 判断"这两个 topic 之间有没有可能的关联"
- 有意义 → 写入 KG.explains；无意义 → 跳过

### 1.3 突触修剪（Synaptic Pruning）

**定义**：把长期无价值的孤立节点降级为 dormant，不参与活跃探索。

**标准**（同时满足）：
- parents = [] 且 children = [] 且 explains = []
- quality < 7.0（无高质量探索结果）

**处理**：标记为 dormant，不删除数据，可召回。

---

## 二、consolidation_engine.py

### 2.1 运行模式

独立线程，固定间隔触发（默认每 15 分钟一次）。

```python
class ConsolidationEngine:
    def __init__(self, interval_minutes: int = 15):
        self.interval = interval_minutes
        self._running = False

    def start(self):
        """启动巩固线程"""
        self._running = True
        self._thread = Thread(target=self._consolidation_loop, daemon=True)
        self._thread.start()

    def _consolidation_loop(self):
        while self._running:
            self.consolidate_recent()
            self.strengthen_existing_connections()
            sleep(self.interval * 60)

    def consolidate_recent(self):
        """
        巩固最近 N 小时内的探索结果
        1. 检查新 topic 的 parent/children 和已有节点的关系
        2. 共同出现多次 → 强化连接
        3. 语义接近 → 主动建立关联
        """

    def strengthen_existing_connections(self):
        """
        扫描已有 KG，检查：
        1. 同一 parent 下的 sibling topics 是否应该建立横向关联
        2. 高质量节点是否应该提升其 neighbors 的权重
        """
```

### 2.2 核心逻辑

```python
def consolidate_recent(self, hours: int = 24):
    """
    扫描最近 hours 小时内的探索结果
    对每个 recent_topic：
        1. 获取其 parent（如果有）
        2. 获取其 explored_children（如果有）
        3. 检查 siblings 之间是否有隐藏关联
        4. 如果发现 strong_association → kg.add_association()
    """

def strengthen_connections(self):
    """
    强化已有连接：
    - 如果 topic A 和 B 共同出现在同一个 exploration_log 条目中
    - 且频率 >= 3 → 提升双向连接权重
    """
```

---

## 三、reorganization_engine.py

### 3.1 运行模式

独立线程，固定间隔触发（默认每 30 分钟一次，与 consolidation 分开）。

```python
class ReorganizationEngine:
    def __init__(self, interval_minutes: int = 30, pairs_per_cycle: int = 5):
        self.interval = interval_minutes
        self.pairs_per_cycle = pairs_per_cycle
        self._running = False

    def start(self):
        self._running = True
        self._thread = Thread(target=self._reorganization_loop, daemon=True)
        self._thread.start()

    def _reorganization_loop(self):
        while self._running:
            self.creative_association()
            sleep(self.interval * 60)

    def creative_association(self):
        """
        随机选取 pairs_per_cycle 对远距离节点
        强制 LLM 判断："node_A 和 node_B 之间有没有可能的关联？"
        """
```

### 3.2 远距离节点选取

```python
def get_distant_pairs(self, max_pairs: int = 5) -> list[tuple]:
    """
    从 KG 中选取距离远且没有连接的节点对

    选取标准：
    1. 两节点间不存在 path（或 path length > 3）
    2. 两节点均有 quality >= 4（有一定探索深度）
    3. 优先选取不同探索分支的节点（cross-domain）

    Returns: list of (node_a, node_b, distance_estimate)
    """
```

### 3.3 LLM 关联判断

```python
def ask_llm_association(self, topic_a: str, topic_b: str) -> dict:
    """
    问 LLM："topic_A 和 topic_B 之间有没有可能的关联？"

    Prompt:
    你是一个知识关联分析器。
    给出两个完全独立的知识点，请判断它们之间是否存在潜在的关联。
    即使没有已知关联，也可以基于领域知识推测可能的连接。

    Topic A: {topic_a}
    Topic B: {topic_b}

    请输出：
    1. 是否有潜在关联: yes/no
    2. 关联类型: (causal, analogical, shared_foundation, hierarchical, none)
    3. 关联描述: 一段话描述关联内容
    4. 置信度: 0.0-1.0

    Returns: {has_association, relation_type, description, confidence}
    """

def add_association(self, topic_a: str, topic_b: str, llm_result: dict):
    """
    如果 llm_result['has_association'] && llm_result['confidence'] >= 0.7:
        kg.add_explains(topic_a, topic_b, relation_type, confidence)
        kg.add_explains(topic_b, topic_a, relation_type, confidence)
    """
```

---

## 四、sleep_pruner.py

### 4.1 降级标准

```python
def should_dormant(self, topic: str, kg_state: dict) -> bool:
    """
    节点同时满足以下条件 → 降级为 dormant：
    1. parents = [] 且 children = [] 且 explains = []
    2. quality < 7.0（无高质量探索结果）
    3. 不是 root_technology_pool 中的候选根技术
    """
    node = kg_state["knowledge"]["topics"].get(topic, {})
    pool_names = {r["name"] for r in kg_state.get("root_technology_pool", {}).get("candidates", [])}

    return (
        len(node.get("parents", [])) == 0
        and len(node.get("children", [])) == 0
        and len(node.get("explains", [])) == 0
        and node.get("quality", 0) < 7.0
        and topic not in pool_names
    )
```

### 4.2 运行模式

独立线程，每 60 分钟一次。

```python
class SleepPruner:
    def __init__(self, interval_minutes: int = 60):
        self.interval = interval_minutes
        self._running = False

    def start(self):
        self._running = True
        self._thread = Thread(target=self._prune_loop, daemon=True)
        self._thread.start()

    def _prune_loop(self):
        while self._running:
            dormant_count = self.prune_isolated_nodes()
            print(f"[SleepPruner] {dormant_count} nodes moved to dormant")
            sleep(self. interval * 60)
```

---

## 五、knowledge_graph.py 修改

### 5.1 新增 dormant 状态

```python
# Topic status 新增
STATUS_DORMANT = "dormant"  # 降级节点，不参与活跃探索
```

### 5.2 新增 API

```python
def mark_dormant(topic: str) -> None:
    """将节点标记为 dormant"""
    state = _load_state()
    if topic in state["knowledge"]["topics"]:
        state["knowledge"]["topics"][topic]["status"] = STATUS_DORMANT
        state["knowledge"]["topics"][topic]["dormant_since"] = datetime.now(timezone.utc).isoformat()
        _save_state(state)

def reactivate(topic: str) -> None:
    """从 dormant 恢复为 partial"""
    state = _load_state()
    if topic in state["knowledge"]["topics"]:
        state["knowledge"]["topics"][topic]["status"] = "partial"
        state["knowledge"]["topics"][topic].pop("dormant_since", None)
        _save_state(state)

def add_explains(from_topic: str, to_topic: str, relation: str, confidence: float):
    """添加 explains 连接"""
    state = _load_state()
    topics = state["knowledge"]["topics"]

    if "explains" not in topics.setdefault(from_topic, {}):
        topics[from_topic]["explains"] = []

    explains_entry = {"target": to_topic, "relation": relation, "confidence": confidence}
    if explains_entry not in topics[from_topic]["explains"]:
        topics[from_topic]["explains"].append(explains_entry)

    topics[from_topic]["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)

def get_dormant_nodes() -> list[str]:
    """返回所有 dormant 节点"""
    state = _load_state()
    return [
        name for name, node in state["knowledge"]["topics"].items()
        if node.get("status") == STATUS_DORMANT
    ]

def strengthen_connection(topic_a: str, topic_b: str):
    """
    强化两节点间的连接权重
    实现：增加 shared_access_count 或类似权重字段
    """
```

---

## 六、curious_api.py 修改

```python
# === v0.2.6 记忆巩固 & 重组 API ===

@app.route("/api/consolidation/run", methods=["POST"])
def api_consolidation_run():
    """手动触发一次记忆巩固"""
    from core.consolidation_engine import ConsolidationEngine
    engine = ConsolidationEngine()
    engine.consolidate_recent()
    return jsonify({"status": "ok", "message": "Consolidation completed"})


@app.route("/api/reorganization/run", methods=["POST"])
def api_reorganization_run():
    """手动触发一次关键重组"""
    from core.reorganization_engine import ReorganizationEngine
    engine = ReorganizationEngine()
    associations = engine.creative_association()
    return jsonify({"status": "ok", "associations_created": len(associations)})


@app.route("/api/kg/dormant", methods=["GET"])
def api_kg_dormant():
    """返回所有 dormant 节点"""
    from core.knowledge_graph import get_dormant_nodes
    return jsonify({"dormant_nodes": get_dormant_nodes()})


@app.route("/api/kg/reactivate", methods=["POST"])
def api_kg_reactivate():
    """恢复 dormant 节点"""
    from core.knowledge_graph import reactivate
    data = request.get_json()
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic is required"}), 400
    reactivate(topic)
    return jsonify({"status": "ok", "topic": topic})
```

---

## 七、curious_agent.py 修改

### 7.1 主程序初始化

```python
# 在 daemon_mode() 启动时，初始化三个后台线程
def daemon_mode(interval_minutes=30):
    from core.consolidation_engine import ConsolidationEngine
    from core.reorganization_engine import ReorganizationEngine
    from core.sleep_pruner import SleepPruner

    # 初始化并启动三个后台线程
    consolidator = ConsolidationEngine(interval_minutes=15)
    reorganizer = ReorganizationEngine(interval_minutes=30)
    pruner = SleepPruner(interval_minutes=60)

    consolidator.start()
    reorganizer.start()
    pruner.start()

    print(f"[v0.2.6] Background threads started:")
    print(f"  - ConsolidationEngine: every 15 min")
    print(f"  - ReorganizationEngine: every 30 min")
    print(f"  - SleepPruner: every 60 min")

    # ... 原有 daemon 循环
```

---

## 八、不修改的内容

以下现有模块**不需要任何修改**，v0.2.6 的三个新引擎是纯新增，不触碰任何现有逻辑：

- `curious_decomposer.py` — 不修改
- `quality_v2.py` — 不修改
- `three_phase_explorer.py` — 不修改
- `async_explorer.py` — 不修改
- `curiosity_engine.py` — 不修改
- `meta_cognitive_monitor.py` — 不修改
- `agent_behavior_writer.py` — 不修改

---

## 九、熟练经验 Agent 接口（外部消费）

v0.2.6 不实现熟练经验 Agent，仅定义 CA 的输出接口供外部消费：

```
CA 探索完成 → shared_knowledge/ca/discoveries/{topic}.md
    ↓ 熟练经验 Agent 消费
分析执行序列 → 生成 Pattern
```

CA 的 consolidated KG 数据通过以下 API 暴露：
- `GET /api/kg/overview` — 全局视图
- `GET /api/kg/trace/<topic>` — 因果链路

---

## 十、验收标准

```bash
# 1. 三个后台线程正常启动
curl http://localhost:4848/api/curious/state | python3 -c "import sys,json; d=json.load(sys.stdin); print('status:', d.get('status'))"

# 2. 手动触发巩固
curl -X POST http://localhost:4848/api/consolidation/run

# 3. 手动触发重组
curl -X POST http://localhost:4848/api/reorganization/run

# 4. 检查 dormant 节点
curl http://localhost:4848/api/kg/dormant

# 5. 恢复 dormant 节点
curl -X POST http://localhost:4848/api/kg/reactivate \
  -H "Content-Type: application/json" \
  -d '{"topic":"某个dormant节点"}'

# 6. 验证孤立节点被降级
# 运行 pruner 后，检查孤立节点 status 变为 dormant
```

---

_Last updated: 2026-03-28 by R1D3_
_v0.2.6: 3 new modules, 1 KG modification, API additions_
