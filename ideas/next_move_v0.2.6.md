# SPEC v0.2.6 — 持续做梦 & 记忆巩固

> **核心目标**: 让 CA 从"探索引擎"进化为"持续学习的数字生命体"
> **架构原则**: 三个独立进程并发运行，共享同一张 KG，节点级协调，无全局锁
> **更新**: 2026-03-28 17:03（按特性重组 + 实现顺序 + 进程边界修正）
> **设计原则**: SpiderAgent 和 DreamAgent 是完全独立的进程，不合并；两者的 LLM 用途不同

---

## 特性概览（Features）

| 特性 | 名称 | 优先级 | 类型 |
|------|------|--------|------|
| F1 | 三进程架构 | P0 | 架构 |
| F2 | KG Schema 扩展 | P0 | 数据 |
| F3 | 节点级锁 | P0 | 基础设施 |
| F4 | ExplorationHistory（线程安全） | P0 | 基础设施 |
| F5 | SpiderAgent（独立探索进程） | P0 | 新模块 |
| F6 | SleepPruner（定时修剪进程） | P0 | 新模块 |
| F7 | 双队列 + 轮询指针 | P0 | 新模块 |
| F8 | DreamAgent（独立做梦进程） | P0 | 新模块 |
| F9 | 创意做梦引擎（生成式） | P0 | 功能 |
| F10 | 洞察验证回路 | P1 | 功能 |
| F11 | SharedInbox（Dream→Spider 通信） | P0 | 通信 |
| F12 | MetaCognitiveMonitor 增强 | P1 | 功能 |
| F13 | API 扩展 | P2 | 接口 |
| F14 | R1D3 Skill 同步 | P2 | 集成 |

---

## 实现顺序（Implementation Order）

```
第一阶段：基础设施（必须先完成）
├── F2: KG Schema 扩展         ← 数据结构先行
├── F3: 节点级锁              ← 并发安全基础
└── F4: ExplorationHistory 线程安全 ← 共享数据安全

第二阶段：核心进程（三个独立进程）
├── F1: 三进程架构             ← 进程骨架
├── F5: SpiderAgent            ← 探索进程
├── F6: SleepPruner           ← 修剪进程
└── F8: DreamAgent            ← 做梦进程

第三阶段：进程间通信
├── F7: 双队列 + 轮询指针      ← DreamAgent 的输入
└── F11: SharedInbox         ← Dream→Spider 的单向通信

第四阶段：核心功能
├── F9: 创意做梦引擎          ← DreamAgent 的核心逻辑
└── F10: 洞察验证回路         ← DreamAgent 的验证机制

第五阶段：增强功能
├── F12: MetaCognitiveMonitor 增强
└── F13: API 扩展

第六阶段：集成
└── F14: R1D3 Skill 同步
```

---

## F1: 三进程架构

### 1.1 架构原则

```
三个独立进程并发运行，共享同一张 KG（knowledge/state.json）：

┌─────────────────────────────────────────────┐
│           KG (shared file)                    │
│     knowledge/state.json + dream_insights/     │
└─────────────────────────────────────────────┘
         ↑                   ↑                  ↑
   节点级锁保护         节点级锁保护         节点级锁保护
         ↑                   ↑                  ↑
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ SpiderAgent  │   │  DreamAgent  │   │ SleepPruner │
│  (探索进程)  │   │  (做梦进程)   │   │  (修剪进程)   │
│  独立进程 PID │   │  独立进程 PID │   │  独立进程 PID │
└──────────────┘   └──────────────┘   └──────────────┘
```

**关键约束**：
- SpiderAgent 和 DreamAgent 是**完全独立的进程**，不合并
- 每个进程有自己的 Python 解释器实例
- 进程间通过队列和 KG 文件通信，不共享内存

### 1.2 LLM 使用区分

| 进程 | LLM 用途 | 说明 |
|------|---------|------|
| SpiderAgent → Explorer | 理解 + 总结外部信息 | 分析搜索结果、生成摘要 |
| DreamAgent → LLMClient | 创造全新内容 | 从 A+B 生成新洞察 |
| SleepPruner | 不使用 LLM | 纯规则计算 |

### 1.3 主进程入口

```python
# curious_agent.py 的 daemon_mode 重构
def daemon_mode():
    from core.spider_agent import SpiderAgent
    from core.dream_agent import DreamAgent
    from core.sleep_pruner import SleepPruner
    from multiprocessing import Queue

    high_priority_queue = Queue()   # SpiderAgent → DreamAgent
    low_priority_queue = Queue()    # DreamAgent 内部轮询用

    spider = SpiderAgent(high_priority_queue)
    dreamer = DreamAgent(high_priority_queue, low_priority_queue)
    pruner = SleepPruner(interval_minutes=60)

    spider.start()   # 进程1
    dreamer.start()  # 进程2
    pruner.start()    # 进程3

    spider.join()
    dreamer.join()
    pruner.join()
```

