# SPEC v0.2.6 — 持续做梦 & 记忆巩固

> **核心目标**: 让 CA 从"探索引擎"进化为"持续学习的数字生命体"
> **架构原则**: 三个独立执行流并发运行，共享同一张 KG，线程级协调，无全局锁
> **更新**: 2026-03-28 17:23（补充：F9-Supp LLMClient.creative_dream 实现 + F12 MetaCognitiveMonitor 完整实现 + 验收方法）
> **设计原则**: SpiderAgent 和 DreamAgent 是完全独立的执行流，不合并；两者的 LLM 用途不同

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

## F1: 三执行流架构

### 1.1 架构决策：基于 threading 而非 multiprocessing

> **决策依据**：基于现有代码分析
> - LLMManager 是单例（`get_instance()`），同一进程内自然共享
> - KG 是 JSON 文件，threading 下 GIL 保护文件读写
> - 当前代码无 multiprocessing 基础，改动成本低
> - 未来可升级为 multiprocessing 做更强隔离

**实现选择**：`threading.Thread`（同一进程内的独立执行流）

**为什么不选 multiprocessing**：
- 每个进程有独立 LLMManager 实例，token 配额各自消耗
- JSON 文件共享需要额外文件锁机制
- 当前阶段 threading 已满足并发需求

### 1.2 架构原则

```
同一个 Python 进程内，三个独立执行流共享 KG + LLMManager：

┌─────────────────────────────────────────────┐
│            Python 进程 (curious_agent.py)     │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ SpiderAgent  │  │  DreamAgent  │  │ SleepPruner │  │
│  │  (Thread)   │  │  (Thread)    │  │  (Thread)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         ↑                  ↑                 ↑         │
│         └──────────────────┴─────────────────┘         │
│                    threading.Lock (F3)                  │
│                          ↓                              │
│         ┌─────────────────────────────────┐            │
│         │  KG (knowledge/state.json)      │            │
│         │  LLMManager (singleton)         │            │
│         │  queue.Queue (thread-safe)     │            │
│         └─────────────────────────────────┘            │
└─────────────────────────────────────────────────────┘
```

**关键约束**：
- 三个 Thread 共享同一个 LLMManager 实例（单例）
- 共享同一个 KG JSON 文件（通过 threading.Lock 保护）
- 线程间通过 `queue.Queue` 通信，不跨进程

### 1.3 LLMClient：通用模块，所有 Agent 共享

**核心设计原则**：LLMClient 是通用 LLM 调用模块，**不专属于任何 Agent**。所有 Agent（SpiderAgent、DreamAgent、DexterousAgent 等）统一使用 LLMClient，只是传入的 prompt 和模型配置不同。

```
LLMClient（通用模块）
    │
    └── LLMManager（单例，支持多 Provider + 多 Model）
            │
            ├── Provider: volcengine
            │       └── Model: minimax-m2.7
            │
            ├── Provider: openai
            │       └── Model: gpt-4o
            │
            └── Provider: anthropic
                    └── Model: claude-3-5-sonnet
```

**LLMManager 的职责**（现有代码）：
- 单例模式，整个进程只有一个实例
- 统一管理所有 Provider 和 Model 配置
- 根据 task_type 或显式指定选择 Provider/Model
- 管理 API key、timeout、重试等

**不同 Agent 的 LLM 调用方式**：

```python
# SpiderAgent：用理解能力强的模型（分析+总结外部信息）
llm = LLMClient()
result = llm.chat(prompt, model_name="claude-3-5-sonnet", temperature=0.3)
# 或通过 LLMManager 的能力路由：
result = llm.manager.chat(prompt, task_type="analysis")

# DreamAgent：用高随机性模型（创意生成）
llm = LLMClient()
result = llm.creative_dream(topic_a, topic_b, temperature=0.9, model_name="gpt-4o")

# DexterousAgent（未来）：用代码能力强的模型
llm = LLMClient()
result = llm.chat(code_prompt, model_name="claude-3-5-sonnet", temperature=0.5)
```

**模型配置示例**（`core/config.py` 或 `config.json`）：

