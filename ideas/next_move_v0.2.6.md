# SPEC v0.2.6 — 持续做梦 & 记忆巩固

> **核心目标**: 让 CA 从"探索引擎"进化为"持续学习的数字生命体"
> **架构原则**: 探索和做梦同时运行，共享同一张 KG，无全局锁，节点级协调
> **更新**: 2026-03-28 16:36（并发架构 + 节点级锁 + 做梦公平性 + 权重修剪 + P0/P1 修复 + Claude Code 对比）

---

## 变更概览

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/spider_agent.py` | 新增 | 持续探索进程（重构自现有探索逻辑） |
| `core/dream_agent.py` | 新增 | 持续做梦重组进程（含 consolidation + reorganization） |
| `core/sleep_pruner.py` | 新增 | 突触修剪器（权重感知） |
| `core/knowledge_graph.py` | 修改 | 新增 dormant 状态、dream_insights、last_consolidated、connection_weight、节点级锁 |
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
- DreamAgent 写入: `dream_insights`（新洞察节点）、`parents`（探索关系）
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

- 新建的 dream_insight：初始 weight = 0.5
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

> ⚠️ 注意：`ExplorationHistory` 内部已加锁，此处调用不需要额外加锁。

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
- 生成新洞察 → 写入 dream_insights（新知识节点）

### 3.2 双队列设计

```python
class DreamAgent:
    def __init__(self, high_priority_queue, low_priority_queue):
        self.high_queue = high_priority_queue  # SpiderAgent 通知的新节点
        self.low_queue = low_priority_queue    # 所有节点轮流

    def run(self):
        while True:
            # 高优先级队列有内容 → 立即处理
            # 高优先级队列空 → 用轮询指针从 KG 主动取
            if not self.high_queue.empty():
                priority, topic = self.high_queue.get()
            else:
                topic = self.get_next_from_low_priority()  # ⚠️ P1：主动轮询，不阻塞

            # 获取与 topic 配对的远距离节点
            distant_pairs = self.find_distant_pairs(topic)

            # 对每对节点执行创意做梦
            for distant_node, distance in distant_pairs:
                self.process_creative_dreaming(topic, distant_node)

            yield_to_other_process()
```

### 3.3 低优先级队列的填充策略

```python
class DreamAgent:
    def __init__(self, high_priority_queue, low_priority_queue):
        ...
        self.dream_pointer = 0  # ⚠️ P1 修复：轮询指针，确保公平性

    def get_next_from_low_priority(self):
        """
        ⚠️ P1 修复：从被动触发 → 主动轮询

        人类睡眠时是所有记忆都有机会被重组，不是"队列空了才处理"。
        用轮询指针确保每个节点定期做梦，不依赖新节点入队触发。

        逻辑：
        1. 从指针位置开始遍历 KG 所有节点
        2. 找第一个 7 天内未做过梦的节点
        3. 指针前移
        4. 所有节点都处理过了 → 重置指针，等待新节点加入
        """
        all_nodes = self.kg.get_all_nodes(active_only=True)
        if not all_nodes:
            return None

        n = len(all_nodes)
        for i in range(n):
            idx = (self.dream_pointer + i) % n
            node_name = all_nodes[idx]

            if not self.kg.has_recent_dreams(node_name, within_days=7):
                self.dream_pointer = (idx + 1) % n
                return node_name

        # 所有节点都在 7 天内处理过了 → 重置指针
        self.dream_pointer = 0
        return None  # 队列空，等待新节点

    def fill_low_priority_queue(self):
        """
        旧逻辑（保留用于批量初始化）

        策略：
        1. 扫描 KG 中所有节点
        2. 排除最近 7 天内已处理过的节点
        3. 剩余节点按 quality 排序（低 quality 优先，接近"遗忘"的知识优先做梦）
        4. 全部加入低优先级队列
        """
        all_nodes = self.kg.get_all_nodes()
        recently_processed = self.kg.get_recently_dreamed(within_days=7)

        candidates = [
            (name, node) for name, node in all_nodes
            if name not in recently_processed
            and node.get("status") != STATUS_DORMANT
        ]

        candidates.sort(key=lambda item: item[1].get("quality", 0))

        for name, _ in candidates:
            self.low_queue.put(name)