---

## F2: KG Schema 扩展

### 2.1 topics 节点新增字段

```python
# topics[topic] 新增字段
{
    "known": bool,
    "depth": float,
    "summary": str,
    "sources": list[str],
    "children": list[str],
    "parents": list[str],
    "explains": list[dict],

    # === v0.2.6 新增 ===
    "status": str,                 # "complete" | "dormant"
    "last_consolidated": str,      # ISO 时间戳
    "dreamed_at": str,             # ISO 时间戳
    "confidence_low": float,       # [F12] 置信度下限，默认 0.3
    "confidence_high": float,      # [F12] 置信度上限，默认 0.7
    "evidence_count": int,        # [F12] 支持证据数
    "contradiction_count": int,    # [F12] 矛盾证据数
}
```

### 2.2 dream_insights 独立存储

```python
# knowledge/dream_insights/{node_id}.json
{
    "node_id": str,
    "content": str,
    "insight_type": str,          # "hypothesis" | "analogy" | "prediction" | "question"
    "source_topics": list[str],
    "surprise": float,
    "novelty": float,
    "trigger_topic": str | None,
    "weight": float,               # 默认 0.5
    "verified": bool,
    "quality": float,
    "created_at": str,
}
```

### 2.3 dream_topic_inbox（SharedInbox）

```python
# knowledge/dream_topic_inbox.json
{
    "inbox": [
        {
            "topic": str,
            "timestamp": str,
            "source_insight": str
        }
    ]
}
```

### 2.4 exploration_log 扩展

```python
# state["exploration_log"][] 新增字段
{
    "topic": str,
    "action": str,
    "findings": str,
    "notified_user": bool,
    "timestamp": str,
    # === v0.2.6 新增 ===
    "predicted_confidence": float | None,  # [F12]
    "actual_outcome": bool | None,         # [F12]
    "is_hypothesis": bool,                # [F12]
}
```

### 2.5 KG 新增 API

```python
# === Dream Insights ===

def add_dream_insight(content: str, insight_type: str, source_topics: list[str],
                         surprise: float, novelty: float, trigger_topic: str | None) -> str:
    """写入 knowledge/dream_insights/{node_id}.json"""
    node_id = f"insight_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
    entry = {...}  # 见 2.2
    path = os.path.join(os.path.dirname(STATE_FILE), "dream_insights", f"{node_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    return node_id

def get_dream_insights(topic: str = None) -> list[dict]:
    """读取所有或指定 topic 相关的 dream_insights"""

def get_all_dream_insights() -> list[dict]:
    """返回所有 dream_insight 节点"""

def remove_dream_insight(node_id: str):
    """删除 dream_insight"""

def is_insight_stale(node_id: str) -> bool:
    """检查洞察是否已过期（从未被验证且超过 7 天）"""

def update_insight_weight(node_id: str, delta: float):
    """更新洞察权重"""

def update_insight_quality(node_id: str, delta: float):
    """更新洞察质量"""

# === Connection Weight ===

def strengthen_connection(topic_a: str, topic_b: str, delta: float = 0.1):
    """强化两节点连接，weight += delta，上限 1.0"""

def update_connection_weight(topic_a: str, topic_b: str, delta: float):
    """更新连接权重，weight < 0.2 时标记 stale"""

# === Node Status ===

def mark_dormant(topic: str):
    """标记为 dormant"""

def reactivate(topic: str):
    """从 dormant 恢复"""

def mark_dreamed(topic: str):
    """标记节点已做过梦处理"""

def set_consolidated(topic: str):
    """标记节点已巩固"""

def get_dormant_nodes() -> list[str]:
    """返回所有 dormant 节点"""

# === Node Queries ===

def get_all_nodes(active_only: bool = False) -> list[tuple[str, dict]]:
    """返回 KG 中所有节点"""

def get_directly_connected(topic: str) -> set[str]:
    """返回与 topic 直接相连的所有节点"""

def get_shortest_path_length(topic_a: str, topic_b: str) -> int | float:
    """返回两节点最短路径长度，不通返回 inf"""

def get_node_domain(topic: str) -> str:
    """返回 topic 所属的探索分支（domain）"""

def has_recent_dreams(topic: str, within_days: int) -> bool:
    """检查 topic 是否在 N 天内做过梦"""

def get_recently_dreamed(within_days: int) -> set[str]:
    """返回最近 N 天内被 DreamAgent 处理过的节点"""

def get_root_pool_names() -> set[str]:
    """返回 root_technology_pool 中所有候选"""

def get_related_nodes(topic: str) -> list[str]:
    """返回与 topic 相关的所有节点（parents + children）"""

# === SharedInbox [F11] ===

def add_to_dream_inbox(topic: str, source_insight: str):
    """DreamAgent 调用，把 trigger_topic 写入 shared inbox"""
    inbox_path = os.path.join(os.path.dirname(STATE_FILE), "dream_topic_inbox.json")
    inbox = {"inbox": []}
    if os.path.exists(inbox_path):
        with open(inbox_path) as f:
            inbox = json.load(f)
    inbox["inbox"].append({
        "topic": topic,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_insight": source_insight
    })
    with open(inbox_path, "w") as f:
        json.dump(inbox, f, ensure_ascii=False, indent=2)

def fetch_and_clear_dream_inbox() -> list[dict]:
    """SpiderAgent 调用，读取并清空 inbox，返回 inbox 列表"""
    inbox_path = os.path.join(os.path.dirname(STATE_FILE), "dream_topic_inbox.json")
    if not os.path.exists(inbox_path):
        return []
    with open(inbox_path) as f:
        inbox = json.load(f)
    with open(inbox_path, "w") as f:
        json.dump({"inbox": []}, f)
    return inbox.get("inbox", [])
```

