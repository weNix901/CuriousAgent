# OpenCode 完善指南：基于 Curious Agent 的增强建议

> 本文档面向 OpenCode/OpenCode TUI 开发者，提供将好奇 Agent 能力集成到 OpenCode 的具体路径。

---

## 一、OpenCode 当前能力评估

基于 Curious Agent 研究，对 OpenCode 的能力维度评分：

| 能力维度 | OpenCode 现状 | 建议增强 | 优先级 |
|---------|-------------|---------|--------|
| **元认知** | ❌ 无自我监控 | 增加知识状态管理层 | ⭐⭐⭐⭐ |
| **好奇心驱动** | ❌ 完全被动 | 集成好奇心引擎 | ⭐⭐⭐⭐ |
| **持久化知识** | ❌ 无会话积累 | 知识图谱持久化 | ⭐⭐⭐⭐ |
| **主动通知** | ⚠️ 有限 | 增强事件驱动通知 | ⭐⭐⭐ |
| **多 Agent 协作** | ✅ 已有 OMO | 与 OMO 深度集成 | ⭐⭐⭐ |
| **内在动机** | ❌ 无 | 引入强化学习反馈 | ⭐⭐ |

---

## 二、短期增强（1-2周）

### 2.1 知识状态管理层 (KnowledgeState)

在 OpenCode 中增加一个持久化的知识状态层：

```
实现位置: opencode/core/knowledge_state.py
```

**核心接口**：

```python
class KnowledgeState:
    """OpenCode 的知识图谱管理层"""

    def __init__(self, storage_path: str):
        self.state = self._load()
        self.llm = get_llm()  # 用于摘要生成

    # 知识管理
    def add_knowledge(self, topic: str, content: str, source: str = ""):
        """添加新知识，支持 LLM 摘要压缩"""

    def query(self, keywords: list[str]) -> list[dict]:
        """基于关键词查询相关知识"""

    def get_related(self, topic: str, k: int = 5) -> list[dict]:
        """获取与 topic 相关的知识"""

    def summarize(self, topic: str) -> str:
        """LLM 驱动的知识摘要"""

    # 持久化
    def _load(self) -> dict: ...
    def _save(self): ...

    # 统计
    def stats(self) -> dict: ...  # 知识节点数、覆盖领域等
```

**集成到 OpenCode**：

```python
# opencode/core/session.py

class Session:
    def __init__(self):
        self.knowledge = KnowledgeState()  # 新增
        self.metadata = {...}

    def on_message(self, msg):
        # 自动提取知识
        new_facts = self._extract_facts(msg)
        for fact in new_facts:
            self.knowledge.add_knowledge(
                topic=fact.topic,
                content=fact.content,
                source="session:{session_id}"
            )
```

### 2.2 好奇心事件系统 (CuriosityEvents)

增加主动的好奇心驱动事件：

```
实现位置: opencode/core/curiosity.py
```

**事件类型**：

```python
class CuriosityEvent(Enum):
    KNOWLEDGE_GAP = "knowledge_gap"      # 发现知识缺口
    TOPIC_EXPLORED = "topic_explored"   # 主题已探索
    CONTRADICTION = "contradiction"      # 发现矛盾
    USER_INTEREST = "user_interest"     # 用户兴趣信号
    DEPTH_EXHAUSTED = "depth_exhausted" # 深度耗尽
```

**触发示例**：

```python
# 当模型推理中出现"不知道"或知识缺口时
if "不知道" in response or "[UNCONFIRMED]" in response:
    curiosity_engine.emit(
        event_type=CuriosityEvent.KNOWLEDGE_GAP,
        topic=current_topic,
        context=response,
        priority=5.0
    )
```

### 2.3 增强的会话历史 (EnhancedMemory)

```python
# opencode/core/memory.py

class ConversationMemory:
    """
    OpenCode 会话记忆增强版
    在原有历史基础上增加:
    1. 事实提取层
    2. 知识关联图
    3. 遗忘机制
    """

    def __init__(self):
        self.episodic = []     # 情景记忆（原始对话）
        self.semantic = {}      # 语义记忆（提取事实）
        self.working = {}       # 工作记忆（当前会话）

    def extract_facts(self, message: str) -> list[Fact]:
        """LLM 提取对话中的事实"""
        prompt = f"""从以下消息中提取独立事实:
        消息: {message}

        以 JSON 格式返回:
        [{{"subject": "...", "predicate": "...", "object": "..."}}]
        """
        # 调用 LLM 提取
        return llm.extract(prompt)

    def decay_old_memories(self, days: int = 30):
        """
        遗忘机制：降低旧记忆的激活权重
        权重 = base_weight * exp(-decay_rate * age_days)
        """
```

---

## 三、中期增强（1个月）

### 3.1 内在动机驱动的任务生成

```
核心思想: Agent 不是等待用户指令，而是基于好奇心主动生成任务
```

**架构**：

