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

### 3.4 运行逻辑（含价值验证回路）

```python
    def process_associations(self, topic: str):
        """对单个 topic 扫描远距离关联"""
        distant_pairs = self.find_distant_pairs(topic)

        for distant_node, distance in distant_pairs:
            result = self.llm_ask_association(topic, distant_node)

            # 写入条件：surprise >= 0.5（意外度够高）
            # 取消 confidence >= 0.7 的门控——避免过滤最意外的连接
            if result["has_association"] and result["surprise"] >= 0.5:
                self.kg_write_with_lock(topic, distant_node, result)

        # 标记为已做梦处理
        self.kg.mark_dreamed(topic)

        # === 价值验证回路：检查已有连接是否被验证 ===
        self.verify_existing_connections(topic)
```

**价值验证回路逻辑**：

```python
    def verify_existing_connections(self, topic: str):
        """
        检查 topic 的已有 explains 连接是否被 SpiderAgent 触发验证过

        规则：
        - 如果 explains 连接在过去 7 天内被 SpiderAgent 触发过 → verified=True, weight += 0.1
        - 如果 explains 连接在过去 7 天内未被触发 → weight -= 0.05
        - weight < 0.2 的连接 → 标记为 stale，后续可被 SleepPruner 清理
        """
        explains = self.kg.get_explains(topic)
        now = datetime.now(timezone.utc)

        for entry in explains:
            if entry.get("verified"):
                continue  # 已验证过，跳过

            # 检查是否在最近探索中被触发
            was_triggered = self.exploration_history.was_ever_triggered(
                topic, entry["target"], within_days=7
            )

            if was_triggered:
                # 被验证了，强化权重
                self.kg.update_explains_weight(
                    topic, entry["target"], delta=0.1
                )
                entry["verified"] = True
            else:
                # 未被验证，缓慢衰减
                self.kg.update_explains_weight(
                    topic, entry["target"], delta=-0.05
                )
```

### 3.5 远距离节点选取（含神经噪声）

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

### 3.6 LLM 关联判断（意外度 + 新颖性）

**核心改进**：从"置信度"改为"意外度+新颖性"，解决最意外连接被过滤的问题。

```python
    def llm_ask_association(self, topic_a: str, topic_b: str) -> dict:
        """
        强制 LLM 判断两个节点是否有意外关联

        输出四个维度（不再是单一置信度）：
        1. has_association: bool - 是否存在关联
        2. relation_type: str - 关联类型
        3. surprise: float  # 0.0-1.0 意外度——建立这个连接需要多创新的推理？
                             #   0.0 = 常识（不需要推理）
                             #   0.5 = 需要跨领域类比
                             #   1.0 = 完全原创假设
        4. novelty: float   # 0.0-1.0 新颖度——这个关联在知识图谱中是否已知？
                             #   0.0 = 已有连接（重复）
                             #   0.5 = 部分已知，有新角度
                             #   1.0 = 全新组合

        写入条件：has_association=True AND surprise >= 0.5（取消置信度门控）
        """
```

**LLM Prompt**：

```
你是一个知识关联分析器，专注于发现"意外但有价值"的跨领域连接。

Topic A: {topic_a}
Topic B: {topic_b}

请分析这两个知识点的关系，输出四个维度的判断：

1. **has_association**: 这两个 topic 之间是否存在可建立的关联？（yes/no）

2. **relation_type**: 关联类型
   - causal: 因果关系（A 导致 B）
   - analogical: 类比关系（A 像 B）
   - shared_foundation: 共同基础（A 和 B 共享底层原理）
   - hierarchical: 层级关系（A 是 B 的上层/下层概念）
   - none: 无关联

3. **surprise（意外度）**: 建立这个关联需要多创新的推理？
   - 0.0-0.3: 常识关联，不需要推理（e.g. "transformer → attention"）
   - 0.4-0.6: 需要跨领域类比（e.g. "transformer → brain regionalization"）
   - 0.7-1.0: 需要完全原创的假设（e.g. "curiosity → circuit breaker"）

4. **novelty（新颖度）**: 这个关联在知识图谱中是否已知？
   - 0.0-0.3: 已有连接，重复（知识图谱中很可能已存在）
   - 0.4-0.6: 部分已知，有新角度
   - 0.7-1.0: 全新组合，极为罕见

注意：**即使 has_association=no，如果 surprise >= 0.7，也请说明这两个 topic 为什么意外地没有关联——这本身就是有价值的洞察。**

输出格式（JSON）：
{
  "has_association": true/false,
  "relation_type": "causal/analogical/shared_foundation/hierarchical/none",
  "surprise": 0.0-1.0,
  "novelty": 0.0-1.0,
  "description": "一段话描述关联内容"
}
```

**写入决策逻辑**：

