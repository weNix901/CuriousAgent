# SPEC v0.2.6 — 持续做梦 & 记忆巩固

> **核心目标**: 让 CA 从"探索引擎"进化为"持续学习的数字生命体"
> **架构原则**: 探索和做梦同时运行，共享同一张 KG，无全局锁，节点级协调
> **更新**: 2026-03-28（并发架构 + 节点级锁 + 做梦公平性 + 权重修剪）

---

## 变更概览

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/spider_agent.py` | 新增 | 持续探索进程（重构自现有探索逻辑） |
| `core/dream_agent.py` | 新增 | 持续做梦重组进程（含 consolidation + reorganization） |
| `core/sleep_pruner.py` | 新增 | 突触修剪器（权重感知） |
| `core/knowledge_graph.py` | 修改 | 新增 dormant 状态、explains、last_consolidated、connection_weight、节点级锁 |
| `core/consolidation_engine.py` | 删除 | 合并入 dream_agent |
| `core/reorganization_engine.py` | 删除 | 合并入 dream_agent |
| `curious_agent.py` | 修改 | 启动三个并发进程 |
| `curious_api.py` | 修改 | 新增控制 API |

**核心变化**: 合并 consolidation + reorganization → dream_agent；定时调度 → 事件驱动并发；新增做梦公平性机制；新增权重感知修剪

---

## 一、核心概念

### 1.1 三层梦境体系

| 层次 | 人类梦境 | CA 对应 | 特征 |
|------|---------|---------|------|
| **浅层** | 浅睡时的记忆激活 | SpiderAgent 探索 | 队列驱动，持续 |
| **中层** | REM 睡眠的创意做梦 | DreamAgent 重组 | 双队列驱动，持续，公平 |
| **深层** | 记忆巩固 & 突触修剪 | DreamAgent + SleepPruner | Hebbian 强化 + 权重感知修剪 |

### 1.2 进程间协调原则

**核心洞察**: 冲突只在两进程操作**同一节点**时发生。

- SpiderAgent 写入: `children`, `quality`, `status`, `sources`, `explored_children`
- DreamAgent 写入: `explains`, `parents`（新增连接）
- 两者写入**不同字段**，即使同一节点也语义独立

**协调策略**: 节点级锁，非全局锁。

**死锁预防**: 按节点名字排序锁顺序后再获取。

### 1.3 做梦公平性

**问题**: 当前设计只对"新探索的节点"触发关联重组，老节点永远没有做梦机会。

**解决方案**: DreamAgent 使用双队列：

```
高优先级队列: SpiderAgent 通知的新节点（立即处理）
低优先级队列: KG 中所有节点轮流加入（确保公平）

→ 每个 KG 节点都有机会被做梦处理
→ 不依赖新节点触发
```

### 1.4 记忆时效性

**新增字段**: `last_consolidated` — 节点最近一次被巩固的时间戳

- 未巩固的节点：可以参与强化（刚探索完）
- 已巩固的节点：降低强化频率，避免重复巩固

### 1.5 连接权重

**新增字段**: `connection_weight` — 连接强度（0.0-1.0）

- 新建的 explains 连接：初始 weight = 0.5
- 被多次共现强化：weight 逐渐上升
- SleepPruner 基于权重而非二元判断（有无连接）

---

## 二、SpiderAgent（持续探索进程）

### 2.1 职责

- 持续从 curiosity_queue 选择 topic 执行探索
- 探索结果写入 KG
- 探索完成后，唤醒 DreamAgent（通过高优先级队列）

### 2.2 运行逻辑

```python
class SpiderAgent:
    def __init__(self, to_dreamer_queue):
        self.to_dreamer_queue = to_dreamer_queue  # 高优先级队列

    def run(self):
        """主循环：选择 → 探索 → 写入 KG → 通知 DreamAgent"""
        while True:
            topic = self.engine.select_next()

            if topic is None:
                topic = self.engine.generate_new()

            result = self.explorer.explore(topic)

            # 写入 KG（带节点级锁）
            self.kg_add_with_lock(topic, result)

            # 通知 DreamAgent 处理新节点（高优先级）
            self.to_dreamer_queue.put(("high", topic))

            # consolidation：强化共现连接（无锁，纯数据写）
            self.strengthen_co_occurring(topic)

            yield_to_other_process()