---

## F3: 节点级锁

### 3.1 NodeLockRegistry

```python
import threading
from weakref import WeakValueDictionary

class NodeLockRegistry:
    """
    节点级锁注册表
    - 同一节点用同一把锁
    - 节点销毁时锁自动释放（WeakValueDictionary）
    - 死锁预防：所有调用方必须按节点名字排序后再获取锁
    """
    _locks = WeakValueDictionary()

    @classmethod
    def get_lock(cls, node_name: str) -> threading.Lock:
        if node_name not in cls._locks:
            cls._locks[node_name] = threading.Lock()
        return cls._locks[node_name]

    @classmethod
    def get_lock_pair(cls, name_a: str, name_b: str) -> tuple:
        """返回排序后的锁对（防死锁）"""
        lock_a = cls.get_lock(name_a)
        lock_b = cls.get_lock(name_b)
        return sorted([lock_a, lock_b], key=lambda l: id(l))
```

### 3.2 使用规范

```python
# ✅ 正确：按名字排序后再获取
def kg_write_with_lock(from_topic: str, to_topic: str, result: dict):
    locks = NodeLockRegistry.get_lock_pair(from_topic, to_topic)
    with locks[0], locks[1]:
        add_explains(from_topic, to_topic, result)

# ❌ 错误：可能导致死锁
with lock_a:
    with lock_b:  # 另一个线程以相反顺序获取就会死锁
        ...
```

---

## F4: ExplorationHistory（线程安全）

### 4.1 职责

记录每次探索事件，供 consolidation 和价值验证回路使用。

> ⚠️ P0 修复：ExplorationHistory 所有方法必须加锁，因为 SpiderAgent 写的同时 DreamAgent 可能在读。

### 4.2 数据存储

存储在 `state["exploration_history"]` 中（与 `exploration_log` 分开）：

```python
# state["exploration_history"] = {
#     "co_occurrence": {
#         "topic_a|topic_b": {"count": int, "last_time": str, "timestamps": [str]}
#     },
#     "insight_generation": {
#         "insight_node_id": {
#             "source_pair": [topic_a, topic_b],
#             "timestamp": str,
#             "triggered": bool
#         }
#     },
#     "predictions": {
#         "topic": {
#             "predicted_confidence": float,
#             "is_hypothesis": bool,
#             "timestamp": str,
#             "actual_outcome": bool | None
#         }
#     }
# }
```

### 4.3 API

```python
class ExplorationHistory:
    _lock = threading.Lock()

    def record_exploration(self, topic: str, related_nodes: list[str], timestamp: datetime):
        with self._lock:
            # 更新 co_occurrence 计数
            ...

    def record_insight_generation(self, insight_node_id: str, source_pair: tuple, timestamp: datetime):
        with self._lock:
            ...

    def co_occurred(self, topic_a: str, topic_b: str, within_hours: int) -> bool:
        with self._lock:
            ...

    def was_insight_triggered(self, insight_node_id: str, within_days: int) -> bool:
        with self._lock:
            ...

    def record_prediction(self, topic: str, predicted_confidence: float, is_hypothesis: bool):
        """[F12] 记录一次预测"""
        with self._lock:
            ...

    def record_outcome(self, topic: str, actual_correct: bool):
        """[F12] 记录预测结果"""
        with self._lock:
            ...

    def get_recent_explorations(self, within_hours: int) -> list[dict]:
        with self._lock:
            ...

    def get_all_predictions(self) -> list[dict]:
        """[F12] 返回所有预测记录"""
        with self._lock:
            ...

    def get_prediction(self, topic: str) -> dict | None:
        """[F12] 返回特定 topic 的预测记录"""
        with self._lock:
            ...
```

