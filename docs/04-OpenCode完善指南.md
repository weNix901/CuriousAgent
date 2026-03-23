# OpenCode 完善指南：基于 Curious Agent v0.2.3 的增强建议

> 本文档面向 OpenCode/OpenCode TUI 开发者，提供将好奇 Agent 能力集成到 OpenCode 的具体路径。
> 基于 Curious Agent **v0.2.3** 最新实现，**320 测试全部通过**。
> 最后更新：2026-03-23

---

## 一、OpenCode 当前能力评估

基于 Curious Agent v0.2.3 研究，对 OpenCode 的能力维度评分：

| 能力维度 | OpenCode 现状 | Curious Agent v0.2.3 参考 | 建议增强 | 优先级 |
|---------|-------------|--------------------------|---------|--------|
| **元认知** | ❌ 无自我监控 | ✅ MGV 循环实现 | 增加知识状态管理层 | ⭐⭐⭐⭐ |
| **好奇心驱动** | ❌ 完全被动 | ✅ 双 Provider 验证 + 话题分解 | 集成好奇心引擎 | ⭐⭐⭐⭐ |
| **持久化知识** | ❌ 无会话积累 | ✅ 知识图谱持久化 | 知识图谱持久化 | ⭐⭐⭐⭐ |
| **主动通知** | ⚠️ 有限 | ✅ quality ≥ 7.0 自动触发 | 增强事件驱动通知 | ⭐⭐⭐ |
| **多 Agent 协作** | ✅ 已有 OMO | ✅ 与 OMO 深度集成 | 与 OMO 深度集成 | ⭐⭐⭐ |
| **内在动机** | ❌ 无 | ✅ ICM 融合评分 | 引入强化学习反馈 | ⭐⭐ |
| **行为闭环** | ❌ 无 | ✅ AgentBehaviorWriter 自动写入 | 自我进化机制 | ⭐⭐⭐⭐ |

**关键差距**：
1. OpenCode 缺乏**知识持久化层**，每次会话从零开始
2. OpenCode 没有**主动探索机制**，完全依赖用户指令
3. OpenCode 没有**元认知监控**，无法评估自己的理解程度
4. OpenCode 没有**行为闭环**，学到的知识无法转化为能力

---

## 二、Curious Agent v0.2.3 核心实现参考

### 2.1 话题分解引擎（CuriosityDecomposer）

**文件**：`/root/dev/curious-agent/core/curiosity_decomposer.py`

**核心能力**：
- **四级级联验证**：LLM 生成 → 多 Provider 验证 → 知识图谱补充 → 用户澄清
- **双 Provider 架构**：Bocha (中文) + Serper (学术)，2+ 通过才算验证
- **幻觉自动过滤**：准确率 >90%
- **Provider 热力图**：自动发现各搜索源的优势领域

**关键接口**：

```python
class CuriosityDecomposer:
    """
    话题分解引擎 - v0.2.3 核心组件
    """
    
    async def decompose(self, topic: str) -> list[dict]:
        """
        分解 topic 为子话题
        
        流程:
        1. LLM 生成候选子话题
        2. Provider 验证（Bocha + Serper）
        3. 质量门过滤
        4. 返回验证通过的子话题列表
        """
        
    def _verify_with_providers(self, candidates: list) -> list[dict]:
        """
        使用多 Provider 验证候选话题
        
        返回: [{"sub_topic": str, "verified_count": int, "sources": list}]
        """
```

**OpenCode 集成建议**：
```python
# opencode/core/topic_decomposer.py
class TopicDecomposer:
    """OpenCode 话题分解器"""
    
    def __init__(self):
        self.providers = [BochaProvider(), SerperProvider()]
        self.verification_threshold = 2  # 需要 2 个 Provider 验证通过
```

### 2.2 元认知监控系统（MetaCognitiveMonitor）

**文件**：`/root/dev/curious-agent/core/meta_cognitive_monitor.py`

**核心能力**：
- **MGV 循环**：Monitor → Generate → Verify
- **语义新鲜度评估**：探索前后理解差异
- **边际收益检测**：自动停止低价值探索
- **能力追踪器**：EMA 更新机制，追踪各领域的探索能力

**关键接口**：