```python
LLM_PROVIDERS = [
    {
        "name": "volcengine",
        "models": [
            {"model": "minimax-m2.7", "capabilities": ["general", "fast"]},
            {"model": "minimax-m2.1", "capabilities": ["general"]}
        ]
    },
    {
        "name": "openai",
        "models": [
            {"model": "gpt-4o", "capabilities": ["creative", "reasoning"]}
        ]
    },
    {
        "name": "anthropic",
        "models": [
            {"model": "claude-3-5-sonnet", "capabilities": ["analysis", "code", "creative"]}
        ]
    }
]

# Agent 的模型推荐：
# - SpiderAgent（探索分析）：claude-3-5-sonnet（强分析能力）
# - DreamAgent（创意生成）：gpt-4o（高随机性）或 claude-3-5-sonnet
# - DexterousAgent（代码任务）：claude-3-5-sonnet（强代码能力）
```

**LLMClient.creative_dream 的模型选择**（F9 实现时使用）：

```python
# core/llm_client.py 的 creative_dream 方法
def creative_dream(self, topic_a: str, topic_b: str, ...):
    # 使用创意能力强的模型，temperature=0.9
    return self.manager.chat(
        prompt,
        model_name="gpt-4o",       # 或 "claude-3-5-sonnet"
        temperature=0.9,
        max_tokens=800,
        timeout=60
    )
```

### 1.4 主进程入口

```python
# curious_agent.py 的 daemon_mode 重构
import threading
import queue

def daemon_mode():
    from core.spider_agent import SpiderAgent
    from core.dream_agent import DreamAgent
    from core.sleep_pruner import SleepPruner

    # SpiderAgent → DreamAgent 的通知队列
    high_priority_queue = queue.Queue()

    spider = SpiderAgent(high_priority_queue, name="SpiderAgent")
    dreamer = DreamAgent(high_priority_queue, name="DreamAgent")
    pruner = SleepPruner(interval_minutes=60)

    spider.start()   # Thread 1
    dreamer.start()  # Thread 2
    pruner.start()   # Thread 3

    # 等待所有线程（实际上不会退出）
    spider.join()
    dreamer.join()
    pruner.join()
```

### 1.5 基础类定义

```python
# 所有 Agent 继承自 threading.Thread
import threading
import queue
import time

class BaseAgent(threading.Thread):
    """所有 Agent 的基础类"""
    def __init__(self, name: str):
        super().__init__(name=name, daemon=True)  # daemon=True: 主进程退出时自动终止
        self.running = True

    def stop(self):
        self.running = False

    def yield_to_other(self):
        """给其他线程让出执行权"""
        time.sleep(0)  # 让出 GIL，允许其他线程运行
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

### 3.1 两层锁机制

**问题**：KG 是 JSON 文件，每次操作是"读→修改→写"。如果两个线程同时读、分别写，后写的会覆盖先写的。

**解决方案**：两层锁：
1. **全局写锁**：保护 KG 文件的读-改-写原子性
2. **节点级锁**：保护同节点操作的互斥

### 3.2 NodeLockRegistry（节点级锁）

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
    _global_write_lock = threading.RLock()  # 全局写锁

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

    @classmethod
    def global_write_lock(cls) -> threading.RLock:
        """全局写锁，保护 KG 文件的读-改-写原子性"""
        return cls._global_write_lock
```

### 3.3 KG 操作的锁使用规范

```python
# ✅ 正确：全局写锁 + 节点级锁
def kg_write_with_lock(from_topic: str, to_topic: str, result: dict):
    # 1. 获取全局写锁（保护文件读写）
    with NodeLockRegistry.global_write_lock():
        # 2. 获取节点级锁（保护同节点互斥）
        locks = NodeLockRegistry.get_lock_pair(from_topic, to_topic)
        with locks[0], locks[1]:
            state = _load_state()
            # 修改 state
            ...
            _save_state(state)

# ✅ 只修改单个节点
def kg_update_node(topic: str, updates: dict):
    with NodeLockRegistry.global_write_lock():
        lock = NodeLockRegistry.get_lock(topic)
        with lock:
            state = _load_state()
            state["knowledge"]["topics"].setdefault(topic, {}).update(updates)
            _save_state(state)

# ❌ 错误：先获取节点锁，再获取全局锁（可能导致死锁）
# 因为另一个线程可能先拿了全局锁，再拿节点锁
with node_lock:  # A 线程拿到节点锁
    with global_lock:  # A 等待全局锁
        ...

# ✅ 正确顺序：总是先全局锁，再节点锁
with global_lock:
    with node_lock:
        ...
```