---

## F5: SpiderAgent（独立探索进程）

### 5.1 职责

- 持续从 curiosity_queue 选择 topic 执行探索
- 探索结果写入 KG
- 探索完成后，通知 DreamAgent（通过高优先级队列）
- 定期消费 DreamInbox（将 trigger_topic 合并到 curiosity_queue）

### 5.2 组成模块

```
SpiderAgent（独立进程）
    │
    ├── CuriosityEngine ← 纯规则（不需要 LLM）
    │       └── select_next() → 纯排序/过滤
    │
    ├── Explorer ← 包含 LLM（理解 + 总结外部信息）
    │       ├── search() → Bocha/Serper/ArXiv
    │       ├── analyze() → LLM 分析
    │       └── synthesize() → LLM 总结
    │
    ├── ExplorationHistory ← 共享数据（线程安全）
    │
    └── KG ← 节点级锁保护
```

### 5.3 运行逻辑

```python
class SpiderAgent:
    def __init__(self, to_dreamer_queue):
        self.high_priority_queue = to_dreamer_queue
        self.engine = CuriosityEngine()
        self.explorer = Explorer()
        self.history = ExplorationHistory()

    def run(self):
        while True:
            # [F11] 每次选择前先消费 DreamInbox
            self.sync_dream_inbox()

            # 选择下一个 topic
            topic = self.engine.select_next()
            if topic is None:
                topic = self.engine.generate_new()

            # 执行探索
            result = self.explorer.explore(topic)

            # 写入 KG（节点级锁）
            self.kg_add_with_lock(topic, result)

            # 通知 DreamAgent（高优先级队列）
            self.high_priority_queue.put(("high", topic))

            # consolidation：强化共现连接
            self.strengthen_co_occurring(topic)

            # [F12] 记录探索结果用于校准
            self.history.record_outcome(topic, actual_correct=True)

            yield_to_other_process()

    def sync_dream_inbox(self):
        """[F11] 消费 DreamInbox，将 trigger_topic 加入 curiosity_queue"""
        inbox_items = kg.fetch_and_clear_dream_inbox()
        for item in inbox_items:
            topic = item["topic"]
            if not kg.is_topic_known(topic):
                kg.add_curiosity(
                    topic=topic,
                    reason=f"Dream insight trigger: {item['source_insight']}",
                    relevance=7.0,
                    depth=6.0
                )

    def strengthen_co_occurring(self, topic: str):
        """基于 Hebbian 原则强化共现连接"""
        related = kg.get_related_nodes(topic)
        for node in related:
            if self.history.co_occurred(topic, node, within_hours=24):
                kg.strengthen_connection(topic, node, delta=0.1)
        kg.set_consolidated(topic)
```

### 5.4 与 DreamAgent 的边界

| | SpiderAgent | DreamAgent |
|--|--|--|
| 进程 | 独立进程 | 独立进程 |
| LLM 用途 | 理解和总结外部信息 | 创造全新内容 |
| 写入 KG | children, quality, sources | dream_insights, parents |
| 管理 | curiosity_queue | 无（只写 KG + 队列） |

---

## F6: SleepPruner（定时修剪进程）

### 6.1 职责

- 每 60 分钟扫描一次 KG
- 识别弱连接节点，降级为 dormant

### 6.2 降级标准

```
节点同时满足以下条件 → 降级为 dormant：
1. parents = [] 且 children = []（结构上真正孤立）
2. 所有 dream_insights 连接均为 stale=True（weight < 0.2）
3. quality < 7.0
4. 非 root_technology_pool 候选
5. 非最近 7 天内产生过 dream_insight 的节点
```

### 6.3 运行逻辑

```python
class SleepPruner:
    def __init__(self, interval_minutes=60):
        self.interval = interval_minutes

    def run(self):
        while True:
            count = self.scan_and_prune()
            print(f"[SleepPruner] {count} nodes → dormant")
            sleep(self.interval * 60)

    def scan_and_prune(self) -> int:
        all_nodes = kg.get_all_nodes(active_only=True)
        pool_names = kg.get_root_pool_names()
        count = 0
        for node_name, node in all_nodes:
            if node_name in pool_names:
                continue
            if not self._is_structurally_isolated(node_name):
                continue
            if not self._all_insights_stale(node_name):
                continue
            if node.get("quality", 0) >= 7.0:
                continue
            if kg.has_recent_dreams(node_name, within_days=7):
                continue
            kg.mark_dormant(node_name)
            count += 1
        return count

    def _is_structurally_isolated(self, node_name: str) -> bool:
        parents = kg.get_parents(node_name)
        children = kg.get_children(node_name)
        return len(parents) == 0 and len(children) == 0

    def _all_insights_stale(self, node_name: str) -> bool:
        insights = kg.get_dream_insights(node_name)
        if not insights:
            return True
        return all(i.get("stale", False) or kg.is_insight_stale(i["node_id"])
                   for i in insights)
```