```

### 2.3 consolidation：强化共现连接

```python
def strengthen_co_occurring(self, topic: str):
    """
    基于 Hebbian 原则：一起激活过的连接应强化

    规则：
    - 只强化 last_updated 在 24 小时内的连接
    - 每次共现，weight += 0.1，上限 1.0
    """
    related = self.kg.get_related_nodes(topic)

    for node in related:
        # 检查 topic 和 node 是否在最近 24h 内共同出现
        if self.exploration_history.co_occurred(topic, node, within_hours=24):
            # 强化连接权重
            self.kg.strengthen_connection(topic, node, delta=0.1)

    # 更新 last_consolidated
    self.kg.set_consolidated(topic)
```

---

## 三、DreamAgent（持续做梦重组进程）

### 3.1 职责

- 持续监听高优先级队列（新节点）和低优先级队列（轮流节点）
- 对每个节点，扫描远距离节点的关联
- 强制 LLM 判断关联是否存在
- 发现有意义连接 → 写入 explains（含 connection_weight）

### 3.2 双队列设计

```python
class DreamAgent:
    def __init__(self, high_priority_queue, low_priority_queue):
        self.high_queue = high_priority_queue  # SpiderAgent 通知的新节点
        self.low_queue = low_priority_queue    # 所有节点轮流

    def run(self):
        while True:
            # 高优先级队列有内容 → 立即处理
            # 高优先级队列空 → 从低优先级队列取
            if not self.high_queue.empty():
                priority, topic = self.high_queue.get()
            else:
                topic = self.low_queue.get()  # 阻塞等待

            self.process_associations(topic)
            yield_to_other_process()
```

### 3.3 低优先级队列的填充策略

```python
class DreamAgent:
    def fill_low_priority_queue(self):
        """
        确保 KG 中所有未处理的节点轮流进入低优先级队列

        策略：
        1. 扫描 KG 中所有节点
        2. 排除最近 7 天内已处理过的节点
        3. 剩余节点按 quality 排序（低 quality 优先，接近"遗忘"的知识优先做梦）
        4. 全部加入低优先级队列
        """
        all_nodes = self.kg.get_all_nodes()
        recently_processed = self.kg.get_recently_dreamed(within_days=7)

        # build candidates as list of (name, node) tuples
        candidates = [
            (name, node) for name, node in all_nodes
            if name not in recently_processed
            and node.get("status") != STATUS_DORMANT
        ]

        # quality 低的优先（"快要遗忘"的值得做梦）
        candidates.sort(key=lambda item: item[1].get("quality", 0))

        for name, _ in candidates:
            self.low_queue.put(name)
```

**触发条件**：低优先级队列为空时，自动触发 fill_low_priority_queue。

### 3.4 运行逻辑

```python
    def process_associations(self, topic: str):
        """对单个 topic 扫描远距离关联"""
        distant_pairs = self.find_distant_pairs(topic)

        for distant_node, distance in distant_pairs:
            result = self.llm_ask_association(topic, distant_node)

            if result["has_association"] and result["confidence"] >= 0.7:
                self.kg_write_with_lock(topic, distant_node, result)

        # 标记为已做梦处理
        self.kg.mark_dreamed(topic)