### 3.4 现有 KG 函数的改造策略

> ⚠️ 重要：现有 KG 函数（如 `_load_state`/`_save_state`/`add_knowledge`）在单线程下运行，没有锁。
> 升级为多线程时，需要逐个改造。

**改造策略**：
1. 读取操作：直接读，不需要锁（GIL 保证 Python 对象读取是原子的）
2. 写入操作：必须用全局写锁 + 节点锁（原子性保证）

**不需要锁的读取**：
```python
def kg_read(topic: str) -> dict:
    state = _load_state()  # GIL 保证读取完成
    return state["knowledge"]["topics"].get(topic, {})
```

**需要锁的写入**：
```python
def kg_write(topic: str, data: dict):
    with NodeLockRegistry.global_write_lock():
        lock = NodeLockRegistry.get_lock(topic)
        with lock:
            state = _load_state()
            state["knowledge"]["topics"][topic] = data
            _save_state(state)
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
        """返回最近 N 小时的探索记录"""
        with self._lock:
            from datetime import datetime, timezone, timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).isoformat()
            history = self._get_history()
            return [e for e in history.get("explorations", [])
                    if e.get("timestamp", "") >= cutoff]

    def get_all_predictions(self) -> list[dict]:
        """[F12] 返回所有预测记录"""
        with self._lock:
            history = self._get_history()
            return list(history.get("predictions", {}).values())

    def get_prediction(self, topic: str) -> dict | None:
        """[F12] 返回特定 topic 的预测记录"""
        with self._lock:
            history = self._get_history()
            return history.get("predictions", {}).get(topic)

    # === 内部辅助方法 ===

    def _get_history(self) -> dict:
        """从 state 读取 exploration_history"""
        state = kg.get_state()
        return state.get("exploration_history", {
            "co_occurrence": {},
            "insight_generation": {},
            "predictions": {}
        })

    def _save_history(self, history: dict):
        """保存 exploration_history 到 state"""
        state = kg.get_state()
        state["exploration_history"] = history
        kg._save_state(state)
```

---

## F5: SpiderAgent（独立探索执行流）

### 5.1 职责

- 持续从 curiosity_queue 选择 topic 执行探索
- 探索结果写入 KG
- 探索完成后，通知 DreamAgent（通过高优先级队列）
- 定期消费 DreamInbox（将 trigger_topic 合并到 curiosity_queue）

### 5.2 组成模块

```
SpiderAgent（Thread，与 DreamAgent/SleepPruner 同进程）
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
class SpiderAgent(BaseAgent):
    def __init__(self, to_dreamer_queue):
        super().__init__(name="SpiderAgent")
        self.high_priority_queue = to_dreamer_queue
        self.engine = CuriosityEngine()
        self.explorer = Explorer()
        self.history = ExplorationHistory()

    def run(self):
        """主循环：选择 → 探索 → 写入 KG → 通知 DreamAgent"""
        while self.running:
            # [F11] 每次选择前先消费 DreamInbox
            self.sync_dream_inbox()

            # 选择下一个 topic
            topic = self.engine.select_next()
            if topic is None:
                topic = self.engine.generate_new()

            # 执行探索
            result = self.explorer.explore(topic)

            # 写入 KG（节点级锁）
            self.kg_write_with_lock(topic, result)

            # 通知 DreamAgent（高优先级队列）
            self.high_priority_queue.put(("high", topic))

            # consolidation：强化共现连接
            self.strengthen_co_occurring(topic)

            # [F12] 记录探索结果用于校准
            self.history.record_outcome(topic, actual_correct=True)

            time.sleep(0)  # 让出 GIL，允许 DreamAgent 运行

    def sync_dream_inbox(self):
        """[F11] 消费 DreamInbox，将 trigger_topic 加入 curiosity_queue"""
        inbox_items = kg.fetch_and_clear_dream_inbox()
        for item in inbox_items:
            topic = item["topic"]
            # 使用 kg.is_topic_completed 而非 is_topic_known（后者不存在）
            if not kg.is_topic_completed(topic):
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

    def kg_write_with_lock(self, topic: str, result: dict):
        """写入 KG，带全局写锁 + 节点锁"""
        with NodeLockRegistry.global_write_lock():
            lock = NodeLockRegistry.get_lock(topic)
            with lock:
                kg.add_knowledge(topic, depth=result.get("depth", 5),
                                 summary=result.get("findings", ""),
                                 sources=result.get("sources", []))
```