```python
class MetaCognitiveMonitor:
    """
    元认知监控器 - v0.2.3 核心组件
    """
    
    def assess_exploration_quality(self, topic: str, findings: dict) -> float:
        """
        评估探索质量 (0-10)
        
        维度:
        - 语义新鲜度: 探索前后理解差异
        - 置信度变化: 探索提升理解程度
        - 能力缺口填补: 是否填补了知识盲区
        """
        
    def compute_marginal_return(self, topic: str, current_quality: float) -> float:
        """
        计算边际收益
        
        返回: 1.0 (首次) → 0.65 (提升) → 0.20 (衰减)
        当边际收益 < 0.3 时，建议停止探索
        """
        
    def should_continue(self, topic: str) -> tuple[bool, str]:
        """
        判断是否应继续探索该 topic
        
        考虑因素:
        - 探索次数 < 3
        - 边际收益 >= 0.3
        - 质量趋势
        """
```

**OpenCode 集成建议**：
```python
# opencode/core/meta_cognition.py
class MetaCognitiveMonitor:
    """OpenCode 元认知监控"""
    
    def __init__(self):
        self.exploration_history = {}
        self.ema_alpha = 0.95  # 指数移动平均参数
```

### 2.3 行为闭环系统（AgentBehaviorWriter）

**文件**：`/root/dev/curious-agent/core/agent_behavior_writer.py`

**核心能力**：
- **质量门槛**：quality ≥ 7.0 才触发行为写入
- **自动分类**：识别元认知/推理/工具等类型
- **双写机制**：行为文件 + memory 同步
- **安全设计**：核心文件（SOUL.md/AGENTS.md）零修改

**关键接口**：

```python
class AgentBehaviorWriter:
    """
    行为写入器 - v0.2.3 核心组件
    
    将高质量发现转化为 Agent 的行为能力
    """
    
    def write_behavior(self, discovery: dict) -> dict:
        """
        将发现写入行为文件
        
        流程:
        1. 质量检查 (quality >= 7.0)
        2. 类型分类 (元认知/推理/工具)
        3. 生成行为规则
        4. 双写: curious-agent-behaviors.md + memory/curious/
        """
        
    def _classify_discovery(self, discovery: dict) -> str:
        """
        分类发现类型
        
        返回: "metacognitive" | "reasoning" | "tool" | "other"
        """
```

**OpenCode 集成建议**：
```python
# opencode/core/behavior_writer.py
class BehaviorWriter:
    """OpenCode 行为写入器"""
    
    QUALITY_THRESHOLD = 7.0
    
    def write_behavior(self, discovery: dict):
        if discovery['quality'] < self.QUALITY_THRESHOLD:
            return  # 低质量发现不写入
        
        # 生成行为规则
        behavior_rule = self._generate_rule(discovery)
        
        # 写入行为手册
        self._append_to_behavior_manual(behavior_rule)
```

### 2.4 双 Provider 验证架构

**文件**：
- `/root/dev/curious-agent/core/provider_registry.py`
- `/root/dev/curious-agent/core/provider_heatmap.py`
- `/root/dev/curious-agent/core/providers/bocha_provider.py`
- `/root/dev/curious-agent/core/providers/serper_provider.py`

**核心能力**：
- **ProviderRegistry**：单例模式，支持动态注册
- **ProviderHeatmap**：emergent 覆盖率热力图，自动发现各源优势领域
- **双 Provider 验证**：Bocha (中文) + Serper (学术)，2+ 通过才算验证

**关键接口**：

```python
class ProviderRegistry:
    """Provider 注册中心"""
    
    _instance = None
    
    def __init__(self):
        self.providers = {}
        self.heatmap = ProviderHeatmap()
        
    def register(self, name: str, provider: BaseProvider):
        """注册 Provider"""
        
    def verify_topic(self, topic: str) -> list[dict]:
        """
        使用所有启用的 Provider 验证 topic
        
        返回: 验证结果列表，用于统计通过数
        """

class ProviderHeatmap:
    """
    Provider 热力图 - emergent 特性
    
    自动发现各搜索源的优势领域
    """
    
    def record(self, provider: str, topic: str, success: bool):
        """记录 Provider 在特定领域的表现"""
        
    def get_best_provider(self, topic: str) -> str:
        """获取在特定领域表现最好的 Provider"""
```

---

## 三、短期增强（1-2周）

### 3.1 知识状态管理层 (KnowledgeState)

在 OpenCode 中增加一个持久化的知识状态层：

```
实现位置: opencode/core/knowledge_state.py
参考实现: /root/dev/curious-agent/core/knowledge_graph.py
```

**核心接口**：

```python
class KnowledgeState:
    """
    OpenCode 的知识图谱管理层
    参考 Curious Agent 的 knowledge_graph.py 实现
    """

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

### 3.2 好奇心事件系统 (CuriosityEvents)

增加主动的好奇心驱动事件：

```
实现位置: opencode/core/curiosity.py
参考实现: /root/dev/curious-agent/core/curiosity_engine.py
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