```

### 3.5 远距离节点选取

```python
    def find_distant_pairs(self, topic: str, max_pairs: int = 5) -> list:
        """
        选取与 topic 距离远且无连接的节点

        标准：
        - 两节点间不存在 path（或 length > 3）
        - 两节点 quality >= 4
        - 优先跨 domain（不同探索分支）
        - 随机性：加入随机采样，不总是选最近/最远的
        """
        all_nodes = self.kg.get_all_nodes(active_only=True)

        # 过滤已有连接的节点
        connected = self.kg.get_directly_connected(topic)
        distant_candidates = [n for n in all_nodes if n not in connected]

        # 过滤距离近的（path length <= 3）
        def distance(node):
            return self.kg.get_shortest_path_length(topic, node)

        distant = [n for n in distant_candidates if distance(n) > 3]

        # 随机选取 + quality 过滤
        import random
        sampled = random.sample(
            [n for n in distant if n.get("quality", 0) >= 4],
            min(max_pairs, len(distant))
        )

        return [(n, distance(n)) for n in sampled]
```

### 3.6 LLM 关联判断

```python
    def llm_ask_association(self, topic_a: str, topic_b: str) -> dict:
        """
        强制 LLM 判断两个节点是否有意外关联

        Returns: {
            has_association: bool,
            relation_type: "causal" | "analogical" | "shared_foundation" | "hierarchical" | "none",
            description: str,
            confidence: float  # 0.0-1.0
        }
        """
```

### 3.7 与 SpiderAgent 的协调

```
SpiderAgent: 写新节点 → 高优先级队列
DreamAgent:  监听高优先级队列 + 低优先级轮流队列
```

两者操作**不同节点时**：零冲突。
两者操作**同一节点时**：节点级锁保护。

---

## 四、SleepPruner（突触修剪器）

### 4.1 职责

- 定时扫描 KG，识别弱连接节点
- 基于 connection_weight 降级低价值节点为 dormant

### 4.2 降级标准（含权重）

**核心原则**：pruning 只对 explains 连接检查权重，不对 parent/child 做权重判断。

- parent/child 是结构性的，二元存在性（有无），不区分强弱
- explains 是创意连接，有权重，可以被判定为"弱"

```
节点同时满足以下条件 → 降级为 dormant：
1. parents = [] 且 children = []（结构上真正孤立）
2. explains 的平均 weight < 0.3（创意连接也弱）
3. quality < 7.0
4. 非 root_technology_pool 候选
5. 非最近 7 天内有过 explains 新建连接的节点
```

### 4.3 运行逻辑

```python
class SleepPruner:
    def __init__(self, interval_minutes=60):
        self.interval = interval_minutes

    def run(self):
        while True:
            dormant_count = self.scan_and_prune()
            print(f"[SleepPruner] {dormant_count} nodes → dormant")
            sleep(self.interval * 60)

    def scan_and_prune(self) -> int:
        """扫描弱连接节点，降级为 dormant"""
        all_nodes = self.kg.get_all_nodes(active_only=True)
        pool_names = self.kg.get_root_pool_names()

        count = 0
        for node_name, node in all_nodes:
            if node_name in pool_names:
                continue

            # 1. 检查结构性连接：parents + children
            parents = self.kg.get_parents(node_name)
            children = self.kg.get_children(node_name)
            has_structural = (len(parents) > 0 or len(children) > 0)

            if has_structural:
                # 有结构性连接，不修剪
                continue

            # 2. 检查 explains 连接的权重
            explains = self.kg.get_explains(node_name)
            if not explains:
                # 既无结构性连接，也无 explains → 真正孤立
                avg_weight = 0.0
            else:
                weights = [e.get("weight", 0.0) for e in explains]
                avg_weight = sum(weights) / len(weights)

            # 3. 最近 7 天有新连接，保留
            if self.kg.has_recent_explains(node_name, within_days=7):
                continue

            # 4. 判断是否降级
            if avg_weight < 0.3 and node.get("quality", 0) < 7.0:
                self.kg.mark_dormant(node_name)
                count += 1

        return count
```

---

## 五、知识图谱修改

### 5.1 新增字段

```python
# 节点状态
STATUS_DORMANT = "dormant"  # 不参与活跃探索

# 节点字段（新增）
last_consolidated: str | None   # ISO 时间戳，最近一次被巩固
dreamed_at: str | None          # ISO 时间戳，最近一次做梦处理