```

### 3.4 创意做梦运行逻辑（生成器模式）

**核心转变**：DreamAgent 从"关联判断器"变为"洞察生成器"。

- 判断器：判断 A 和 B 有没有关联 → 产出关系标签
- 生成器：基于 A 和 B 生成全新洞察 → 产出新知识节点

**为什么这个区别重要**：如果只是建关联，KG 只是变得更密集；如果生成新洞察，KG 会真正生长出新的知识维度。

```python
    def process_creative_dreaming(self, topic_a: str, topic_b: str):
        """
        创意做梦：对两个远距离节点，生成新洞察

        流程：
        1. LLM 生成创意洞察（新内容，不是判断关联）
        2. 洞察写入 KG 为新节点
        3. 洞察的 trigger_topic 进入探索队列
        """
        result = self.llm_creative_dream(topic_a, topic_b)

        # 写入条件：surprise >= 0.5（洞察够意外）
        if result["has_insight"] and result["surprise"] >= 0.5:
            # 写入 KG：新增洞察节点
            insight_node = self.kg.add_dream_insight(
                content=result["insight"],
                insight_type=result["insight_type"],
                source_topics=[topic_a, topic_b],
                surprise=result["surprise"],
                novelty=result["novelty"],
                trigger_topic=result["trigger_topic"]
            )

            # 新洞察进入探索候选队列
            if result["trigger_topic"]:
                self.engine.add_to_queue(result["trigger_topic"])

            # 记录探索历史（用于后续价值验证）
            self.exploration_history.record_insight_generation(
                insight_node=insight_node,
                source_pair=(topic_a, topic_b),
                timestamp=datetime.now(timezone.utc)
            )

        # 标记为已做梦处理
        self.kg.mark_dreamed(topic_a)

        # === 洞察价值验证回路 ===
        self.verify_existing_insights(topic_a)
```

### 3.5 洞察价值验证回路

```python
    def verify_existing_insights(self, topic: str):
        """
        检查 topic 的已有洞察是否被后续探索验证过

        规则：
        - 如果洞察在过去 7 天内被 SpiderAgent 触发探索过 → quality += 1
        - 如果洞察在过去 7 天内未被触发 → weight -= 0.05
        - weight < 0.2 的洞察 → 标记为 stale
        """
        insights = self.kg.get_insights_generated_from(topic)

        for insight in insights:
            if insight.get("verified"):
                continue

            was_triggered = self.exploration_history.was_insight_triggered(
                insight["node_id"], within_days=7
            )

            if was_triggered:
                self.kg.update_insight_quality(insight["node_id"], delta=1.0)
                insight["verified"] = True
            else:
                self.kg.update_insight_weight(insight["node_id"], delta=-0.05)