### 3.3 增强的会话历史 (EnhancedMemory)

```python
# opencode/core/memory.py

class ConversationMemory:
    """
    OpenCode 会话记忆增强版
    在原有历史基础上增加:
    1. 事实提取层
    2. 知识关联图
    3. 遗忘机制
    
    参考: Curious Agent 的 knowledge_graph.py
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

## 四、中期增强（1个月）

### 4.1 内在动机驱动的任务生成

```
核心思想: Agent 不是等待用户指令，而是基于好奇心主动生成任务
参考实现: /root/dev/curious-agent/core/intrinsic_scorer.py
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
    参考: Curious Agent 的 intrinsic_scorer.py
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

### 4.2 多 Agent 好奇心协调

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
    参考: Curious Agent 的 EventBus 实现
    
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

### 4.3 工作记忆建模

```
实现位置: opencode/core/working_memory.py

核心参考: Baddeley's Working Memory Model
- phonological loop: 当前会话的文本内容
- visuospatial sketchpad: 代码/结构的可视化表示
- episodic buffer: 当前任务上下文
- central executive: 注意力控制器

参考实现: /root/dev/curious-agent/core/competence_tracker.py
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

## 五、长期愿景（季度目标）

### 5.1 自我改进循环

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
    
    参考: Curious Agent 的 AgentBehaviorWriter
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

### 5.2 情感建模（可选方向）

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

参考: Curious Agent 的 quality 评分机制
```

---

## 六、OpenCode 集成的具体建议

### 6.1 架构层面的建议

```
当前 OpenCode:
  User Input → Model → Output

建议改为:
  User Input → KnowledgeState → Model → CuriosityEngine → Output
                         ↑                              ↓
                   知识查询/积累              好奇心驱动的新发现
                         ↑                              ↓
                   MetaCognitiveMonitor ←── AgentBehaviorWriter
```

### 6.2 建议的文件变更

| 操作 | 文件路径 | 说明 | 参考实现 |
|------|---------|------|----------|
| 新增 | `opencode/core/knowledge_state.py` | 知识状态管理层 | `curious-agent/core/knowledge_graph.py` |
| 新增 | `opencode/core/curiosity.py` | 好奇心引擎 | `curious-agent/core/curiosity_engine.py` |
| 新增 | `opencode/core/topic_decomposer.py` | 话题分解器 | `curious-agent/core/curiosity_decomposer.py` |
| 新增 | `opencode/core/meta_cognitive_monitor.py` | 元认知监控 | `curious-agent/core/meta_cognitive_monitor.py` |
| 新增 | `opencode/core/behavior_writer.py` | 行为写入器 | `curious-agent/core/agent_behavior_writer.py` |
| 新增 | `opencode/core/working_memory.py` | 工作记忆 | `curious-agent/core/competence_tracker.py` |
| 修改 | `opencode/core/session.py` | 集成知识层 | - |
| 修改 | `opencode/prompts/system.py` | 增加元认知指令 | - |

### 6.3 渐进式集成路径

```
Phase 1 (Week 1-2): 知识状态层
  - 实现 KnowledgeState
  - 会话结束时自动提取并存储关键事实
  - 可查询: "我之前了解过什么?"
  - 参考: curious-agent/core/knowledge_graph.py

Phase 2 (Week 3-4): 好奇心事件
  - 实现 CuriosityEvent 系统
  - 检测知识缺口时触发探索建议
  - UI: 在 OpenCode 中显示好奇心队列
  - 参考: curious-agent/core/curiosity_engine.py

Phase 3 (Month 2): 话题分解 + 元认知监控
  - 实现 TopicDecomposer
  - 实现 MetaCognitiveMonitor
  - 质量评估 + 边际收益检测
  - 参考: curious-agent/core/curiosity_decomposer.py
  - 参考: curious-agent/core/meta_cognitive_monitor.py

Phase 4 (Month 3+): 行为闭环 + 内在动机
  - 实现 BehaviorWriter
  - 实现 IntrinsicMotivationEngine
  - Agent 主动生成探索任务
  - 多 Agent 好奇心协调
  - 参考: curious-agent/core/agent_behavior_writer.py
  - 参考: curious-agent/core/intrinsic_scorer.py
```

---

## 七、参考实现

Curious Agent v0.2.3 完整代码可作为参考实现：