---

## F7: 双队列 + 轮询指针

### 7.1 设计原因

DreamAgent 需要处理两类输入：
1. **高优先级队列**：SpiderAgent 通知的新节点（立即处理）
2. **低优先级队列**：KG 中老节点轮流处理（确保公平）

### 7.2 轮询指针（不是被动填充）

低优先级不用"队列空才填充"的被动模式，而是用**轮询指针**主动遍历：

```python
class DreamAgent:
    def __init__(self, high_priority_queue, low_priority_queue):
        self.high_queue = high_priority_queue
        self.low_queue = low_priority_queue
        self.dream_pointer = 0  # 轮询指针

    def get_next_low_priority(self):
        """主动轮询，不阻塞"""
        all_nodes = kg.get_all_nodes(active_only=True)
        if not all_nodes:
            return None
        n = len(all_nodes)
        for i in range(n):
            idx = (self.dream_pointer + i) % n
            node_name = all_nodes[idx]
            if not kg.has_recent_dreams(node_name, within_days=7):
                self.dream_pointer = (idx + 1) % n
                return node_name
        self.dream_pointer = 0
        return None  # 所有节点近期都处理过了

    def run(self):
        while True:
            if not self.high_queue.empty():
                _, topic = self.high_queue.get()
            else:
                topic = self.get_next_low_priority()
                if topic is None:
                    sleep(1)  # 等待新节点
                    continue
            self.process_creative_dreaming(topic)
```

---

## F8: DreamAgent（独立做梦进程）

### 8.1 职责

- 持续监听高优先级队列和轮询指针
- 对每个节点执行创意做梦（生成新洞察）
- 生成的新洞察通过 SharedInbox 传递给 SpiderAgent

### 8.2 组成模块

```
DreamAgent（独立进程）
    │
    ├── LLMClient ← 直接使用（创意生成，不是 Explorer）
    │       └── llm_creative_dream(topic_a, topic_b) → 新洞察
    │
    ├── ExplorationHistory ← 共享数据（线程安全）
    │
    └── KG ← 节点级锁保护
```

### 8.3 运行逻辑

```python
class DreamAgent:
    def __init__(self, high_priority_queue, low_priority_queue):
        self.high_queue = high_priority_queue
        self.llm = LLMClient()  # 创意生成专用
        self.history = ExplorationHistory()

    def run(self):
        while True:
            if not self.high_queue.empty():
                _, topic = self.high_queue.get()
            else:
                topic = self.get_next_low_priority()
                if topic is None:
                    sleep(1)
                    continue

            distant_pairs = self.find_distant_pairs(topic, max_pairs=5)
            for distant_node, distance in distant_pairs:
                self.process_creative_dreaming(topic, distant_node)

            kg.mark_dreamed(topic)
            self.verify_existing_insights(topic)
```

---

## F9: 创意做梦引擎（生成式）

### 9.1 核心转变

DreamAgent 从"关联判断器"变为"洞察生成器"：

| | 关联判断器 | 洞察生成器 |
|--|--|--|
| 输入 | topic_a, topic_b | topic_a, topic_b |
| 输出 | has_association=True/False | 新洞察内容 + trigger_topic |
| KG 变化 | 边更多，节点不变 | 节点增加，真正生长 |
| 演进必要 | 低 | 高 |

### 9.2 process_creative_dreaming

```python
def process_creative_dreaming(self, topic_a: str, topic_b: str):
    """
    创意做梦：对两个远距离节点，生成新洞察
    """
    result = self.llm.creative_dream(topic_a, topic_b)

    if result["has_insight"] and result["surprise"] >= 0.5:
        # 写入 KG：新增洞察节点
        insight_node = kg.add_dream_insight(
            content=result["insight"],
            insight_type=result["insight_type"],
            source_topics=[topic_a, topic_b],
            surprise=result["surprise"],
            novelty=result["novelty"],
            trigger_topic=result["trigger_topic"]
        )

        # [F11] 通过 SharedInbox 通知 SpiderAgent
        if result["trigger_topic"]:
            kg.add_to_dream_inbox(
                topic=result["trigger_topic"],
                source_insight=insight_node
            )

        # 记录探索历史（用于价值验证）
        self.history.record_insight_generation(
            insight_node_id=insight_node,
            source_pair=(topic_a, topic_b),
            timestamp=datetime.now(timezone.utc)
        )

        # [F12] 记录预测（洞察 = 假设）
        self.history.record_prediction(
            topic=insight_node,
            predicted_confidence=result["surprise"],
            is_hypothesis=True
        )
```