# 连接字段（新增）
connection_weight: float        # 连接强度 0.0-1.0，default 0.5
```

### 5.2 新增 API

```python
def add_explains(from_topic: str, to_topic: str, relation: str, confidence: float, weight: float = 0.5):
    """添加 explains 连接，含权重"""

def strengthen_connection(topic_a: str, topic_b: str, delta: float = 0.1):
    """
    强化两节点连接
    - 如果连接存在：weight += delta，上限 1.0
    - 如果连接不存在：不操作（consolidation 只强化已有连接）
    """

def set_consolidated(topic: str):
    """标记节点已巩固"""

def mark_dormant(topic: str):
    """标记为 dormant"""

def reactivate(topic: str):
    """从 dormant 恢复"""

def mark_dreamed(topic: str):
    """标记节点已做过梦处理"""

def get_all_connections(topic: str) -> list[dict]:
    """
    返回 topic 的所有连接（含 weight）
    - parents, children, explains 统一格式
    """

def get_all_nodes(active_only: bool = False) -> list[tuple[str, dict]]:
    """
    返回 KG 中所有节点
    active_only=True: 排除 dormant 节点
    Returns: list of (node_name, node_data)
    """

def get_directly_connected(topic: str) -> set[str]:
    """
    返回与 topic 直接相连的所有节点（parents + children + explains）
    用于 find_distant_pairs 时过滤已有连接的节点
    """

def get_shortest_path_length(topic_a: str, topic_b: str) -> int | float:
    """
    返回 topic_a 到 topic_b 的最短路径长度
    如果不存在路径，返回 inf
    """

def get_parents(topic: str) -> list[dict]:
    """返回 topic 的 parents 连接（无权重字段）"""

def get_children(topic: str) -> list[dict]:
    """返回 topic 的 children 连接（无权重字段）"""

def get_explains(topic: str) -> list[dict]:
    """返回 topic 的 explains 连接（含 weight 字段）"""

def has_recent_explains(topic: str, within_days: int) -> bool:
    """检查节点最近 N 天是否有新的 explains 连接"""

def get_root_pool_names() -> set[str]:
    """返回 root_technology_pool 中所有候选名称"""

def get_recently_dreamed(within_days: int) -> set[str]:
    """
    返回最近 within_days 天内被 DreamAgent 处理过的节点名称
    用于 fill_low_priority_queue 时排除近期已处理的节点
    """
```

### 5.3 节点级锁实现

```python
import threading
from weakref import WeakValueDictionary

class NodeLockRegistry:
    """
    节点级锁注册表
    - 同一节点用同一把锁
    - 节点销毁时锁自动释放（WeakValueDictionary）
    """
    _locks = WeakValueDictionary()

    @classmethod
    def get_lock(cls, node_name: str) -> threading.Lock:
        if node_name not in cls._locks:
            cls._locks[node_name] = threading.Lock()
        return cls._locks[node_name]


def kg_write_with_lock(from_topic: str, to_topic: str, result: dict):
    """
    带节点级锁的写入（DreamAgent 使用）
    确保和 SpiderAgent 不会同时写同一节点

    死锁预防：按节点名字排序锁顺序后再获取
    """
    lock_a = NodeLockRegistry.get_lock(from_topic)
    lock_b = NodeLockRegistry.get_lock(to_topic)

    # 按名字排序，确保全局顺序一致
    locks = sorted([lock_a, lock_b], key=lambda l: id(l))

    with locks[0], locks[1]:
        add_explains(
            from_topic, to_topic,
            result["relation_type"], result["confidence"],
            weight=0.5  # 新建连接默认权重 0.5
        )