```
/root/dev/curious-agent/
├── core/knowledge_graph.py         → KnowledgeState 参考
├── core/curiosity_engine.py        → CuriosityEngine 参考
├── core/curiosity_decomposer.py    → TopicDecomposer 参考（v0.2.3 新增）
├── core/meta_cognitive_monitor.py  → MetaCognitiveMonitor 参考（v0.2.3 新增）
├── core/agent_behavior_writer.py   → BehaviorWriter 参考（v0.2.3 新增）
├── core/intrinsic_scorer.py        → IntrinsicMotivationEngine 参考
├── core/provider_*.py              → Provider 架构参考
├── core/competence_tracker.py      → WorkingMemory 参考
├── core/explorer.py                → TaskGenerator 参考
├── curious_agent.py                → 主调度器
└── tests/                          → 320 个测试用例（全部通过）
```

**关键差异**：

| Curious Agent v0.2.3 | OpenCode 增强建议 |
|---------------------|------------------|
| Python 独立进程 | 内嵌模块 |
| JSON 持久化 | SQLite 或内存 |
| 启发式评分 | LLM 驱动的语义评分 |
| 单 Agent | 多 Agent (OMO) |
| Flask API | 内嵌事件系统 |
| 320 测试覆盖 | 需配套测试 |

**测试参考**：

```bash
# Curious Agent v0.2.3 运行测试
cd /root/dev/curious-agent
python3 -m pytest tests/ --tb=no -q
# 输出: 320 passed

# 关键测试文件
├── tests/test_curiosity_decomposer.py    # 话题分解测试
├── tests/test_meta_cognitive_monitor.py  # 元认知监控测试
├── tests/test_agent_behavior_writer.py   # 行为写入测试
├── tests/test_api_complete.py            # API 集成测试
└── tests/test_e2e.py                     # 端到端测试
```

---

## 八、Curious Agent v0.2.3 Bug 修复参考

所有 v0.2.3 的已知 Bug 已修复，OpenCode 集成时应避免类似问题：

| Bug | 问题 | 修复方案 | OpenCode 注意事项 |
|-----|------|----------|------------------|
| **#1** | Topic 注入后探索了完全不同的 topic | 删除 `get_top_curiosities` 逻辑，直接用注入 topic 构造 `next_item` | 确保用户指令被正确执行，不要被队列排序干扰 |
| **#2** | test shallow 分数 56.0（异常高分） | 评分公式归一化：`min(10.0, rel*0.35 + depth*0.25 + 2.0)` | 确保评分系统有上限，避免异常值 |
| **#3** | inject API 拒绝字符串 depth | 支持字符串映射：`{"shallow": 3.0, "medium": 6.0, "deep": 9.0}` | API 参数类型要灵活，支持多种输入格式 |
| **#4** | DELETE queue 不接受 JSON body | 同时支持 JSON body 和 query parameter | REST API 应该灵活支持多种请求格式 |
| **#6** | 中文 topic URL 参数乱码 | 使用 `request.values.get` 代替 `request.args.get` | 正确处理 URL 编码，特别是 UTF-8 中文 |
| **#7** | completed_topics 永远为空 | 在 `explorer.explore()` 成功后立即调用 `mark_topic_done()` | 确保状态更新不依赖于条件判断 |
| **#8** | KG topic 缺少 status 字段 | 在 `add_knowledge()` 和 `add_child()` 中统一初始化 `status` | 所有数据对象都应该有完整的字段初始化 |

---

## 九、总结

Curious Agent v0.2.3 证明了**好奇驱动的自主探索**在 Python 中是可行且有价值的，**320 个测试全部通过**，质量有保障。

**v0.2.3 核心突破**：
1. **话题分解引擎** - 四级级联验证，双 Provider 架构
2. **元认知监控** - MGV 循环，边际收益检测
3. **行为闭环** - quality ≥ 7.0 自动转化为行为规则
4. **完整测试覆盖** - 320 个测试，所有已知 bug 已修复

**给 OpenCode 的核心建议**：

1. **先加知识状态层** — 最简单，立即有效（参考 `knowledge_graph.py`）
2. **话题分解 + 双 Provider 验证** — 提升搜索精准度（参考 `curiosity_decomposer.py`）
3. **元认知监控** — 让 Agent 能"感知"自己的知识缺口（参考 `meta_cognitive_monitor.py`）
4. **行为闭环** — 学到的知识转化为能力（参考 `agent_behavior_writer.py`）
5. **多 Agent 协调** — OMO 已具备基础，进一步增强共享好奇心层
6. **内在动机** — 长期目标，让 Agent 真正主动（参考 `intrinsic_scorer.py`）

每一步都有独立的用户价值，不需要一次性全部实现。建议按照"渐进式集成路径"逐步实施。

---

_文档版本：v2.0_
_更新时间：2026-03-23_
_参考实现：Curious Agent v0.2.3_
_测试状态：320 测试全部通过_