```
┌─────────────────────────────────────────────────────┐
│              Intrinsic Motivation Engine             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐   │
│  │ 好奇心    │ + │ 困惑度   │ + │ 发现率      │   │
│  │Curiosity │   │Confusion │   │Discovery Rate│   │
│  └────┬─────┘   └────┬─────┘   └──────┬───────┘   │
│       │               │                │            │
│       └───────────────┼────────────────┘            │
│                       ▼                              │
│              ┌──────────────┐                       │
│              │  内在动机分   │                       │
│              │Intrinsic Score│                       │
│              └──────┬───────┘                       │
│                     │                                │
│                     ▼                                │
│              ┌──────────────┐                       │
│              │  任务生成器   │                       │
│              │ Task Generator│                       │
│              └──────────────┘                       │
│                     │                                │
│                     ▼                                │
│         ┌───────────────────────┐                   │
│         │ 自动生成子任务序列     │                   │
│         └───────────────────────┘                   │
└─────────────────────────────────────────────────────┘
```

**实现**：

```python
# opencode/core/intrinsic_motivation.py

class IntrinsicMotivationEngine:
    """
    内在动机引擎
    参考: Pathak et al. (2017) Curiosity-driven Exploration
    """

    def __init__(self, curiosity_module, knowledge_state):
        self.curiosity = curiosity_module
        self.knowledge = knowledge_state
        self.ema_alpha = 0.95  # 指数移动平均参数

    def compute_intrinsic_reward(self, state: str, action: str, next_state: str) -> float:
        """
        内在动机 = 预测误差 (ICM 方法)
        Agent 因难以预测的结果获得奖励
        """
        # 特征编码
        phi_s = self._encode(state)
        phi_sp = self._encode(next_state)

        # 逆模型: 预测 action
        pred_action = self.inverse_model(phi_s, phi_sp)

        # 正模型: 预测 next_state
        pred_next = self.forward_model(phi_s, action)

        # 预测误差 = 内在奖励
        reward = self.ema_alpha * reward + (1 - self.ema_alpha) * (
            ||phi_sp - pred_next||² + ||action - pred_action||²
        )
        return reward

    def should_explore(self) -> bool:
        """判断是否应该触发主动探索"""
        curiosity_score = self.curiosity.get_max_score()
        return curiosity_score > self.exploration_threshold
```

### 3.2 多 Agent 好奇心协调

当 OMO 中的多个 Agent 共享同一个好奇心层：

```
┌─────────────────────────────────────────────────────┐
│           Shared Curiosity Layer (SCL)              │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Metis ─┐                                            │
│  Oracle ─┼──▶ Shared Curiosity Queue ──▶ 探索执行   │
│  Libra ──┤         ↑                                  │
│  Explore ─┼──── 写入 │                                │
│  Atlas ──┘         │                                  │
│                    │                                  │
│              ┌─────┴─────┐                           │
│              │ 知识融合   │                           │
│              │Knowledge  │                           │
│              │  Broker   │                           │
│              └───────────┘                           │
└─────────────────────────────────────────────────────┘
```

```python
# opencode/core/shared_curiosity.py

class SharedCuriosityLayer:
    """
    多 Agent 共享好奇心层
    每个 Agent 可以:
    1. 写入自己的好奇心发现
    2. 读取其他 Agent 的发现
    3. 基于共享知识协调探索
    """

    def __init__(self):
        self.shared_queue = PriorityQueue()  # 共享优先级队列
        self.agent_knowledge = {}             # 各 Agent 的知识贡献
        self.knowledge_graph = KnowledgeGraph()

    def contribute(self, agent_id: str, topic: str, findings: str):
        """Agent 贡献新发现"""
        self.agent_knowledge.setdefault(agent_id, []).append({
            "topic": topic,
            "findings": findings,
            "timestamp": datetime.now()
        })
        self.knowledge_graph.merge(topic, findings, agent_id)

    def get_coordination_hint(self, agent_id: str, current_task: str) -> str:
        """给 Agent 提供协调建议"""
        related = self.knowledge_graph.get_related(current_task)
        other_agents = [k for k in related if k["contributor"] != agent_id]
        if other_agents:
            return f"注意: {other_agents[0]['contributor']} 已在探索相关主题"
        return ""
```

### 3.3 工作记忆建模

```
实现位置: opencode/core/working_memory.py

核心参考: Baddeley's Working Memory Model
- phonological loop: 当前会话的文本内容
- visuospatial sketchpad: 代码/结构的可视化表示
- episodic buffer: 当前任务上下文
- central executive: 注意力控制器
```