### 9.3 llm.creative_dream prompt

```
你是创意做梦引擎。不是判断两个领域有没有关联，而是从它们的组合中生成全新的洞察。

Topic A: {topic_a}
Topic B: {topic_b}

要求：
1. 洞察必须是从 A+B 组合中**新生成的**，不是 A 也不是 B
2. 生成的内容必须有认知价值（新的假设、类比、预测、问题）
3. trigger_topic：这个洞察能指向哪个新的探索方向？

生成类型（选最合适的）：
- hypothesis: "如果 A，那么可能 B"（新假设）
- analogy: "A 就像 B 中的 X"（新类比）
- prediction: "基于 A 和 B，X 可能发生"（新预测）
- question: "A 和 B 暗示了一个新问题：X"（新问题）

输出格式（JSON）：
{
  "has_insight": true/false,
  "insight": "具体的新洞察内容",
  "insight_type": "hypothesis/analogy/prediction/question",
  "surprise": 0.0-1.0,
  "novelty": 0.0-1.0,
  "trigger_topic": "string 或 null"
}
```

### 9.4 find_distant_pairs（含神经噪声）

```python
def find_distant_pairs(self, topic: str, max_pairs: int = 5) -> list:
    """
    选取远距离无连接的节点

    策略（三层随机）：
    1. 70%：按距离筛选（distance > 3 且 quality >= 4）
    2. 20%：跨 domain 优先
    3. 10%：神经噪声——完全随机，模拟生物大脑的随机激活
    """
    import random
    all_nodes = kg.get_all_nodes(active_only=True)
    connected = kg.get_directly_connected(topic)
    candidates = [n for n in all_nodes if n not in connected and n != topic]

    distant = [n for n in candidates if kg.get_shortest_path_length(topic, n) > 3]
    meaningful = [n for n in distant if n.get("quality", 0) >= 4]

    results = []
    for _ in range(max_pairs):
        rand = random.random()
        if rand < 0.1:
            # 10%：神经噪声
            if candidates:
                results.append((random.choice(candidates), -1))
        elif rand < 0.3:
            # 20%：跨 domain
            topic_domain = kg.get_node_domain(topic)
            cross = [n for n in meaningful if kg.get_node_domain(n) != topic_domain]
            if cross:
                results.append((random.choice(cross), kg.get_shortest_path_length(topic, cross[0])))
        else:
            # 70%：按距离
            if meaningful:
                chosen = random.choice(meaningful)
                results.append((chosen, kg.get_shortest_path_length(topic, chosen)))
    return results
```

---

## F10: 洞察验证回路

### 10.1 逻辑

```python
def verify_existing_insights(self, topic: str):
    """
    检查 topic 相关的已有洞察是否被后续探索验证过

    规则：
    - 7 天内被触发 → verified=True，quality += 1
    - 7 天内未被触发 → weight -= 0.05
    - weight < 0.2 → stale=True
    """
    insights = kg.get_dream_insights(topic)
    for insight in insights:
        if insight.get("verified"):
            continue
        was_triggered = self.history.was_insight_triggered(
            insight["node_id"], within_days=7
        )
        if was_triggered:
            kg.update_insight_quality(insight["node_id"], delta=1.0)
            insight["verified"] = True
        else:
            kg.update_insight_weight(insight["node_id"], delta=-0.05)
            if insight.get("weight", 0.5) < 0.2:
                insight["stale"] = True
```

---

## F11: SharedInbox（Dream→Spider 通信）

### 11.1 通信方向

```
DreamAgent → KG (dream_topic_inbox.json) → SpiderAgent

注意：这是单向通信
- DreamAgent 写 inbox
- SpiderAgent 读并清空 inbox
- 没有反向通道（SpiderAgent 通过高优先级队列通知 DreamAgent）
```

### 11.2 为什么不直接写 curiosity_queue？

因为 curiosity_queue 是 SpiderAgent 的内部数据结构，DreamAgent 作为独立进程不应该直接操作 SpiderAgent 的内部状态。SharedInbox 是明确的进程间协议接口。

---

## F12: MetaCognitiveMonitor 增强

### 12.1 设计决策

**增强现有 `core/meta_cognitive_monitor.py`，不新建独立模块**。

理由：
- 现有 MetaCognitiveMonitor 已有 assess_quality / compute_marginal_return / record_exploration 等方法
- 新建独立模块会导致功能分散、代码重复
- KG 已有 topic 字段，只需扩展字段

### 12.2 新增方法