### 5.4 与 DreamAgent 的边界

| | SpiderAgent | DreamAgent |
|--|--|--|
| 执行模型 | Thread（与另两者同进程） | Thread（与另两者同进程） |
| LLM 用途 | 理解和总结外部信息 | 创造全新内容 |
| 写入 KG | children, quality, sources | dream_insights, parents |
| 管理 | curiosity_queue | 无（只写 KG + 队列） |

---

## F6: SleepPruner（定时修剪执行流）

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
class SleepPruner(BaseAgent):
    def __init__(self, interval_minutes=60):
        super().__init__(name="SleepPruner")
        self.interval = interval_minutes

    def run(self):
        while self.running:
            count = self.scan_and_prune()
            print(f"[SleepPruner] {count} nodes → dormant")
            time.sleep(self.interval * 60)

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
                   for i in insights)
```

---

## F7: 双队列 + 轮询指针

### 7.1 设计原因

DreamAgent 需要处理两类输入：
1. **高优先级队列**：SpiderAgent 通知的新节点（立即处理）
2. **低优先级轮询**：KG 中老节点轮流处理（确保公平）

### 7.2 轮询指针（不是队列被动填充）

低优先级使用**轮询指针**主动遍历，不依赖队列填充：

```python
class DreamAgent(BaseAgent):
    def __init__(self, high_priority_queue):
        super().__init__(name="DreamAgent")
        self.high_queue = high_priority_queue
        self.dream_pointer = 0  # 轮询指针

    def get_next_low_priority(self):
        """主动轮询，不阻塞，返回一个待做梦的节点"""
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
        while self.running:
            try:
                # 高优先级队列：等待通知（阻塞，最多等 60 秒）
                item = self.high_queue.get(timeout=60)
                topic = item[1]  # item = ("high", topic)
            except queue.Empty:
                # 超时：主动轮询一个低优先级节点
                topic = self.get_next_low_priority()
                if topic is None:
                    time.sleep(1)  # 没有可处理节点，等待一下
                    continue

            self.process_creative_dreaming(topic)
            time.sleep(0)  # 让出 GIL
```

### 7.3 为什么不用 low_priority_queue？

低优先级队列是被动模式（队列空才填充），会导致老节点永久没有做梦机会。
轮询指针是主动模式，每个节点定期都有机会被处理。
两者的权衡：指针遍历有 O(n) 开销，但保证了公平性。

---

## F8: DreamAgent（独立做梦进程）

## F8: DreamAgent（独立做梦执行流）

### 8.1 职责

- 持续监听高优先级队列和轮询指针
- 对每个节点执行创意做梦（生成新洞察）
- 生成的新洞察通过 SharedInbox 传递给 SpiderAgent

### 8.2 组成模块

```
DreamAgent（Thread，与 SpiderAgent/SleepPruner 同进程）
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
class DreamAgent(BaseAgent):
    def __init__(self, high_priority_queue):
        super().__init__(name="DreamAgent")
        self.high_queue = high_priority_queue
        self.llm = LLMClient()  # 创意生成专用
        self.history = ExplorationHistory()

    def run(self):
        while self.running:
            try:
                item = self.high_queue.get(timeout=60)
                topic = item[1]  # item = ("high", topic_name)
            except queue.Empty:
                topic = self.get_next_low_priority()
                if topic is None:
                    time.sleep(1)
                    continue

            distant_pairs = self.find_distant_pairs(topic, max_pairs=5)
            for distant_node, distance in distant_pairs:
                self.process_creative_dreaming(topic, distant_node)

            kg.mark_dreamed(topic)
            self.verify_existing_insights(topic)
            time.sleep(0)  # 让出 GIL
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