```

### 3.6 远距离节点选取（含神经噪声）

```python
    def find_distant_pairs(self, topic: str, max_pairs: int = 5) -> list:
        """
        选取与 topic 距离远且无连接的节点

        策略（三层随机）：
        1. 70%：按距离筛选（distance > 3 且 quality >= 4）
        2. 20%：跨 domain 优先（不同探索分支的远距离节点）
        3. 10%：神经噪声模式——强制随机选取，不考虑距离
           → 模拟人类做梦时的神经元随机激活，产生最意外的连接
        """
        import random
        all_nodes = self.kg.get_all_nodes(active_only=True)

        # 过滤已有连接的节点
        connected = self.kg.get_directly_connected(topic)
        distant_candidates = [n for n in all_nodes if n not in connected]

        def distance(node):
            return self.kg.get_shortest_path_length(topic, node)

        # 距离 > 3 的候选
        distant = [n for n in distant_candidates if distance(n) > 3]

        # 按 quality 过滤（至少有一定探索深度）
        meaningful = [n for n in distant if n.get("quality", 0) >= 4]

        results = []
        for i in range(max_pairs):
            rand = random.random()

            if rand < 0.1:
                # 10%：神经噪声模式——完全随机，不管距离
                candidates_noise = [n for n in all_nodes if n not in connected and n != topic]
                if candidates_noise:
                    chosen = random.choice(candidates_noise)
                    results.append((chosen, -1))  # -1 表示神经噪声模式
                    continue

            elif rand < 0.3:
                # 20%：跨 domain 优先
                # 选和 topic 不在同一探索分支的节点
                topic_domain = self.kg.get_node_domain(topic)
                cross_domain = [n for n in meaningful if self.kg.get_node_domain(n) != topic_domain]
                if cross_domain:
                    chosen = random.choice(cross_domain)
                    results.append((chosen, distance(chosen)))
                    continue

            # 70%：正常按距离筛选
            if meaningful:
                chosen = random.choice(meaningful)
                results.append((chosen, distance(chosen)))
            elif distant:
                chosen = random.choice(distant)
                results.append((chosen, distance(chosen)))

        return results
```

### 3.6 LLM 创意洞察生成（生成器模式）

**核心转变**：DreamAgent 从"关联判断器"变为"洞察生成器"。

- 判断器：判断 A 和 B 有没有关联 → 产出关系标签（关联生成器）
- 生成器：基于 A 和 B 生成全新洞察 → 产出新知识节点（创意做梦引擎）

**为什么这个区别决定演进的必要性**：

| | 关联生成器 | 创意做梦引擎 |
|--|---------|------------|
| 产出 | 关系标签 | 新知识节点 |
| KG 变化 | 变得更密集 | 真正生长 |
| 演进必要 | 低（只是更精确） | 高（创造新维度） |

```python
    def llm_creative_dream(self, topic_a: str, topic_b: str) -> dict:
        """
        创意做梦：对两个完全无关的知识领域，生成全新的洞察

        Returns: {
            has_insight: bool,                    # 是否生成了有价值的洞察
            insight: str,                          # 生成的洞察内容（全新的，不是 A 也不是 B）
            insight_type: str,                    # "hypothesis" | "analogy" | "prediction" | "question"
            surprise: float,                       # 0.0-1.0 意外程度
            novelty: float,                        # 0.0-1.0 新颖程度
            trigger_topic: str | None,            # 这个洞察能触发哪个新探索方向
        }
        """
```

**LLM Prompt（生成式）**：

```
你是创意做梦引擎。不是判断两个领域有没有关联，而是从它们的组合中生成全新的洞察。

Topic A: {topic_a}
Topic B: {topic_b}

要求：
1. 洞察必须是从 A+B 组合中**新生成的**，不是 A 也不是 B
2. 生成的内容必须有认知价值（新的假设、类比、预测、问题）
3. trigger_topic 是指：这个洞察能指向哪个新的探索方向？

生成类型（选最合适的）：
- hypothesis: "如果 A，那么可能 B"（新假设）
- analogy: "A 就像 B 中的 X"（新类比）
- prediction: "基于 A 和 B，X 可能发生"（新预测）
- question: "A 和 B 暗示了一个新问题：X"（新问题）