```python
# core/meta_cognitive_monitor.py 新增

class MetaCognitiveMonitor:
    # === 节点置信区间 [F12-1] ===
    def get_confidence_interval(self, topic: str) -> tuple[float, float]:
        """返回 (confidence_low, confidence_high)"""

    def update_node_confidence(self, topic: str, delta_evidence: int,
                                delta_contradiction: int):
        """更新节点的置信度"""

    # === 知识前沿检测 [F12-2] ===
    def detect_frontier(self) -> list[dict]:
        """
        知识前沿 = 已探索节点指向未探索候选的边
        前沿类型：explicit | cross_domain | contradiction
        """

    def recommend_exploration_from_frontier(self) -> list[str]:
        """从前沿推荐优先探索方向（矛盾 > 跨域 > 显式）"""

    # === 校准评估 [F12-3] ===
    def record_prediction(self, topic: str, predicted_confidence: float, is_hypothesis: bool):
        """记录预测（DreamAgent 生成洞察时调用）"""

    def record_outcome(self, topic: str, actual_correct: bool):
        """记录预测结果（SpiderAgent 验证后调用）"""

    def get_calibration_error(self) -> float:
        """返回 Brier score（越低越好，0=完美校准）"""

    def get_topic_calibration(self, topic: str) -> dict:
        """返回特定 topic 的校准详情"""
```

### 12.3 MetaCognitiveController 扩展

```python
# core/meta_cognitive_controller.py 新增

class MetaCognitiveController:
    def should_explore_frontier(self) -> tuple[bool, list[str]]:
        """推荐基于知识前沿的探索方向"""
        recommendations = self.monitor.recommend_exploration_from_frontier()
        return (len(recommendations) > 0, recommendations)
```

---

## F13: API 扩展

### 13.1 新增路由

```python
# curious_api.py

# === Dream Insights ===
@app.route("/api/kg/dream_insights")
def api_kg_dream_insights():
    """返回所有 dream_insight"""
    return jsonify({"insights": kg.get_all_dream_insights()})

@app.route("/api/kg/dream_insights/<topic>")
def api_kg_dream_insights_topic(topic: str):
    """返回与 topic 相关的所有 dream_insight"""
    return jsonify({"insights": kg.get_dream_insights(topic)})

@app.route("/api/kg/dream_insights/remove/<node_id>", methods=["POST"])
def api_kg_remove_insight(node_id: str):
    """删除 dream_insight（SleepPruner 使用）"""
    kg.remove_dream_insight(node_id)
    return jsonify({"status": "ok"})

# === [F6] Dormant ===
@app.route("/api/kg/dormant")
def api_kg_dormant():
    """返回所有 dormant 节点"""
    return jsonify({"dormant_nodes": kg.get_dormant_nodes()})

@app.route("/api/kg/reactivate", methods=["POST"])
def api_kg_reactivate():
    """恢复 dormant 节点"""
    data = request.get_json()
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic is required"}), 400
    kg.reactivate(topic)
    return jsonify({"status": "ok", "topic": topic})

# === [F8] Dream Agent ===
@app.route("/api/dreamer/force", methods=["POST"])
def api_dreamer_force():
    """强制 DreamAgent 对指定 topic 执行一次创意做梦"""
    data = request.get_json()
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic is required"}), 400
    result = force_dream_topic(topic)
    return jsonify({"status": "ok", "insight_created": result["insight_created"]})

# === [F12] MetaCognitive ===
@app.route("/api/kg/confidence/<path:topic>", methods=["GET"])
def api_kg_confidence(topic: str):
    """获取节点置信区间"""
    low, high = meta_monitor.get_confidence_interval(topic)
    return jsonify({
        "topic": topic,
        "confidence_low": low,
        "confidence_high": high
    })

@app.route("/api/kg/frontier", methods=["GET"])
def api_kg_frontier():
    """获取知识前沿"""
    frontiers = meta_monitor.detect_frontier()
    return jsonify({"frontiers": frontiers})

@app.route("/api/kg/calibration", methods=["GET"])
def api_kg_calibration():
    """获取整体校准误差"""
    error = meta_monitor.get_calibration_error()
    return jsonify({
        "calibration_error": error,
        "verdict": "well_calibrated" if error < 0.1 else "overconfident"
    })
```

---

## F14: R1D3 Skill 同步

### 14.1 当前 curious skill 的同步路径

```
CA: knowledge/state.json / knowledge/dream_insights/
    ↓
skills/curious-agent/scripts/sync_discoveries.py
    ↓
R1D3: memory/curious-discoveries.md
```

### 14.2 v0.2.6 需要新增的同步