## F9-Supp: LLMClient.creative_dream() 设计补充

### 设计目的

为 DreamAgent 提供"从两个无关知识领域生成新洞察"的 LLM 调用能力。

### 业务逻辑

```
输入：topic_a, topic_b（两个完全无关的知识节点）
处理：
1. 构造 prompt（包含领域 A 和 B 的信息）
2. 调用 LLM 生成洞察
3. 解析 LLM 返回的 JSON
4. 验证返回格式，过滤不合规的响应
输出：dict {
    has_insight: bool,
    insight: str,
    insight_type: str,
    surprise: float,
    novelty: float,
    trigger_topic: str | None
}
```

### 初步实现

```python
# core/llm_client.py 新增方法

def creative_dream(self, topic_a: str, topic_b: str,
                   temperature: float = 0.9,
                   max_tokens: int = 800,
                   timeout: int = 60) -> dict:
    """
    创意做梦：对两个领域生成新洞察

    Args:
        topic_a: 领域 A
        topic_b: 领域 B
        temperature: 0.9（高随机性，鼓励创意）
        max_tokens: 800（足够生成一段洞察）
        timeout: 60 秒

    Returns:
        {
            "has_insight": bool,
            "insight": str,
            "insight_type": str,
            "surprise": float,
            "novelty": float,
            "trigger_topic": str | None
        }

    错误处理：
        - LLM 返回非 JSON → 返回 has_insight=False，insight=""
        - LLM 超时 → 返回 has_insight=False
        - JSON 解析失败 → 返回 has_insight=False
    """
    prompt = CREATIVE_DREAM_PROMPT.format(topic_a=topic_a, topic_b=topic_b)

    try:
        response = self.manager.chat(
            prompt,
            model_name="default",  # 或选择能力强的模型
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
    except Exception as e:
        print(f"[LLMClient] creative_dream failed: {e}")
        return {"has_insight": False, "insight": "", "insight_type": "",
                "surprise": 0.0, "novelty": 0.0, "trigger_topic": None}

    # 解析 JSON
    try:
        import json, re
        # 尝试提取 JSON 代码块
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            result = json.loads(match.group())
        else:
            result = json.loads(response)

        # 验证必要字段
        if not isinstance(result.get("has_insight"), bool):
            return {"has_insight": False, "insight": "", "insight_type": "",
                    "surprise": 0.0, "novelty": 0.0, "trigger_topic": None}

        return {
            "has_insight": result.get("has_insight", False),
            "insight": result.get("insight", ""),
            "insight_type": result.get("insight_type", "hypothesis"),
            "surprise": float(result.get("surprise", 0.0)),
            "novelty": float(result.get("novelty", 0.0)),
            "trigger_topic": result.get("trigger_topic")
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"[LLMClient] creative_dream parse failed: {e}, response={response[:200]}")
        return {"has_insight": False, "insight": "", "insight_type": "",
                "surprise": 0.0, "novelty": 0.0, "trigger_topic": None}
```

### CREATIVE_DREAM_PROMPT

```python
CREATIVE_DREAM_PROMPT = """你是创意做梦引擎。不是判断两个领域有没有关联，而是从它们的组合中生成全新的洞察。

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
{{
  "has_insight": true/false,
  "insight": "具体的新洞察内容",
  "insight_type": "hypothesis/analogy/prediction/question",
  "surprise": 0.0-1.0,
  "novelty": 0.0-1.0,
  "trigger_topic": "string 或 null"
}}"""
```

### 验收方法

```python
# 测试代码
def test_creative_dream():
    llm = LLMClient()
    result = llm.creative_dream(
        "transformer attention mechanism",
        "neurotransmitter release in brain"
    )
    assert isinstance(result["has_insight"], bool)
    assert isinstance(result["insight"], str)
    assert result["surprise"] in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    assert result["insight_type"] in ["hypothesis", "analogy", "prediction", "question"]
    print(f"has_insight={result['has_insight']}, type={result['insight_type']}, surprise={result['surprise']}")
    print(f"insight={result['insight'][:100]}...")
    return result
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

### 12.2 新增方法（含初步实现）

```python
# core/meta_cognitive_monitor.py 新增方法