输出格式（JSON）：
{
  "has_insight": true/false,
  "insight": "具体的新洞察内容（必须是从 A+B 生成的）",
  "insight_type": "hypothesis/analogy/prediction/question",
  "surprise": 0.0-1.0,
  "novelty": 0.0-1.0,
  "trigger_topic": "这个洞察指向的新探索方向（string 或 null）"
}
```

### 3.7 与 SpiderAgent 的协调### 3.7 与 SpiderAgent 的协调

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

### 4.2 降级标准（含 verified + stale）

**核心原则**：pruning 只对 dream_insights 检查权重，不对 parent/child 做权重判断。

- parent/child 是结构性的，二元存在性（有无），不区分强弱
- dream_insights 是创意产出，有权重，可以被判定为"弱"

**新增逻辑**：
- verified=False 且 created_at > 7 天前 → 说明从未被 SpiderAgent 验证 → 直接删除这条 explains
- verified=True 的连接 → 不会被 SleepPruner 删除
- stale=True 的连接 → weight 已经很低，等待被修剪

```
节点同时满足以下条件 → 降级为 dormant：
1. parents = [] 且 children = []（结构上真正孤立）
2. 所有 explains 连接均为 stale=True（weight < 0.2）
3. quality < 7.0
4. 非 root_technology_pool 候选
5. 非最近 7 天内产生过 dream_insight 的节点
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

            # 2. 检查 dream_insights
            insights = self.kg.get_dream_insights(node_name)
            if not insights:
                all_stale = True
                has_verified = False
            else:
                # 先清理：删除从未被验证且已创建超过 7 天的 dream_insights
                for entry in explains:
                    if not entry.get("verified") and self.kg.is_insight_stale(entry["node_id"]):
                        # 从未被验证且超过 7 天 → 删除这个洞察
                        self.kg.remove_dream_insight(entry["node_id"])

                # 重新检查
                remaining = self.kg.get_dream_insights(node_name)
                has_verified = any(e.get("verified") for e in remaining)
                all_stale = all(e.get("stale", False) for e in remaining)

            # 3. 有已验证的连接，不修剪
            if has_verified:
                continue

            # 4. 所有连接都已 stal 且节点质量低 → 降级
            if all_stale and node.get("quality", 0) < 7.0:
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
def add_dream_insight(content: str, insight_type: str, source_topics: list[str],
                         surprise: float, novelty: float, trigger_topic: str | None) -> str:
    """
    添加梦境洞察节点（创意做梦引擎的核心产出）

    新洞察作为 KG 的独立节点存在，不是边的属性

    Returns: 新节点的 node_id
    """
    node_id = f"insight_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
    entry = {
        "node_id": node_id,
        "content": content,
        "insight_type": insight_type,  # hypothesis/analogy/prediction/question
        "source_topics": source_topics,
        "surprise": surprise,
        "novelty": novelty,
        "trigger_topic": trigger_topic,
        "weight": 0.5,
        "verified": False,
        "quality": 0.0,  # 被探索触发后提升
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    state["knowledge"]["dream_insights"][node_id] = entry
    _save_state(state)
    return node_id

def strengthen_connection(topic_a: str, topic_b: str, delta: float = 0.1):
    """
    强化两节点连接（consolidation 使用）
    - 如果连接存在：weight += delta，上限 1.0
    - 如果连接不存在：不操作（consolidation 只强化已有连接）
    """

def mark_explains_verified(from_topic: str, to_topic: str):
    """
    标记某条 explains 连接已被 SpiderAgent 验证过（价值验证回路使用）
    """

def update_explains_weight(from_topic: str, to_topic: str, delta: float):
    """
    更新 explains 连接权重（价值验证回路使用）
    - 如果 weight < 0.2，标记为 stale=True
    - weight 下限 0.0，上限 1.0
    """

def set_consolidated(topic: str):
    """标记节点已巩固"""

def mark_dormant(topic: str):
    """标记为 dormant"""

def reactivate(topic: str):
    """从 dormant 恢复"""

def mark_dreamed(topic: str):
    """标记节点已做过梦处理"""

def mark_explains_verified(from_topic: str, to_topic: str):
    """
    标记某条 explains 连接已被 SpiderAgent 验证过（价值验证回路使用）
    """

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

def get_node_domain(topic: str) -> str:
    """
    返回 topic 所属的探索分支（domain）

    实现：沿着 parent 链向上追溯，找到最近的 root，
    以 root 作为 domain 标识

    用于跨 domain 连接发现（20% 概率优先跨 domain）
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

def get_dream_insights(topic: str) -> list[dict]:
    """
    返回 topic 相关的所有 dream_insight 节点
    （source_topics 中包含 topic 的洞察）
    """

def get_all_dream_insights() -> list[dict]:
    """返回 KG 中所有 dream_insight 节点"""

def remove_dream_insight(node_id: str):
    """删除某个 dream_insight 节点（SleepPruner 使用）"""

def is_insight_stale(node_id: str) -> bool:
    """检查某个洞察是否已过期（从未被验证且超过 7 天）"""

def get_root_pool_names() -> set[str]:
    """返回 root_technology_pool 中所有候选名称"""

def get_recently_dreamed(within_days: int) -> set[str]:
    """
    返回最近 within_days 天内被 DreamAgent 处理过的节点名称
    用于 fill_low_priority_queue 时排除近期已处理的节点
    """

def has_recent_dreams(topic: str, within_days: int) -> bool:
    """
    检查 topic 是否在 within_days 天内做过梦
    用于轮询指针跳过近期已处理的节点
    """
```

### 5.3 ExplorationHistory（探索历史记录）

**职责**：记录每次探索的事件，用于 consolidation 和价值验证回路。

```python
class ExplorationHistory:
    """
    探索历史记录器
    - SpiderAgent 每次探索完成时记录事件
    - DreamAgent 的 consolidation 和价值验证回路依赖此数据

    ⚠️ P0 修复：ExplorationHistory 所有方法必须加锁
    原因：SpiderAgent 写（strengthen_co_occurring）的同时 DreamAgent 读（co_occurred），
          存在 race condition。ExplorationHistory 是共享数据结构，必须线程安全。
    """
    _lock = threading.Lock()

    def record_exploration(self, topic: str, related_nodes: list[str], timestamp: datetime):
        """记录一次探索事件"""
        with self._lock:
            ...

    def co_occurred(self, topic_a: str, topic_b: str, within_hours: int) -> bool:
        """检查 topic_a 和 topic_b 是否在 within_hours 小时内共同出现过"""
        with self._lock:
            ...

    def was_insight_triggered(self, topic_a: str, topic_b: str, within_days: int) -> bool:
        """检查 topic_b 是否在 topic_a 的探索过程中被触发过"""
        with self._lock:
            ...

    def get_recent_explorations(self, within_hours: int) -> list[dict]:
        """返回最近 N 小时的探索记录（用于调试）"""
        with self._lock:
            ...
```

### 5.4 节点级锁实现

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
    """强制 DreamAgent 对指定 topic 执行一次创意做梦"""
    from core.dream_agent import force_dream_topic
    data = request.get_json()
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic is required"}), 400
    result = force_dream_topic(topic)
    return jsonify({"status": "ok", "insight_created": result["insight_created"]})


@app.route("/api/kg/insights/<path:topic>", methods=["GET"])
def api_kg_insights(topic: str):
    """获取节点相关的所有 dream_insight"""
    from core.knowledge_graph import get_dream_insights
    return jsonify({"topic": topic, "insights": get_dream_insights(topic)})
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
| 中层做梦 | 创意生成 + 公平对待所有记忆 | DreamAgent 双队列 + 轮流队列 | ✅ 完全满足 |
| 中层做梦 | 意外洞察发现 | surprise >= 0.5，生成而非判断 | ✅ 完全满足 |
| 中层做梦 | 价值验证反馈 | verified + stale + 洞察验证回路 | ✅ 完全满足 |
| 中层做梦 | 神经噪声模拟 | 10% 神经噪声模式（强制随机） | ✅ 完全满足 |
| 深层修剪 | 弱洞察清理（权重感知） | SleepPruner + dream_insights 清理 | ✅ 完全满足 |

---

## 十、模块依赖关系

```
curious_agent.py (入口)
    ├── SpiderAgent
    │   ├── CuriosityEngine
    │   ├── Explorer
    │   └── KnowledgeGraph (with node-level locks)
    ├── DreamAgent
    │   ├── LLMClient (creative_dream)
    │   ├── high_priority_queue (来自 SpiderAgent)
    │   ├── low_priority_queue (轮流填充)
    │   └── KnowledgeGraph
    └── SleepPruner
        └── KnowledgeGraph
```

---

## 十一、已知问题 & 改进计划

### P0：必须修复（实现前）

**1. ExplorationHistory race condition**
- **问题**：`strengthen_co_occurring` 在 SpiderAgent 里写 `connection_weight`，同时 `co_occurred()` 在 DreamAgent 里读。存在数据不一致风险。
- **修复**：ExplorationHistory 所有方法加 `threading.Lock()`。
- **状态**：✅ 已在 5.3 节修复。

**2. LLM 创意生成质量控制**
- **问题**：两个随机 topic 进去，LLM 一定能编出一个看起来合理的 insight。可能是幻觉，不是真正有价值的连接。
- **修复**：prompt 里加约束（"必须是 A+B 都没提到的全新洞察"），或加验证步骤。
- **状态**：待实现。

### P1：应该改进（实现后优化）

**3. 低优先级队列轮询指针**
- **问题**：被动触发（队列空才填充）导致老节点永久没有做梦机会。
- **修复**：用 `dream_pointer` 主动轮询，每个节点定期都有机会。
- **状态**：✅ 已在 3.3 节修复。

**4. 双门控触发条件**
- **问题**：现在只有新节点入队才触发做梦，没有"时间+次数"门控。
- **修复**：参考 Claude Code Auto Dream，距上次 consolidation ≥24h 且新节点 ≥5 才触发。
- **状态**：待实现。

### P2：可以增强（数字生命体核心能力）

**5. 元认知监控（MetacognitiveMonitor）**
- **问题**：CA 不知道自己知识边界在哪，只知道"不知道"，不知道"自己知道多少"。
- **差距**：数字生命体需要有置信度校准能力。
- **建议实现**：
  ```python
  class MetacognitiveMonitor:
      def get_confidence_interval(self, topic: str) -> tuple[float, float]:
          """返回对 topic 认知的置信区间"""

      def detect_contradictions(self) -> list[Contradiction]:
          """检测 KG 中互相矛盾的认知"""

      def recommend_exploration_priority(self) -> list[str]:
          """推荐应该优先探索的方向（最大不确定性减少）"""
  ```
- **状态**：待规划。

**6. 内部动机系统**
- **问题**：ICM 是外部知识探索的驱动，但数字生命体需要"这件事对我有意义"的情感锚点。
- **建议实现**：给 KG 节点增加"主观重要性"评分，不只是 quality/quality。
- **状态**：待探索。

**7. 自我模型更新**
- **问题**：dream_insight 生成后 KG 变了，但"CA 这个人"没有变。
- **建议实现**：每次做梦后更新自我表征——"我擅长什么、我缺什么能力"。
- **状态**：待探索。

---

## 十二、与 Claude Code Auto Dream 的对比

> 来源：Serper 搜索（2026-03-28）

| 维度 | Claude Code Auto Dream | CA DreamAgent v0.2.6 |
|------|----------------------|---------------------|
| **目标** | 记忆整理/整理 | 创意生成新知识 |
| **触发** | 双门控（时间+次数） | 新节点入队 + 轮询指针 |
| **产出** | 整理后的索引（MEMORY.md ≤200行） | 新洞察节点（KG 生长） |
| **Session 分析** | Targeted grep JSONL | N/A（CA 无 session JSONL） |
| **矛盾检测** | ✅ 有（主动删除矛盾事实） | ⚠️  可加入（4.5 节） |
| **修剪** | 删除矛盾/过时条目 | 弱 explains 清理 + dormant |
| **并发控制** | 锁文件 | 节点级锁 |

**关键差异**：Claude Code Auto Dream 是"整理已有知识"，CA DreamAgent 是"创造新知识"。两个方向互补，不竞争。

---

_Last updated: 2026-03-28 16:36 by R1D3_
_v0.2.6: Creative DreamAgent (insight generator) + SpiderAgent + SleepPruner, dual-queue fairness, value verification, P0/P1 fixes_