```

---

## 六、curious_agent.py 修改

### 6.1 主程序

```python
def daemon_mode(interval_minutes=30):
    from core.spider_agent import SpiderAgent
    from core.dream_agent import DreamAgent
    from core.sleep_pruner import SleepPruner
    from queue import Queue

    # 双队列：SpiderAgent → DreamAgent
    high_priority_queue = Queue()    # 新节点（高优先级）
    low_priority_queue = Queue()    # 轮流队列（低优先级）

    # 初始化并启动三个并发进程
    spider = SpiderAgent(high_priority_queue)
    dreamer = DreamAgent(high_priority_queue, low_priority_queue)
    pruner = SleepPruner(interval_minutes=60)

    spider.start()
    dreamer.start()
    pruner.start()

    print(f"[v0.2.6] Concurrent processes started:")
    print(f"  - SpiderAgent: continuous exploration")
    print(f"  - DreamAgent: continuous dreaming (high + low priority queues)")
    print(f"  - SleepPruner: pruning every {pruner.interval} min")

    spider.join()
    dreamer.join()
    pruner.join()
```

---

## 七、API 修改

```python
# === v0.2.6 新增 ===

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


@app.route("/api/dreamer/force", methods=["POST"])
def api_dreamer_force():
    """强制 DreamAgent 处理指定 topic"""
    from core.dream_agent import force_process_topic
    data = request.get_json()
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic is required"}), 400
    associations = force_process_topic(topic)
    return jsonify({"status": "ok", "associations_created": len(associations)})


@app.route("/api/kg/connection/<path:topic>", methods=["GET"])
def api_kg_connection(topic: str):
    """获取节点所有连接（含权重）"""
    from core.knowledge_graph import get_all_connections
    return jsonify({"topic": topic, "connections": get_all_connections(topic)})
```

---

## 八、验收标准

```bash
# 1. 三个进程正常启动
curl http://localhost:4848/api/curious/state

# 2. 注入话题后，DreamAgent 高优先级处理
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"test dreaming","score":7.0,"depth":6.0}'

# 3. 手动触发 DreamAgent 处理
curl -X POST http://localhost:4848/api/dreamer/force \
  -H "Content-Type: application/json" \
  -d '{"topic":"metacognitive monitoring"}'

# 4. 检查 dormant 节点
curl http://localhost:4848/api/kg/dormant

# 5. 恢复 dormant 节点
curl -X POST http://localhost:4848/api/kg/reactivate \
  -H "Content-Type: application/json" \
  -d '{"topic":"某个dormant节点"}'

# 6. 检查节点连接权重
curl http://localhost:4848/api/kg/connection/metacognitive\ monitoring

# 7. 验证低优先级队列填充（观察日志）
# 当高优先级队列为空时，应自动从 KG 填充低优先级队列
```

---

## 九、三层做梦能力 vs 人类梦境

| 层次 | 人类做梦 | CA 实现 | 满足程度 |
|------|---------|---------|---------|
| 浅层探索 | 队列驱动探索 | SpiderAgent 持续运行 | ✅ 完全满足 |
| 浅层巩固 | Hebbian（共现强化） | strengthen_co_occurring() + last_consolidated | ✅ 完全满足 |
| 中层做梦 | 创意关联重组 + 公平对待所有记忆 | DreamAgent 双队列 + 轮流队列 | ✅ 完全满足 |
| 深层修剪 | 弱连接清理（权重感知） | SleepPruner + connection_weight | ✅ 完全满足 |

---

## 十、模块依赖关系

```
curious_agent.py (入口)
    ├── SpiderAgent
    │   ├── CuriosityEngine
    │   ├── Explorer
    │   └── KnowledgeGraph (with node-level locks)
    ├── DreamAgent
    │   ├── LLMClient
    │   ├── high_priority_queue (来自 SpiderAgent)
    │   ├── low_priority_queue (轮流填充)
    │   └── KnowledgeGraph (with node-level locks)
    └── SleepPruner
        └── KnowledgeGraph
```

---

_Last updated: 2026-03-28 by R1D3_
_v0.2.6: concurrent SpiderAgent + DreamAgent + SleepPruner, node-level locking, dual-queue fairness, weight-aware pruning_