| 新增
| 新增同步 | 源路径 | 目的路径 | 触发条件 |
|---------|--------|---------|---------|
| Dream insights | `knowledge/dream_insights/*.json` | `shared_knowledge/ca/dream_insights/` | 新洞察生成时 |
| Confidence 更新 | KG topics{} | `shared_knowledge/ca/confidence/` | Confidence 显著变化时 |
| Frontier | MetaCognitiveMonitor | `shared_knowledge/ca/frontier/` | 每小时一次 |
| Calibration | MetaCognitiveMonitor | `shared_knowledge/ca/calibration/` | 每小时一次 |

### 14.3 新增 skill 文件

```
skills/curious-agent/scripts/
    ├── sync_dream_insights.py     ← 新增：同步 dream insights
    └── sync_metacognitive.py     ← 新增：同步 confidence/frontier/calibration
```

### 14.4 同步逻辑

```python
# sync_dream_insights.py
def sync_new_insights():
    """同步新生成的 dream insights 到 shared_knowledge"""
    insights = kg.get_all_dream_insights()
    # 读取上次同步位置，只同步新增的
    for insight in insights:
        if not insight.get("_synced"):
            write_to_shared(insight)
            insight["_synced"] = True
    kg.save_dream_insights(insights)

# sync_metacognitive.py
def sync_metacognitive():
    """同步 meta cognitive 状态"""
    # frontier
    frontiers = meta_monitor.detect_frontier()
    # calibration
    error = meta_monitor.get_calibration_error()
    # 写入 shared_knowledge/ca/
```

---

## 模块依赖关系

```
curious_agent.py (入口)
    ├── SpiderAgent (进程1)
    │   ├── CuriosityEngine
    │   ├── Explorer
    │   ├── ExplorationHistory (线程安全, F4)
    │   └── KG (节点级锁, F3)
    ├── DreamAgent (进程2)
    │   ├── LLMClient (creative_dream, F9)
    │   ├── ExplorationHistory (线程安全, F4)
    │   ├── KG (节点级锁, F3)
    │   └── SharedInbox (F11)
    └── SleepPruner (进程3)
        └── KG (节点级锁, F3)

MetaCognitiveMonitor（增强现有模块，不是独立进程）
    ├── ExplorationHistory (F4)
    └── KG (F3)
```

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/spider_agent.py` | 新增 | 持续探索进程（F5） |
| `core/dream_agent.py` | 新增 | 持续做梦进程（F8） |
| `core/sleep_pruner.py` | 新增 | 定时修剪进程（F6） |
| `core/knowledge_graph.py` | 修改 | KG Schema 扩展（F2）+ 新增 API |
| `core/meta_cognitive_monitor.py` | 修改 | 新增方法（F12） |
| `core/meta_cognitive_controller.py` | 修改 | 新增决策方法（F12） |
| `core/exploration_history.py` | 新增 | ExplorationHistory 独立文件（F4） |
| `core/node_lock_registry.py` | 新增 | 节点级锁（F3） |
| `curious_agent.py` | 修改 | 启动三个独立进程（F1） |
| `curious_api.py` | 修改 | 新增 API 路由（F13） |
| `skills/curious-agent/scripts/sync_dream_insights.py` | 新增 | R1D3 同步（F14） |
| `skills/curious-agent/scripts/sync_metacognitive.py` | 新增 | R1D3 同步（F14） |

---

## 验收标准

```bash
# === 进程启动 ===
# 1. 三个进程正常启动
curl http://localhost:4848/api/curious/state

# === Dream Insights ===
# 2. 注入话题后，DreamAgent 高优先级处理
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"test dreaming","score":7.0,"depth":6.0}'

# 3. 手动触发 DreamAgent
curl -X POST http://localhost:4848/api/dreamer/force \
  -H "Content-Type: application/json" \
  -d '{"topic":"metacognitive monitoring"}'

# 4. 查看 dream_insights
curl http://localhost:4848/api/kg/dream_insights

# === Dormant & Pruning ===
# 5. 查看 dormant 节点
curl http://localhost:4848/api/kg/dormant

# 6. 恢复 dormant 节点
curl -X POST http://localhost:4848/api/kg/reactivate \
  -H "Content-Type: application/json" \
  -d '{"topic":"某个dormant节点"}'

# === MetaCognitive [F12] ===
# 7. 查看置信区间
curl http://localhost:4848/api/kg/confidence/metacognitive%20monitoring

# 8. 查看知识前沿
curl http://localhost:4848/api/kg/frontier

# 9. 查看校准误差
curl http://localhost:4848/api/kg/calibration
```

---

_Last updated: 2026-03-28 17:03 by R1D3_
_v0.2.6: Three independent processes + Creative DreamAgent + SpiderAgent + SleepPruner + MetaCognitiveMonitor enhanced_