```python
    def should_write_connection(self, result: dict) -> bool:
        """
        写入条件：
        - has_association=True
        - surprise >= 0.5（意外度够高，不被过滤）

        不再要求 confidence >= 0.7——这是关键改变
        """
        return (
            result["has_association"]
            and result["surprise"] >= 0.5
        )
```
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

### 4.2 降级标准（含 verified + stale）

**核心原则**：pruning 只对 explains 连接检查权重，不对 parent/child 做权重判断。

- parent/child 是结构性的，二元存在性（有无），不区分强弱
- explains 是创意连接，有权重，可以被判定为"弱"

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

            # 2. 检查 explains 连接
            explains = self.kg.get_explains(node_name)
            if not explains:
                # 既无结构性连接，也无 explains → 真正孤立
                all_stale = True
                has_verified = False
            else:
                # 先清理：删除从未被验证且已创建超过 7 天的 explains
                for entry in explains:
                    if not entry.get("verified") and self.kg.is_explains_stale(node_name, entry["target"]):
                        # 从未被验证且超过 7 天 → 删除这条 explains
                        self.kg.remove_explains(node_name, entry["target"])

                # 重新检查
                remaining = self.kg.get_explains(node_name)
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
def add_explains(from_topic: str, to_topic: str, relation: str, surprise: float, novelty: float, weight: float = 0.5):
    """
    添加 explains 连接（含意外度、新颖度、验证状态）

    初始 weight = 0.5（新建连接的默认权重）
    verified = False（待 SpiderAgent 探索触发后验证）
    """
    entry = {
        "target": to_topic,
        "relation": relation,
        "surprise": surprise,
        "novelty": novelty,
        "weight": weight,
        "verified": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

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

def get_explains(topic: str) -> list[dict]:
    """返回 topic 的 explains 连接（含 weight 字段）"""

def has_recent_explains(topic: str, within_days: int) -> bool:
    """检查节点最近 N 天是否有新的 explains 连接"""

def is_explains_stale(from_topic: str, to_topic: str) -> bool:
    """
    检查某条 explains 连接是否已过期（从未被验证且超过 7 天）
    """

def remove_explains(from_topic: str, to_topic: str):
    """
    删除某条 explains 连接（价值验证回路使用）
    """

def get_root_pool_names() -> set[str]:
    """返回 root_technology_pool 中所有候选名称"""

def get_recently_dreamed(within_days: int) -> set[str]:
    """
    返回最近 within_days 天内被 DreamAgent 处理过的节点名称
    用于 fill_low_priority_queue 时排除近期已处理的节点
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
    """

    def record_exploration(self, topic: str, related_nodes: list[str], timestamp: datetime):
        """
        记录一次探索事件

        Args:
            topic: 本次探索的 topic
            related_nodes: 本次探索中同时涉及的节点列表
            timestamp: 探索时间
        """

    def co_occurred(self, topic_a: str, topic_b: str, within_hours: int) -> bool:
        """
        检查 topic_a 和 topic_b 是否在 within_hours 小时内共同出现过
        （用于 consolidation 的 Hebbian 强化）
        """

    def was_ever_triggered(self, topic_a: str, topic_b: str, within_days: int) -> bool:
        """
        检查 topic_b 是否在 topic_a 的探索过程中被触发过
        （用于价值验证回路：explains 连接是否被实际使用）

        触发定义：topic_a 的探索结果中涉及了 topic_b，
        或者 SpiderAgent 基于 topic_a→topic 的 explains 连接进行了后续探索
        """

    def get_recent_explorations(self, within_hours: int) -> list[dict]:
        """返回最近 N 小时的探索记录（用于调试）"""
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


def kg_write_with_lock(from_topic: str, to_topic: str, result: dict):
    """
    带节点级锁的写入（DreamAgent 使用）
    确保和 SpiderAgent 不会同时写同一节点

    死锁预防：按节点名字排序锁顺序后再获取

    result 格式：{has_association, relation_type, surprise, novelty, description}
    """
    lock_a = NodeLockRegistry.get_lock(from_topic)
    lock_b = NodeLockRegistry.get_lock(to_topic)

    # 按名字排序，确保全局顺序一致
    locks = sorted([lock_a, lock_b], key=lambda l: id(l))

    with locks[0], locks[1]:
        add_explains(
            from_topic, to_topic,
            result["relation_type"],
            result["surprise"],
            result["novelty"],
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
| 中层做梦 | 意外连接发现 | surprise >= 0.5 替代 confidence >= 0.7 | ✅ 完全满足 |
| 中层做梦 | 价值验证反馈 | verified + stale + 价值验证回路 | ✅ 完全满足 |
| 中层做梦 | 神经噪声模拟 | 10% 神经噪声模式（强制随机） | ✅ 完全满足 |
| 深层修剪 | 弱连接清理（权重感知） | SleepPruner + verified/stale | ✅ 完全满足 |

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