```python
class WorkingMemory:
    """
    Agent 工作记忆
    实现 Baddeley 多组件模型
    """

    def __init__(self, capacity: int = 7):
        self.phonological = []    # 文本内容
        self.structural = []      # 代码结构
        self.episodic = {}        # 任务上下文
        self.executive = ExecutiveController()

    def push(self, item: WorkingMemoryItem):
        """推入工作记忆，自动容量管理"""
        if item.type == "text":
            self.phonological.append(item)
        elif item.type == "structure":
            self.structural.append(item)

        # 容量超限时，激活遗忘
        if len(self.phonological) > self.capacity * 2:
            self.forget_least_relevant()

    def forget_least_relevant(self):
        """遗忘最不相关的项"""
        # 计算各项的注意力权重
        weights = [self.executive.attention_weight(item) for item in self.phonological]
        min_idx = weights.index(min(weights))
        self.phonological.pop(min_idx)

    def snapshot(self) -> dict:
        """获取当前工作记忆快照"""
        return {
            "phonological_size": len(self.phonological),
            "structural_size": len(self.structural),
            "current_episode": self.episodic,
            "attention_focus": self.executive.focus
        }
```

---

## 四、长期愿景（季度目标）

### 4.1 自我改进循环

```
┌─────────────────────────────────────────────────────────┐
│                   Self-Improvement Loop                │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   执行任务 ──▶ 结果评估 ──▶ 反思 ──▶ 策略更新           │
│       ↑                                    │             │
│       └────────────────────────────────────┘             │
│                      (迭代)                              │
└─────────────────────────────────────────────────────────┘
```

```python
# opencode/core/self_improver.py

class SelfImprover:
    """
    自我改进器
    实现: 执行 → 评估 → 反思 → 策略更新的闭环
    """

    def on_task_complete(self, task: Task, result: Result):
        # 1. 评估结果质量
        quality = self.evaluator.evaluate(task, result)

        # 2. 如果质量低，触发反思
        if quality < self.threshold:
            reflection = self.reflector.analyze(task, result)

            # 3. 提取改进策略
            new_strategies = self.extractor.extract(reflection)

            # 4. 更新策略库
            self.strategy_library.update(new_strategies)

            # 5. 记录到知识图谱
            self.knowledge.add_knowledge(
                topic=f"strategy:{task.type}",
                content=reflection.summary,
                quality_score=quality
            )
```

### 4.2 情感建模（可选方向）

```
探索: Agent 是否需要"情感"来驱动好奇心？

类比人类:
- 好奇心 = 认知性情感（想知道）
- 惊讶 = 对意外的响应
- 满足 = 发现后的正向反馈
- 挫折感 = 引导深入探索

实现建议:
- 不是真正的情感，而是情感化的信号
- 用 LLM 生成"情感标签"影响行为选择
```

---

## 五、OpenCode 集成的具体建议

### 5.1 架构层面的建议

```
当前 OpenCode:
  User Input → Model → Output

建议改为:
  User Input → KnowledgeState → Model → CuriosityEngine → Output
                        ↑                              ↓
                  知识查询/积累              好奇心驱动的新发现
```

### 5.2 建议的文件变更

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `opencode/core/knowledge_state.py` | 知识状态管理层 |
| 新增 | `opencode/core/curiosity.py` | 好奇心引擎 |
| 新增 | `opencode/core/working_memory.py` | 工作记忆 |
| 修改 | `opencode/core/session.py` | 集成知识层 |
| 修改 | `opencode/prompts/system.py` | 增加元认知指令 |

### 5.3 渐进式集成路径

```
Phase 1 (Week 1-2): 知识状态层
  - 实现 KnowledgeState
  - 会话结束时自动提取并存储关键事实
  - 可查询: "我之前了解过什么?"

Phase 2 (Week 3-4): 好奇心事件
  - 实现 CuriosityEvent 系统
  - 检测知识缺口时触发探索建议
  - UI: 在 OpenCode 中显示好奇心队列

Phase 3 (Month 2): 工作记忆
  - 实现 WorkingMemory
  - 改善多轮对话中的上下文管理
  - 支持更长的任务链

Phase 4 (Month 3+): 内在动机
  - 实现 IntrinsicMotivationEngine
  - Agent 主动生成探索任务
  - 多 Agent 好奇心协调
```

---

## 六、参考实现

Curious Agent MVP 完整代码可作为参考实现：

```
/root/dev/curious-agent/
├── core/knowledge_graph.py    → 对应 KnowledgeState
├── core/curiosity_engine.py  → 对应 CuriosityEngine
├── core/explorer.py          → 对应 TaskGenerator
└── curious_agent.py          → 主调度器
```

关键差异：

| Curious Agent | OpenCode 增强 |
|---------------|--------------|
| Python 独立进程 | 内嵌模块 |
| JSON 持久化 | SQLite 或内存 |
| 启发式评分 | LLM 驱动的语义评分 |
| 单 Agent | 多 Agent (OMO) |

---

## 七、总结

Curious Agent MVP 证明了**好奇驱动的自主探索**在 Python 中是可行且有价值的。

**给 OpenCode 的核心建议**：

1. **先加知识状态层** — 最简单，立即有效
2. **好奇心事件** — 让 Agent 能"感知"自己的知识缺口
3. **工作记忆** — 改善长对话质量
4. **多 Agent 协调** — OMO 已具备基础，进一步增强共享好奇心层
5. **内在动机** — 长期目标，让 Agent 真正主动

每一步都有独立的用户价值，不需要一次性全部实现。