class MetaCognitiveMonitor:
    # === 节点置信区间 [F12-1] ===

    def get_confidence_interval(self, topic: str) -> tuple[float, float]:
        """返回 (confidence_low, confidence_high)"""
        state = kg.get_state()
        topic_data = state["knowledge"]["topics"].get(topic, {})
        low = topic_data.get("confidence_low", 0.3)
        high = topic_data.get("confidence_high", 0.7)
        return (low, high)

    def update_node_confidence(self, topic: str, delta_evidence: int = 0,
                                delta_contradiction: int = 0):
        """
        更新节点的置信度

        置信度更新规则：
        - 新证据支持：confidence_low += delta_evidence * 0.1
        - 矛盾证据：confidence_high -= delta_contradiction * 0.2
        """
        state = kg.get_state()
        topic_data = state["knowledge"]["topics"].setdefault(topic, {})

        # 初始化默认值
        if "confidence_low" not in topic_data:
            topic_data["confidence_low"] = 0.3
        if "confidence_high" not in topic_data:
            topic_data["confidence_high"] = 0.7
        if "evidence_count" not in topic_data:
            topic_data["evidence_count"] = 0
        if "contradiction_count" not in topic_data:
            topic_data["contradiction_count"] = 0

        # 更新
        topic_data["confidence_low"] = min(1.0, topic_data["confidence_low"] + delta_evidence * 0.1)
        topic_data["confidence_high"] = max(0.0, topic_data["confidence_high"] - delta_contradiction * 0.2)
        topic_data["evidence_count"] = topic_data.get("evidence_count", 0) + delta_evidence
        topic_data["contradiction_count"] = topic_data.get("contradiction_count", 0) + delta_contradiction

        kg._save_state(state)

    # === 知识前沿检测 [F12-2] ===

    def detect_frontier(self) -> list[dict]:
        """
        知识前沿 = 已探索节点但无 children 的节点

        前沿类型：
        - explicit: known=True 但 children = []（有探索但无扩展）
        - cross_domain: 跨 domain 连接但目标 domain 未探索
        - contradiction: 互相矛盾的节点对
        """
        frontiers = []
        state = kg.get_state()
        for topic, data in state["knowledge"]["topics"].items():
            if not data.get("known"):
                continue

            children = data.get("children", [])
            if not children:
                frontiers.append({
                    "from_node": topic,
                    "frontier_type": "explicit",
                    "uncertainty": "high"  # 有探索但无扩展 = 高不确定性
                })

        return frontiers

    def recommend_exploration_from_frontier(self) -> list[str]:
        """
        从前沿推荐优先探索方向

        策略：按 uncertainty 排序，高不确定性优先
        """
        frontiers = self.detect_frontier()
        sorted_frontiers = sorted(frontiers, key=lambda f: (
            {"high": 0, "medium": 1, "low": 2}.get(f["uncertainty"], 2)
        ))
        return [f["from_node"] for f in sorted_frontiers]

    # === 校准评估 [F12-3] ===

    def record_prediction(self, topic: str, predicted_confidence: float, is_hypothesis: bool):
        """
        记录预测（DreamAgent 生成洞察时调用）

        存储到 ExplorationHistory.predictions
        """
        self.history.record_prediction(topic, predicted_confidence, is_hypothesis)

    def record_outcome(self, topic: str, actual_correct: bool):
        """
        记录预测结果（SpiderAgent 验证后调用）

        用于计算 calibration error
        """
        self.history.record_outcome(topic, actual_correct)

    def get_calibration_error(self) -> float:
        """
        返回 Brier score（越低越好，0=完美校准）

        Brier score = mean((predicted - actual)^2)
        """
        predictions = self.history.get_all_predictions()
        if not predictions:
            return 0.0

        scored = [p for p in predictions if p.get("actual_outcome") is not None]
        if not scored:
            return 0.0

        brier = sum(
            (p["predicted_confidence"] - (1.0 if p["actual_outcome"] else 0.0)) ** 2
            for p in scored
        ) / len(scored)
        return round(brier, 4)

    def get_topic_calibration(self, topic: str) -> dict:
        """返回特定 topic 的校准详情"""
        pred = self.history.get_prediction(topic)
        if not pred:
            return {"topic": topic, "verdict": "no_prediction_recorded"}

        error = abs(pred["predicted_confidence"] - (1.0 if pred["actual_outcome"] else 0.0))
        verdict = "well_calibrated" if error < 0.2 else ("overconfident" if pred["predicted_confidence"] > 0.7 else "underconfident")

        return {
            "topic": topic,
            "predicted": pred["predicted_confidence"],
            "actual_outcome": pred["actual_outcome"],
            "error": round(error, 3),
            "verdict": verdict
        }
```

### 12.3 MetaCognitiveController 扩展

```python
# core/meta_cognitive_controller.py 新增

class MetaCognitiveController:
    def should_explore_frontier(self) -> tuple[bool, list[str]]:
        """
        基于知识前沿推荐探索方向

        Returns:
            (should_explore, list_of_frontier_topics)
        """
        recommendations = self.monitor.recommend_exploration_from_frontier()
        if not recommendations:
            return (False, [])
        return (True, recommendations[:3])  # 最多返回 3 个
```

### 12.4 验收方法

```python
# 测试代码
def test_metacognitive_monitor():
    monitor = MetaCognitiveMonitor()

    # 测试置信区间
    low, high = monitor.get_confidence_interval("transformer attention")
    assert 0 <= low <= high <= 1.0
    print(f"confidence: [{low:.2f}, {high:.2f}]")

    # 测试前沿检测
    frontiers = monitor.detect_frontier()
    print(f"frontiers: {len(frontiers)} nodes")
    for f in frontiers[:3]:
        print(f"  - {f['from_node']} ({f['frontier_type']})")

    # 测试校准误差
    error = monitor.get_calibration_error()
    print(f"calibration error: {error:.4f}")

    # 测试前沿推荐
    recs = monitor.recommend_exploration_from_frontier()
    print(f"recommendations: {recs[:3]}")
```

### 12.5 与 CuriosityEngine 的集成

```python
# CuriosityEngine.select_next() 中增加 frontier 感知

def select_next(self):
    # 1. 从前沿中采样（10% 概率）
    if random.random() < 0.1:
        recs = self.meta_monitor.recommend_exploration_from_frontier()
        if recs:
            return random.choice(recs)

    # 2. 原有逻辑...
    candidates = kg.get_top_curiosities(k=10)
    ...
```

### 12.6 与 SpiderAgent 的集成

```python
# SpiderAgent 探索完成后，更新置信度

def strengthen_co_occurring(self, topic: str):
    # ...原有逻辑...

    # 更新置信度（新证据支持）
    self.meta_monitor.update_node_confidence(topic, delta_evidence=+1)
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
curious_agent.py (入口，同一 Python 进程)
    │
    ├── BaseAgent (基础类，threading.Thread)
    │
    ├── SpiderAgent (Thread)
    │   ├── CuriosityEngine
    │   ├── Explorer
    │   ├── ExplorationHistory (线程安全, F4)
    │   └── KG (节点级锁, F3)
    │
    ├── DreamAgent (Thread)
    │   ├── LLMClient (creative_dream, F9)
    │   ├── ExplorationHistory (线程安全, F4)
    │   ├── KG (节点级锁, F3)
    │   └── SharedInbox (F11)
    │
    └── SleepPruner (Thread)
        └── KG (节点级锁, F3)

共享资源（同一进程内）：
    ├── LLMManager (singleton)
    ├── KG (knowledge/state.json)
    ├── NodeLockRegistry (threading.Lock)
    └── high_priority_queue (queue.Queue)

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

_Last updated: 2026-03-28 17:23 by R1D3_
_v0.2.6: Threading-based (not multiprocessing) - F1 threaded model, F3 two-layer locking, F7 no low_queue param, F8 no engine_
