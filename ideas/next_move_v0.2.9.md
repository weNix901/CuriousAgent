# v0.2.9 — Agent 架构重构 + 知识结构化

> 规划时间：2026-04-08 | 更新：2026-04-11 22:47
> 版本目标：将 SpiderAgent/DreamAgent 重构为真正的 Agent（Nanobot 框架），同时建立结构化的知识表示
> 
> **版本历史**：
> - 2026-04-11 21:20：DreamAgent 重构为多周期循环架构（Light → Deep → REM）
> - 2026-04-11 22:47：**简化设计**：保留 L1-L3，移除 L4-L6（探索是 ExploreAgent 的工作）
> - **最终设计**：DreamAgent = 检索（发现缺口），ExploreAgent = 加工（探索写入）

---

## 1. 概述 & 版本目标

### 核心目标

让 Curious Agent 具备以下能力：

1. **Agent 架构重构** — ExploreAgent 和 DreamAgent 成为真正的 Agent（ReAct 循环、Tool 接口）
2. **知识结构化** — 统一知识节点数据模型，支持热度、状态、版本化
3. **外部集成** — R1D3 可以通过 Skill 接口消费 CA 的知识

### 架构选型

**最终选择：Nanobot 框架 + 自实现工程模块**

详见「2. 框架选型决策」

---

## 2. 框架选型决策

> **重要澄清（2026-04-11）**：Nanobot、Hermes Agent、OpenClaw 是**三个完全独立的项目**，由三个不同团队开发，只是在设计理念上有借鉴。

### 框架关系

| 项目 | 组织 | 语言 | 定位 | 关系 |
|------|------|------|------|------|
| **Nanobot** | HKUDS（香港大学数据科学实验室） | Python | 轻量 Agent 框架（~4000行） | 独立项目，"inspired by OpenClaw" |
| **Hermes Agent** | NousResearch | Python | 全功能 Agent 框架（~40000行） | 独立项目，Self-Evolution Loop |
| **OpenClaw** | openclaw（社区） | Node.js | 个人 AI 助手，多平台 | 独立项目 |

**三者之间没有代码关系**，只是在设计理念上互相借鉴（Agent Loop、Tool 系统、Memory 等）。

### 决策理由

1. CA 不需要 Session 存储（Agent 执行完就结束，无跨次记忆）
2. CA 不需要多平台（只被 R1D3 调用）
3. Hermes 的 error_classifier、retry_utils 代码质量高，直接复用
4. Nanobot 架构轻量，代码可读，适合做 CA Agent 基础
5. Nanobot 已有 HeartbeatService，DreamAgent 需要

### 框架对比

| 特性 | Hermes | Nanobot | Smolagents |
|------|--------|---------|------------|
| Heartbeat | ✅ cron | ✅ HeartbeatService | ❌ |
| Tool registry | ✅ 完整 | ✅ 简单够用 | ✅ |
| error_classifier | ✅ | ❌ | ❌ |
| retry_utils | ✅ | ❌ | ❌ |
| Session 存储 | ✅ | ❌ | ❌ |
| 多平台 | ✅ | ❌ | ❌ |
| 代码量 | ~40000行 | ~5000行 | ~3000行 |

### 从各框架借用的模块

| 模块 | 来源 | 方式 | 路径 |
|------|------|------|------|
| `error_classifier.py` | Hermes (NousResearch) | 复制 | `/root/dev/hermes-agent/agent/error_classifier.py` |
| `retry_utils.py` | Hermes (NousResearch) | 复制 | `/root/dev/hermes-agent/agent/retry_utils.py` |
| `HeartbeatService` | Nanobot (HKUDS) | 复制 | `/root/dev/nanobot/nanobot/heartbeat/service.py` |
| `AgentRunner` | Nanobot (HKUDS) | 参考重写 | `/root/dev/nanobot/nanobot/agent/runner.py` |
| `AgentHook` | Nanobot (HKUDS) | 参考重写 | `/root/dev/nanobot/nanobot/agent/hook.py` |
| `ToolRegistry` | Nanobot (HKUDS) | 参考重写 | `/root/dev/nanobot/nanobot/agent/tools/registry.py` |

**CA 自己实现的模块**：KG 存储（Neo4j）、Queue 存储（SQLite）、ExploreAgent、DreamAgent、Self-Evolution

---

## 2.1 Agent 架构：统一 CAAgent 框架

> **核心设计原则**：ExploreAgent 和 DreamAgent 是同一个 `CAAgent` 类的**不同配置实例**，代码逻辑统一，仅配置不同。三者（Nanobot、OpenClaw、Hermes）均为独立项目，无代码关系。

### 统一架构

```
┌─────────────────────────────────────────────────────────────┐
│                    CAAgent（统一 Agent 类）                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  nanobot AgentRunner（ReAct 执行引擎）               │  │
│  │  • 统一的 ReAct Loop                                │  │
│  │  • 统一的 Hook System                               │  │
│  │  • 统一的 hermes error_classifier                  │  │
│  └─────────────────────────────────────────────────────┘  │
│                           │                               │
│                           ▼                               │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  CA ToolRegistry（统一 Tool 接口）                   │  │
│  │  • KG Tools（Neo4j）                              │  │
│  │  • Queue Tools（SQLite）                          │  │
│  │  • Search Tools                                   │  │
│  │  • LLM Tools（volcengine）                        │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌──────────────────┐      ┌──────────────────┐
│  ExploreAgent    │      │   DreamAgent     │
│  (配置实例 A)     │      │   (配置实例 B)    │
│                  │      │                  │
│  • System Prompt │      │  • System Prompt │
│  • Tools 子集   │      │  • Tools 子集    │
│  • Daemon 模式  │      │  • Heartbeat 模式│
└──────────────────┘      └──────────────────┘
```

### CAAgent 统一实现

```python
# agents/ca_agent.py
from dataclasses import dataclass
from nanobot.agent.runner import AgentRunner, AgentRunSpec
from nanobot.agent.hook import AgentHook
from hermes.agent.error_classifier import ErrorClassifier

@dataclass
class CAAgentConfig:
    """Agent 配置：ExploreAgent 和 DreamAgent 的差异仅在于配置"""
    name: str
    system_prompt: str
    tools: list[str]
    max_iterations: int
    model: str = "doubao-pro-32k"
    hook_class: type[AgentHook] = None
    daemon_class: type = None

class CAAgent:
    """统一 Agent 类：ExploreAgent 和 DreamAgent 共用同一套代码"""

    def __init__(self, config: CAAgentConfig, llm_provider):
        self.config = config
        self.runner = AgentRunner(llm_provider)
        self.tools = ToolRegistry(config.tools)
        self.error_classifier = ErrorClassifier()

    async def run(self, input_data: dict) -> AgentResult:
        spec = AgentRunSpec(
            initial_messages=self._build_messages(input_data),
            tools=self.tools,
            model=self.config.model,
            max_iterations=self.config.max_iterations,
            hook=self._create_hook(),
        )
        return await self.runner.run(spec)

    def _build_messages(self, input_data: dict) -> list[dict]:
        return [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": str(input_data)},
        ]

    def _create_hook(self) -> AgentHook:
        return self.config.hook_class()
```

### ExploreAgent 配置

```python
# configs/agent_explore.py
EXPLORE_SYSTEM_PROMPT = """
You are an exploration agent specialized in discovering and verifying knowledge.

Your mission:
1. Search for authoritative information about the given topic
2. Analyze and synthesize findings from multiple sources
3. Identify related concepts, contradictions, and knowledge gaps
4. Write verified knowledge to the knowledge graph with proper citations

Key principles:
- Always verify claims against multiple sources
- Prefer primary sources (research papers, official documentation)
- Clearly distinguish between facts and speculation
- Update existing knowledge rather than creating duplicates
"""

explore_config = CAAgentConfig(
    name="ExploreAgent",
    system_prompt=EXPLORE_SYSTEM_PROMPT,
    tools=[
        "add_to_kg", "update_kg_status", "update_kg_metadata",
        "claim_queue", "mark_done", "mark_failed",
        "search_web", "fetch_page", "download_paper",
        "parse_pdf", "process_paper",
        "llm_analyze", "llm_summarize",
    ],
    max_iterations=10,
    hook_class=ExploreHook,
    daemon_class=ExploreDaemon,
)
```

### DreamAgent 配置

```python
# configs/agent_dream.py
DREAM_SYSTEM_PROMPT = """
You are a DreamAgent — a multi-cycle knowledge consolidation engine based on human sleep science.

## Core Mission
原料（记忆/Topic）是 ExplorationLog 和 KG 节点，
产品（知识）是结构化的 KG 节点和待探索 Queue。
DreamAgent 是加工厂，模仿人类睡眠的多周期循环。

## Architecture: Multi-Cycle Sleep

每 6 小时触发一次 = 模拟"一夜睡眠"
包含 3-4 个 Mini-Cycles，每个 Mini-Cycle 四层工序
每个 Mini-Cycle 处理一批候选（并行批处理）

## Mini-Cycle: 四层工序

### Layer 1: Light Sleep（摄入 + 候选筛选）
- 从 ExplorationLog 读取最近 7 天探索记录
- 从 KG 批量查询异常状态节点（DEPRECATED/DISPUTED/FROZEN/ORPHAN）
- Jaccard 去重（阈值 0.9）
- 输出候选列表（不写 KG）

### Layer 2: Deep Sleep（密集巩固 + 信号评分）
- 对候选并行计算 6 维信号：
  - Relevance(0.30), Frequency(0.24), Query Diversity(0.15)
  - Recency(0.15), Consolidation(0.10), Conceptual Richness(0.06)
- 应用相位强化 boost
- 截断 top 20 候选（不写 KG）

### Layer 3: Filtering（阈值门控筛选）
- 应用三重阈值门控：minScore≥0.8, minRecallCount≥3, minUniqueQueries≥3
- 只有通过所有门控的候选进入 Queue

### Layer 4: REM Sleep（整合 + 写入 Queue）
- 将合格候选生成 Queue topic
- DreamAgent 不写 KG，只生成 Queue topic
- **真正的「加工」是 ExploreAgent 的工作**

## Core Responsibilities
1. **Memory Consolidation**: ExplorationLog → KG 节点
2. **Knowledge Consolidation**: 更新 KG 关系、标记过时、归档冷门
3. **Link Consolidation**: 建立 KG 节点双向关系
4. **Knowledge Gap Detection**: 识别 KG 缺口，生成待探索 topic

## Candidate Priority (P0-P5)
- P0: Hot + DEPRECATED — 正在被用但已过时
- P1: Cold + VALID + High Citation — 频繁引用但长期不探索
- P2: DISPUTED — 存在矛盾
- P3: Frozen + VALID + High Citation — 曾被高引用但冻结
- P4: Orphan — 孤立节点
- P5: Missing Link — KG 中缺失的关系

## Key Principles
- Light/Deep: 只读不写 KG
- REM: 执行 KG 写入 + Queue 生成
- 多个 Mini-Cycles 累积 Consolidation 信号
- 不是所有记忆都值得成为知识 — 需要信号评分和阈值门控
"""

dream_config = CAAgentConfig(
    name="DreamAgent",
    system_prompt=DREAM_SYSTEM_PROMPT,
    tools=[
        # KG 查询
        "query_kg", "query_kg_by_status", "query_kg_by_heat",
        "get_node_relations",
        # KG 修改（REM Sleep 写入）
        "add_to_kg", "update_kg_status", "update_kg_metadata",
        "update_kg_relation", "merge_kg_nodes",
        # Memory 读取
        "read_exploration_log", "get_recent_memories",
        # Queue 操作
        "add_to_queue",
        # LLM 操作
        "llm_analyze", "llm_summarize",
    ],
    # DreamAgent 不使用 ReAct 循环，使用线性流水线 + 多周期
    num_minicycles=3,  # 每个大周期包含 3 个 Mini-Cycles
    batch_size=100,  # 每个 Mini-Cycle 处理 100 个候选
    hook_class=DreamHook,
    daemon_class=DreamDaemon,  # Heartbeat 6h 触发
)
```

### 关键特性对比

| 特性 | ExploreAgent | DreamAgent |
|------|-------------|------------|
| **设计目的** | 探索未知知识入 KG | 检索（发现知识缺口） |
| **输入** | Queue 中的 topic | 全 KG 扫描 + 最近 7 天 ExplorationLogs |
| **输出** | 探索结果写入 KG | Queue topic（让 ExploreAgent 去加工） |
| **核心职责** | 探索新知识 | 发现缺口 → 生成 Queue topic |
| **Tool 数量** | 14 个 | 15 个 |
| **执行模型** | ReAct 循环（LLM 驱动） | **多周期循环**：多个 Mini-Cycles，每个 L1 → L2 → L3 → L4 |
| **处理方式** | 单 topic 串行 | **并行批处理**：每个阶段并行处理本批次 |
| **Daemon 模式** | 连续运行 | Heartbeat（6h 触发一次全量周期） |
| **KG 写入权限** | ✅ 写 KG | ❌ 不写 KG，只写 Queue |

### DreamAgent 执行模型澄清

**架构决策**：DreamAgent 遵循人类睡眠科学，是**多周期循环架构**，不是线性流水线，也不是 ReAct 循环。

| 组件 | ExploreAgent | DreamAgent |
|------|-------------|------------|
| **执行入口** | `ExploreAgent.run(topic)` | `DreamAgent.run_full_dream_cycle()` |
| **大周期** | - | 6 小时一次（相当于"一夜睡眠"） |
| **Mini-Cycles** | - | 3-4 个 per 大周期，每个处理一批候选 |
| **每个 Mini-Cycle** | - | 四层工序：Light → Deep → Filtering → REM |
| **CAAgent 复用** | ToolRegistry + Hook + ErrorClassifier | ToolRegistry + Hook + ErrorClassifier |
| **ReAct 循环** | ✅ 使用（10次迭代） | ❌ 不使用 |
| **KG 写入** | ✅ 写 KG | ❌ 不写 KG，只写 Queue |

**为什么不用 ReAct**：
- 多周期批处理架构，有严格顺序依赖，LLM 不需要也不应该做执行决策
- 每个阶段算法确定，不需要 LLM 动态决定下一步
- 并行批处理效率远高于 ReAct 串行

**为什么不是单一线性**：
- 人类睡眠就是多周期，不是一次性线性
- 多个 Mini-Cycles 分批处理，内存可控，不阻塞主流程
- 跨周期累积 Consolidation 信号，避免一次判断错误

**如何集成 CAAgent 基础设施**：
```python
class DreamAgent:
    """DreamAgent 使用 CAAgent 的基础设施，但自己控制执行流程"""
    
    def __init__(self, config: CAAgentConfig, llm_provider, kg, queue):
        # 复用 CAAgent 的基础设施
        self.tools = ToolRegistry(config.tools)  # 统一 Tool 注册
        self.error_classifier = ErrorClassifier()  # 错误分类
        self.hook = DreamHook()  # CAAgent Hook 系统
        self.kg = kg
        self.queue = queue
        self.config = config
        self.scoring = DreamScoringEngine()
        self.gating = ThresholdGating()
        
        # 但自己控制执行流程，不走 ReAct 循环
    
    async def run_full_dream_cycle(self):
        """执行完整的多周期睡眠（相当于"一夜睡眠"）"""
        stats = {"total_candidates": 0, "promoted": 0, "linked": 0, "queued": 0, "archived": 0}
        
        for cycle_idx in range(self.config.num_minicycles):
            candidates = await self.light_sleep(cycle_idx)
            scored_candidates = await self.deep_sleep(candidates)
            cycle_stats = await self.rem_sleep(scored_candidates)
            for k in stats:
                stats[k] += cycle_stats[k]
        
        await self._write_dream_diary(stats)
        return stats
```

**DreamDaemon 调用方式**：
```python
class DreamDaemon(HeartbeatService):
    async def _execute_dream(self, prompt):
        # 执行完整的多周期睡眠（相当于"一夜睡眠"）
        await self.dream_agent.run_full_dream_cycle()
```

### Hook 实现差异

```python
# agents/hooks/explore_hook.py
class ExploreHook(AgentHook):
    """ExploreAgent Hook：管理探索输出"""

    async def after_iteration(self, context: AgentHookContext):
        if context.final_content:
            await self._log_exploration(
                tools_used=context.tool_calls,
                quality=context.usage,
            )

# agents/hooks/dream_hook.py
class DreamHook(AgentHook):
    """DreamAgent Hook：管理三阶段输出的持久化"""

    async def before_phase(self, phase: str):
        """Phase 开始前调用"""
        if phase == "light_sleep":
            await self._log_phase_start("Light Sleep")
        elif phase == "rem_sleep":
            await self._log_phase_start("REM Sleep")
        elif phase == "deep_sleep":
            await self._log_phase_start("Deep Sleep")

    async def after_phase(self, phase: str, result: dict):
        """Phase 结束后调用，记录输出"""
        if phase == "deep_sleep":
            # Deep Sleep 输出：KG 写入 + Queue 生成
            await self._persist_kg_writes(result.get("kg_operations", []))
            await self._persist_queue_writes(result.get("queue_topics", []))
            await self._log_dream_stats(result)

    async def _persist_kg_writes(self, operations: list):
        """Deep Sleep 的 KG 操作持久化"""
        for op in operations:
            if op["type"] == "promote":
                await self.kg.create_node(op["node"])
            elif op["type"] == "update_relation":
                await self.kg.add_relation(op["from"], op["to"], op["relation"])
            elif op["type"] == "mark_deprecated":
                await self.kg.update_status(op["node_id"], "DEPRECATED")
            elif op["type"] == "archive":
                await self.kg.update_status(op["node_id"], "ARCHIVED")

    async def _persist_queue_writes(self, topics: list):
        """Deep Sleep 的 Queue 操作持久化"""
        for topic in topics:
            await self.queue.add(
                topic["content"],
                priority=topic.get("priority", "MEDIUM"),
                source="dream",
                reason=topic.get("reason", ""),
            )

    async def _log_dream_stats(self, result: dict):
        """写入 Dream Diary"""
        stats = {
            "promoted": len(result.get("kg_operations", [])),
            "queued": len(result.get("queue_topics", [])),
            "archived": result.get("archived_count", 0),
        }
        await self._append_dream_report(stats)
```

### Daemon 实现差异

```python
# agents/daemons/explore_daemon.py
class ExploreDaemon:
    """ExploreAgent 守护进程：连续运行"""

    async def run(self):
        while True:
            item = await self.queue.claim(holder_id=self.name)
            if item:
                await self.agent.run({"topic": item.topic})
                await self.queue.mark_done(item.topic)
            else:
                await asyncio.sleep(1)

# agents/daemons/dream_daemon.py
class DreamDaemon(HeartbeatService):
    """DreamAgent 守护进程：心跳触发"""

    async def _execute_dream(self, tasks: str):
        candidates = await self.kg.query_by_heat_and_status(...)
        result = await self.agent.run({"candidates": candidates})
        topics = self._extract_topics(result.final_content)
        for topic in topics:
            await self.queue.add(topic, source="dream", priority=1)
```

---

## 2.2 Self-Evolution Loop（Hermes 启发）

### Hermes Self-Evolution 核心机制

Hermes 的 self-evolution 使用 **DSPy + GEPA**（Genetic-Pareto Prompt Evolution）自动优化：
- Skills 的 Prompt
- Tool 描述
- System Prompt

### CA 的 Self-Evolution：探索策略自适应

**Hermes 启发 CA 的核心思路**：从历史探索结果中学习，自动调整未来探索策略。

#### 进化维度

| 进化维度 |Hermes | CA 实现 |
|---------|-------|---------|
| Skill 优化 | DSPy 自动优化 Skill Prompt | **探索策略权重**（搜索词、来源偏好） |
| Tool 描述 | GEPA 优化 Tool 描述 | **Tool 调用模式**（search vs fetch vs paper） |
| System Prompt | Prompt Evolution | **探索深度配置**（max_iterations、timeout） |
| 质量反馈 | 用户评分 | **KG 质量评分**（heat、quality 变化） |

#### Self-Evolution 闭环

```
ExploreAgent 探索完成
    │
    ├── 记录探索结果 ──→ ExplorationLog
    │                      topic, tools_used, duration, quality_score
    │
    ├── 分析模式
    │   • 哪些 Tool 组合成功率高？
    │   • 哪些 topic 类型容易失败？
    │   • 探索深度和质量的权衡？
    │
    ├── 更新策略权重 ──→ StrategyWeights
    │   • search_web 成功率 × topic_type → 权重↑
    │   • fetch_page 超时率 → 权重↓
    │   • process_paper 质量 → 权重调整
    │
    └── 下次探索 ──→ 使用更新后的策略
```

#### 探索日志 Schema

```python
# kg/exploration_log.py
@dataclass
class ExplorationLog:
    topic: str
    topic_type: str          # tech / science / news / ...
    tools_used: list[str]   # ["search_web", "fetch_page", "add_to_kg"]
    duration_s: float
    quality_score: float    # 0.0 ~ 1.0（基于 KG 热度变化）
    success: bool
    error_reason: str | None
    strategy_version: str    # 当前策略版本
    created_at: datetime
```

#### 策略权重更新

```python
# agents/evolution.py
class ExplorationEvolution:
    """探索策略自进化引擎"""

    def __init__(self, kg):
        self.kg = kg

    async def record_and_evolve(self, log: ExplorationLog):
        """记录探索结果，更新策略"""
        # 1. 记录到 ExplorationLog
        await self._save_log(log)

        # 2. 贝叶斯更新权重
        await self._update_weights(log)

        # 3. 检测策略漂移
        await self._check_drift(log)

    async def _update_weights(self, log: ExplorationLog):
        """根据探索结果更新 Tool 权重"""
        for tool in log.tools_used:
            current = self._get_weight(tool, log.topic_type)

            # 成功 + 高质量 → 权重提升
            if log.success and log.quality_score > 0.7:
                new_weight = current + 0.1
            # 成功 + 低质量 → 权重下降
            elif log.success and log.quality_score < 0.3:
                new_weight = current - 0.05
            # 失败 → 权重下降
            else:
                new_weight = current - 0.15

            self._set_weight(tool, log.topic_type, new_weight)

    async def get_strategy(self, topic: str, topic_type: str) -> dict:
        """获取当前最优策略"""
        weights = self._get_weights_for_type(topic_type)
        return {
            "preferred_tools": sorted(weights.items(), key=lambda x: -x[1])[:3],
            "timeout_s": self._get_timeout(topic_type),
            "max_iterations": self._get_iterations(topic_type),
        }
```

#### R1D3 消费反馈（质量闭环）

```
R1D3 消费 KG 知识
    │
    ├── 查询 query_knowledge(topic)
    │   返回: {nodes, confidence, quality_score}
    │
    ├── R1D3 使用知识回答用户
    │
    └── 反馈质量 ──→ update_kg_metadata(heat↑, quality?)
                        │
                        └──→ ExplorationEvolution 记录
                                quality_score 变化
                                → 触发策略更新
```

#### 与 Hermes Self-Evolution 的区别

| 维度 | Hermes | CA |
|------|--------|-----|
| 进化对象 | Skills、Prompts、Tool 描述 | 探索策略（Tool 选择、深度配置） |
| 进化方法 | DSPy + GEPA | 贝叶斯权重更新 |
| 反馈来源 | 用户评分 | KG 热度/质量变化 |
| 进化频率 | 需要单独运行 | 每次探索后自动 |
| 目标 | 优化 LLM 输出质量 | 优化探索效率 |

### 与 Nanobot 原生的关键差异

| 维度 | Nanobot 原生 | CA 定制 |
|------|------------|---------|
| Session | 有（跨次记忆） | ❌ 无（CA 用 Neo4j KG） |
| Memory | 有（文件 I/O） | ❌ 无 |
| 多平台 | 支持 | ❌ 不支持（只服务 R1D3） |
| Tool 类型 | 通用工具 | CA 专用（KG/Queue/Search） |
| Agent 实例化 | 无 | ✅ 统一 CAAgent + 配置实例化 |
| 错误处理 | 简单重试 | Hermes error_classifier 分层 |
| Heartbeat | 可选 | DreamAgent 专用（6h 触发） |

---

## 3. 开发方式：选择性复制 + 参考重写

### 原则

**不直接引用外部框架**，复制需要的模块到 CA 项目，保证完全可控。

### 具体做法

| 模块 | 来源 | 方式 | 路径 |
|------|------|------|------|
| `error_classifier.py` | Hermes | 复制 | `/root/dev/hermes-agent/agent/error_classifier.py` |
| `retry_utils.py` | Hermes | 复制 | `/root/dev/hermes-agent/agent/retry_utils.py` |
| `heartbeat_service.py` | Nanobot | 复制 | `/root/dev/nanobot/nanobot/heartbeat/service.py` |
| `agent_runner.py` | Nanobot | 复制后修改 | `/root/dev/nanobot/nanobot/agent/runner.py` |
| `agent_hook.py` | Nanobot | 复制后修改 | `/root/dev/nanobot/nanobot/agent/hook.py` |
| `tool_registry.py` | Nanobot | 参考重写 | `/root/dev/nanobot/nanobot/agent/tools/registry.py` |

### 项目结构

```
/root/dev/curious-agent/
├── frameworks/                  # 从外部复制的模块
│   ├── error_classifier.py     # 从 Hermes 复制
│   ├── retry_utils.py          # 从 Hermes 复制
│   ├── heartbeat_service.py    # 从 Nanobot 复制
│   ├── agent_runner.py         # 从 Nanobot 复制后修改
│   ├── agent_hook.py           # 从 Nanobot 复制后修改
│   └── tool_registry.py        # 从 Nanobot 参考重写
│
├── agents/
│   ├── ca_agent.py            # 统一 Agent 类
│   ├── hooks/
│   │   ├── base.py           # AgentHook 基类
│   │   ├── explore_hook.py   # ExploreAgent Hook
│   │   └── dream_hook.py     # DreamAgent Hook
│   └── evolution.py            # Self-Evolution 引擎
│
├── configs/
│   ├── agent_explore.py       # ExploreAgent 配置
│   ├── agent_dream.py         # DreamAgent 配置
│   └── llm.yaml              # volcengine LLM 配置
│
├── tools/
│   ├── base.py                 # Tool 基类
│   ├── kg_tools.py             # 6 个 KG 操作 Tool
│   ├── queue_tools.py          # 5 个 Queue 操作 Tool
│   ├── search_tools.py         # 5 个搜索操作 Tool
│   └── llm_tools.py            # 2 个 LLM 操作 Tool（volcengine）
│
├── kg/
│   ├── neo4j_client.py          # Neo4j 操作封装
│   ├── exploration_log.py      # 探索日志存储
│   └── strategy_weights.py      # 策略权重存储
│
├── daemon/
│   ├── explore_daemon.py       # ExploreAgent 连续守护进程
│   └── dream_daemon.py         # DreamAgent 心跳守护进程
│
└── tests/                      # 测试框架
```

### 复制模块的维护

- 复制后**不跟踪上游**，除非有安全或功能问题
- 如需更新，手动同步（diff 后合并）
- CA 项目依赖这些模块，但这些模块**独立于外部框架**

---

## 4. 命名规范变更

### 核心更名：SpiderAgent → ExploreAgent

**原因**：SpiderAgent 名字带有「爬虫」意味，但它的核心职责是探索知识、填充 KG，是一个真正的 Agent（ReAct 循环 + 反思），不是简单的爬虫。「Explore」更能反映它的本质。

### 全部更名清单

| 类别 | 旧名称 | v0.2.9 新名称 |
|------|--------|--------------|
| Agent 名称 | `SpiderAgent` | `ExploreAgent` |
| 目录 | `agents/spider_agent.py` | `agents/explore_agent.py` |
| 配置 | `configs/agent_spider.yaml` | `configs/agent_explore.yaml` |
| Prompt | `prompts/spider_system_prompt.md` | `prompts/explore_system_prompt.md` |
| 测试 | `tests/test_spider_agent.py` | `tests/test_explore_agent.py` |

**DreamAgent 不更名**（名称已准确）

---

## 5. 知识模型

### 5.1 知识状态

| 状态 | 含义 |
|------|------|
| `VALID` | 有效知识，当前最准确版本 |
| `DEPRECATED` | 已过时，被新知识替代 |
| `DISPUTED` | 存在矛盾，需要验证 |
| `ARCHIVED` | 长期不消费但仍然有效 |

**版本化语义**：
- 不删除旧知识，只标记 `DEPRECATED`
- 保留历史版本，记录「谁替代了谁」关系 `superseded_by`

### 5.2 热度模型（Heat Dissipation）

**核心直觉**：被 R1D3 消费的知识会变热，热量自然消散，热度传导到邻居节点。

```
R1D3 消费节点 A:
  A.heat += ΔH_A
  A.last_accessed = now
  对 A 的每个邻居节点:
    neighbor.heat += ΔH_A × conduction_factor

每个时间步:
  所有节点.heat *= decay_factor
```

### 5.3 热度阈值语义

| 热度范围 | 语义 | 处理方式 |
|---------|------|---------|
| 🔥 `Heat > 0.8` | 正在高频消费 | 工作记忆，高优先级召回 |
| 🌡️ `0.3 < Heat ≤ 0.8` | 偶尔消费 | 正常召回范围 |
| ❄️ `0.0 < Heat ≤ 0.3` | 长期未消费 | 归档到长期记忆，不默认召回 |
| 💀 `Heat = 0` | 超过 N 天完全无消费 | 深度归档，仍永久保存 |

### 5.4 统一知识节点数据模型

```json
{
  "title": "Attention Mechanism",
  "content": "Attention 机制通过加权求和的方式让模型自动关注输入中最相关的部分...",
  "source_urls": ["https://arxiv.org/abs/1706.03762"],
  "relations": {
    "web_citation": ["Multi-Head Attention", "Transformer Architecture"],
    "derived_from": ["Deep Learning Architecture"],
    "cites": ["arXiv:1706.03762"],
    "related_to": ["Positional Encoding", "Layer Normalization"],
    "superseded_by": [],
    "supersedes": []
  },
  "status": "VALID",
  "metadata": {
    "created_at": "2026-04-08T07:02:38Z",
    "last_accessed": "2026-04-09T15:30:00Z",
    "heat": 0.92,
    "quality": 8.5,
    "confidence": 0.85
  }
}
```

---

## 6. Agent 模块

### 6.1 ExploreAgent

**职责**：从 web 探索知识，填充 KG

**架构**：参考 Nanobot AgentLoop

```python
class ExploreAgent:
    def __init__(self, tools, ...):
        self.tools = tools

    async def run_topic(self, topic: str):
        # 执行 topic 探索
        result = await self.agent_loop.run_conversation(topic)
        return result

class ExploreAgentDaemon:
    async def run(self):
        self._running = True
        while self._running:
            topic = queue.claim()
            if topic:
                await self.agent.run_topic(topic)
            else:
                await asyncio.sleep(1)

    def stop(self):
        self._running = False
```

### 6.2 DreamAgent

**核心定位**：基于生物学睡眠类比的**多周期循环知识巩固引擎**

**记忆 vs 知识区分**：
| 类型 | CA 存储位置 | 职责 |
|------|-----------|------|
| **Memory（记忆）** | `memory/curious/*.md` + `ExplorationLog` | 原始探索记录，时间索引，事件粒度 |
| **Knowledge（知识）** | Neo4j KG | 结构化概念，语义索引，事实粒度 |

**核心职责**：
1. **检索（发现缺口）** — 扫描 KG 异常节点，识别知识缺口
2. **Queue 生成** — 生成待探索 topic，让 ExploreAgent 去加工

**架构**：模仿人类睡眠科学
```
┌─────────────────────────────────────────────────────────┐
│         DreamAgentDaemon（每 6 小时触发一次 = 一夜睡眠）    │
└────────────┬──────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  Mini-Cycle 1: L1 → L2 → L3 → L4（Queue）  （一批候选）  │
└─────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  Mini-Cycle 2: L1 → L2 → L3 → L4（Queue）  （下一批）    │
└─────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  Mini-Cycle 3: L1 → L2 → L3 → L4（Queue）  （剩余）     │
└─────────────────────────────────────────────────────────┘
```

**输入**（每个大周期的输入）：
1. **KG 节点** — 批量查询状态异常和高引用节点
2. **ExplorationLog** — 最近 7 天的原始探索记录
3. **现有 Queue** — 去重已经 pending 的 topic
4. **配置** — 阈值、限额、phase 参数

**架构设计原则**：
- **DreamAgent = 检索（发现缺口）**：扫描 KG，生成 Queue topic
- **ExploreAgent = 加工（探索写入）**：接收 Queue，写入 KG
- **分工明确**：DreamAgent 不写 KG，只发现和生成；ExploreAgent 不发现，只执行和写入
- **并行批处理**：每个 phase 并行处理本批次所有候选
- **门控过滤**：不是所有候选都入 Queue，信号评分 + 阈值门控筛选
- **累积效应**：候选可以跨周期累积 Consolidation 信号

```python
class DreamAgent:
    """多周期循环检索引擎，基于人类睡眠架构"""
    
    def __init__(self, kg: KnowledgeGraph, queue: ExplorationQueue, config):
        self.kg = kg
        self.queue = queue
        self.config = config
        self.scoring = DreamScoringEngine()
        self.gating = ThresholdGating()

    async def run_full_dream_cycle(self):
        """执行一次完整的睡眠周期（相当于"一夜睡眠"）"""
        # 3-4 个 Mini-Cycles，每个处理一批候选
        stats = {"total_candidates": 0, "queued": 0}
        
        for cycle_idx in range(self.config.num_minicycles):
            # 每个 Mini-Cycle: L1 → L2 → L3 → L4(Queue)
            candidates = await self.light_sleep(cycle_idx)
            scored_candidates = await self.deep_sleep(candidates)
            filtered = await self.filtering(scored_candidates)
            cycle_stats = await self.rem_sleep_queue(filtered)
            
            # 累积统计
            for k in stats:
                stats[k] += cycle_stats[k]
        
        await self._write_dream_diary(stats)
        return stats
```

### 6.3 DreamAgent 总体架构：多周期循环 + 并行批处理

## 总体架构（基于人类睡眠科学）

### 核心洞察

人类睡眠不是一次性线性流程，而是**多周期循环**：
- 一个夜晚：4-6 个周期，每个周期 90-110 分钟
- 每个周期顺序：Light → Deep → REM
- 前半夜：更多深度睡眠（修复为主），后半夜：更多 REM（创意整合为主）

DreamAgent 遵循相同模式：

```
DreamAgentDaemon 每 6 小时触发一次（模拟"一夜睡眠"）
├── Input：KG 全部节点 + 最近 7 天 ExplorationLogs
├── 3-4 个 Mini-Cycles（模拟睡眠周期）
│   ├── 每个 Mini-Cycle：Light → Deep → REM
│   ├── 每个 Mini-Cycle 处理一批候选（并行处理）
│   └── 后续 Mini-Cycles 处理不同批次，结果可累积
└── Output：KG 巩固操作 + Queue 新 topic
```

### DreamAgent 输入

| 输入来源 | 内容 | 批量获取方式 |
|----------|------|------------|
| **KG 节点** | 现有知识图谱中的所有节点 | 按状态批量查询：
| | | - `WHERE status IN ['DEPRECATED', 'DISPUTED', 'FROZEN', 'ORPHAN']`
| | | - `WHERE heat > 0.8 AND last_accessed < 30 days`
| | | - `WHERE citation_count > 5 AND explored = false`
| | | 一次批量获取 N 个候选（N 默认 100） |
| **ExplorationLog** | 最近探索记录（原始记忆） | `WHERE created_at > 7 days ago` 批量获取 |
| **现有 Queue** | 当前 pending topic | 去重：已经在 Queue 的不再重复加入 |
| **配置参数** | 阈值、限额、phase 参数 | 从 config 读取 |

### 批量处理 KG 节点算法

**Neo4j 批量查询模式**：
```cypher
// 批量查询异常状态节点
MATCH (n:Knowledge)
WHERE n.status IN ['DEPRECATED', 'DISPUTED', 'FROZEN', 'ORPHAN']
   OR (n.heat > 0.8 AND n.last_accessed < timestamp() - 30*86400*1000)
RETURN n LIMIT 100;

// 每个 Mini-Cycle 只查询一批，多个 Cycles 覆盖更多节点
```

**并行处理**：
```python
# 每个 phase 并行处理 batch 中所有候选
async def process_batch(candidates):
    tasks = [process_candidate(c) for c in candidates]
    return await asyncio.gather(*tasks)
```

**优势**：
- 不阻塞主流程：每个周期只处理 100 个，多个周期逐步处理
- 可并行：多个候选同时计算信号评分
- 内存可控：不会一次性加载整个 KG

---

## Mini-Cycle 四层工序

**设计思想**：
- L1-L3：检索流程（发现知识缺口）
- L4（REM Sleep）：写入（生成 Queue topic）
- **真正的「加工」是 ExploreAgent 的工作**

**DreamAgent = 检索（发现缺口）**
**ExploreAgent = 加工（探索写入 KG）**

每个 Mini-Cycle 的四层工序：

---

### Layer 1: Light Sleep（摄入 + 候选筛选）

**目标**：从输入批量提取候选，预处理后暂存

**算法步骤**：
```
1. 批量读取最近 7 天的 ExplorationLog
2. 解析 ExplorationLog 为 memory chunks
   - chunk = {topic_id, content, created_at, search_queries, confidence}
3. Jaccard 去重（相似度阈值 0.9）
4. 批量 KG 查询：状态异常 + 高引用节点（见上表）
5. 合并两个来源，生成 candidate list
6. 写入 staging 暂存区（本周期专用）
7. 记录 Light Sleep 信号命中

约束：Light Sleep 不写 KG，只暂存
```

**KG 候选优先级**：
| 优先级 | 类型 | 信号组合 | 目标 |
|--------|------|---------|------|
| **P0** | 🔥 Hot + DEPRECATED | 正在被访问但状态已过时 | 需要重新探索 |
| **P1** | ❄️ Cold + VALID + High Citation | 频繁被引用但长期不探索 | 验证是否过时 |
| **P2** | DISPUTED | 多个来源结论矛盾 | 需要验证哪个正确 |
| **P3** | 💀 Frozen + VALID + High Citation | 曾被高引用，长期冻结 | 重新激活评估 |
| **P4** | Orphan | 没有入边的孤立节点 | 寻找相关节点建立链接 |
| **P5** | Missing Link | A → B 存在引用但 KG 没边 | 建立缺失关系 |

**输出**：`List[Candidate]`（本批次） → 传递给 L2

---

### Layer 2: Deep Sleep（密集巩固 + 信号评分）

**目标**：对本批次所有候选并行计算 6 维信号评分，生成综合得分

**参考来源**：OpenClaw Dreaming 评分体系（加权信号）

**6 维评分信号**：
| 信号 | 权重 | 计算方法 |
|------|------|---------|
| **Relevance** | 0.30 | 最近检索命中次数 / 总检索次数 |
| **Frequency** | 0.24 | 出现在探索日志中的次数（对数归一化） |
| **Query Diversity** | 0.15 | 检索到这个节点的不同 query 数量 |
| **Recency** | 0.15 | 时间衰减：`exp(-ln(2) * days / half_life)`，half_life = 14 天 |
| **Consolidation** | 0.10 | 连续多少个 Dream 周期出现在候选中 |
| **Conceptual Richness** | 0.06 | 概念标签密度：标签数量 / 内容长度 |

**相位强化 Boost**：
```
score = base_score
if 本周期 Light Sleep 命中: score += 0.05 * Recency
if 之前周期 REM Sleep 命中: score += 0.08 * Recency
```

**算法步骤**：
```
1. 对本批次 candidates 并行计算 6 个信号值
2. 计算 base_score = Σ(signal_i * weight_i)
3. 应用相位强化 boost
4. 对 candidates 按 score 降序排序
5. 截断：只保留 top K（K = 默认 20 / 每周期）
6. 记录 Deep Sleep 信号命中

约束：Deep Sleep 不写 KG，只评分
```

**输出**：`List[ScoredCandidate]`（本批次过滤后） → 传递给 L3

---

### Layer 3: Filtering（阈值门控筛选）

**目标**：应用阈值门控，只处理合格候选

**阈值门控**：候选必须通过所有三个门才能被处理

| 门 | 默认阈值 | 含义 |
|----|---------|------|
| **minScore** | 0.80 | 综合评分必须 ≥ 0.8 |
| **minRecallCount** | 3 | 至少被召回 3 次 |
| **minUniqueQueries** | 3 | 至少来自 3 个不同查询 |

**输出**：`List[FilteredCandidate]` → 传递给 L4（REM Sleep）

---

### Layer 4: REM Sleep（整合 + 写入 Queue）

**目标**：将合格候选生成探索 Queue topic

**人类对应功能**：REM 负责整合记忆、解决创造性问题

**核心输出**：生成 Queue topic，让 ExploreAgent 去「加工」

| 操作类型 | 触发条件 | 优先级 |
|----------|---------|--------|
| **Re-explore** | Hot + DEPRECATED / DISPUTED | HIGH |
| **Explore Gap** | Orphan / Missing Link | MEDIUM |
| **Verify Stale** | Cold + High Citation + 高过时概率 | MEDIUM |

**算法步骤**：
```
1. 对每个 FilteredCandidate 检查阈值门控
2. 未通过门控 → 跳过，等待下一个大周期
3. 通过门控 → 生成 Queue topic（不是直接写 KG）
4. 写入 Dream Diary 总结本周期
5. 返回操作统计：queued: N 个新 topic

约束：DreamAgent 只生成 Queue topic，不写 KG
```

**为什么 DreamAgent 不写 KG？**
- DreamAgent = 检索（发现缺口）
- ExploreAgent = 加工（探索 + 写入 KG）
- 分工明确：DreamAgent 负责发现问题，ExploreAgent 负责解决问题

---

## 多个 Mini-Cycles 的协调

### 顺序协调

```
Cycle 1: Light (100 candidates) → Deep → Filtering → REM (top 20) → 入 Queue
Cycle 2: Light (下一批 100 candidates) → Deep → Filtering → REM (top 20) → 入 Queue
Cycle 3: Light (剩余候选) → Deep → Filtering → REM → 入 Queue
```

### 累积效应

- 同一个候选可以出现在多个 Cycles
- 每次出现都会增加 Consolidation 信号（+0.10）
- 连续多个周期出现在候选 → 更容易通过阈值门控

### 夜间趋势模仿

| Cycle 序号 | Deep Sleep 限额 | REM 限额 | 原因 |
|------------|----------------|----------|------|
| Cycle 1 | 50 | 20 | 前周期：更多深度处理 |
| Cycle 2 | 30 | 20 |  |
| Cycle 3 | 20 | 15 | 后周期：更多整合 |
| Cycle 4 | 10 | 10 |  |

模仿人类"前半夜深睡多，后半夜 REM 多"的趋势

---

### 6.4 DreamAgent Tool 配置

DreamAgent = 检索（发现缺口），不需要写 KG，只读和生成 Queue：

```yaml
# DreamAgent
tools:
  # KG 查询（用于扫描异常节点）
  - query_kg
  - query_kg_by_status
  - query_kg_by_heat
  - get_node_relations
  
  # Memory 读取（用于扫描 ExplorationLog）
  - read_exploration_log
  - get_recent_memories
  
  # Queue 操作（生成待探索 topic）
  - add_to_queue
```

**注意**：DreamAgent 不需要写 KG 工具，因为 KG 写入是 ExploreAgent 的工作。

### 6.5 算法复杂度

| 四层工序 | 复杂度 | 说明 |
|----------|--------|------|
| **L1: Light Sleep** | O(N) | N = 最近探索日志数量 + KG 异常节点数量，批量查询 |
| **L2: Deep Sleep** | O(C × 6) | C = 候选数量（默认 ≤ 100），并行计算 6 维信号 |
| **L3: Filtering** | O(C) | C = 候选数量，阈值门控检查 |
| **L4: REM Sleep** | O(P) | P = 通过门控的候选数量（默认 ≤ 20），Queue 生成 |

**多周期总复杂度**：`O(num_minicycles × (N + C×6 + P))`，由于是批处理且截断 top 20，实际复杂度很低

**总复杂度**：极低，适合后台定时运行，不会阻塞主探索流程

---

## 7. Tool 模块

### 7.1 统一 TOOL_REGISTRY

所有 Agent 共享同一套 Tool，Agent 配置只声明「能用什么 Tool」。

```python
TOOL_REGISTRY = {
    # KG 操作
    "query_kg": QueryKGTool(),
    "query_kg_by_status": QueryKGByStatusTool(),
    "query_kg_by_heat": QueryKGByHeatTool(),
    "get_node_relations": GetNodeRelationsTool(),
    "add_to_kg": AddToKGTool(),
    "update_kg_status": UpdateKGStatusTool(),
    "update_kg_metadata": UpdateKGMetadataTool(),
    "update_kg_relation": UpdateKGRelationTool(),
    "merge_kg_nodes": MergeKGNodesTool(),

    # Queue 操作
    "add_to_queue": AddToQueueTool(),
    "claim_queue": ClaimQueueTool(),
    "get_queue": GetQueueTool(),
    "mark_done": MarkQueueDoneTool(),
    "mark_failed": MarkQueueFailedTool(),

    # Memory / ExplorationLog 操作
    "read_exploration_log": ReadExplorationLogTool(),
    "get_recent_memories": GetRecentMemoriesTool(),

    # 搜索操作
    "search_web": SearchWebTool(),
    "fetch_page": FetchPageTool(),
    "download_paper": DownloadPaperTool(),
    "parse_pdf": ParsePDFTool(),
    "process_paper": ProcessPaperTool(),  # 快捷封装: download + parse

    # LLM 操作
    "llm_analyze": LLMAnalyzeTool(),
    "llm_summarize": LLMSummarizeTool(),
}
```

### 7.2 Agent Tool 配置

```yaml
# ExploreAgent
name: ExploreAgent
tools:
  - search_web
  - fetch_page
  - add_to_kg
  - update_kg_status
  - update_kg_metadata
  - add_to_queue
  - claim_queue
  - mark_done
  - mark_failed

# DreamAgent
name: DreamAgent
tools:
  # KG 查询
  - query_kg
  - query_kg_by_status
  - query_kg_by_heat
  - get_node_relations
  
  # KG 修改
  - add_to_kg
  - update_kg_status
  - update_kg_metadata
  - update_kg_relation
  - merge_kg_nodes
  
  # Memory 操作
  - read_exploration_log
  - get_recent_memories
  
  # Queue 操作
  - add_to_queue
  
  # LLM 操作
  - llm_analyze
  - llm_summarize
```

### 7.3 Tool 逐一设计（inputs/outputs）

**Q12 设计决策结论**（2026-04-11）：

| # | 问题 | 结论 |
|---|------|------|
| Q12-1 | status + heat 是否合并？ | ❌ 不合并，增加 `update_kg_metadata` |
| Q12-2 | claim_queue 模式？ | ✅ **Atomic claim** + holder_id + timeout |
| Q12-3 | download + parse 是否合并？ | ❌ 分开，加 `process_paper` 快捷封装 |
| Q12-4 | LLM Provider？ | ✅ **volcengine**（weNix 已配置） |

#### KG 类 Tool

| Tool | inputs | outputs | 说明 |
|------|--------|---------|------|
| `query_kg` | `topic: str`, `limit: int=5` | `{nodes: list, confidence: str}` | 查询相关知识，返回 confidence: high/medium/low |
| `query_kg_by_status` | `status: str` | `{nodes: list}` | 按状态筛选：VALID/DEPRECATED/DISPUTED/ARCHIVED |
| `query_kg_by_heat` | `min_heat: float=0.0`, `max_heat: float=1.0` | `{nodes: list}` | 按热度范围筛选 |
| `add_to_kg` | `topic: str`, `content: str`, `source_urls: list`, `relations: dict` | `{success: bool, node_id: str}` | 添加知识节点，relations 含 derived_from/cites/related_to/supersedes/superseded_by |
| `update_kg_status` | `topic: str`, `status: str` | `{success: bool}` | 状态流转：VALID→DEPRECATED→ARCHIVED |
| `update_kg_metadata` | `topic: str`, `heat: float?`, `quality: float?`, `confidence: float?` | `{success: bool}` | 指标更新（heat/quality/confidence 独立更新） |

#### Queue 类 Tool

| Tool | inputs | outputs | 说明 |
|------|--------|---------|------|
| `add_to_queue` | `topic: str`, `source: str="manual"`, `priority: int=0` | `{success: bool, queue_size: int}` | 添加 topic 到队列，priority 越大优先级越高 |
| `claim_queue` | `holder_id: str`, `timeout_s: int=300` | `{topic: str or null}` | **Atomic claim**：返回 topic 并锁定，holder_id 标识持有者，超时自动释放 |
| `get_queue` | `limit: int=10` | `{items: list, total: int}` | 查看队列当前状态（不 claim） |
| `mark_done` | `topic: str` | `{success: bool}` | 标记 topic 探索完成，释放 claim |
| `mark_failed` | `topic: str`, `reason: str` | `{success: bool}` | 标记探索失败，释放 claim，记录错误原因 |

#### Search 类 Tool

| Tool | inputs | outputs | 说明 |
|------|--------|---------|------|
| `search_web` | `query: str`, `count: int=5`, `provider: str` | `{results: list, provider: str}` | 搜索，返回 title/url/snippet |
| `fetch_page` | `url: str`, `max_chars: int=5000` | `{content: str, title: str}` | 抓取页面内容 |
| `download_paper` | `url: str`, `save_dir: str` | `{success: bool, file_path: str}` | 下载 PDF 到本地 |
| `parse_pdf` | `file_path: str`, `pages: str?=null` | `{text: str, page_count: int}` | 解析 PDF 为文本，pages 为 "1-5" 或 "1,3,5" |
| `process_paper` | `url: str`, `save_dir: str`, `pages: str?=null` | `{text: str, file_path: str}` | 快捷封装：download_paper + parse_pdf 串联 |

#### LLM 类 Tool（Provider: volcengine）

| Tool | inputs | outputs | 说明 |
|------|--------|---------|------|
| `llm_analyze` | `prompt: str`, `context: str` | `{analysis: str, confidence: float}` | LLM 分析，返回分析结果和置信度 |
| `llm_summarize` | `text: str`, `max_length: int=500` | `{summary: str}` | LLM 摘要 |

#### Tool 基类定义

```python
class BaseTool:
    name: str           # 注册名，LLM 可见
    description: str    # 描述，LLM 决策用

    def forward(self, **kwargs) -> dict:
        raise NotImplementedError

    @property
    def input_schema(self) -> dict:
        """JSON Schema for inputs, used for LLM tool calling"""
        raise NotImplementedError
```

---

## 8. Q 问题清单及结论

| # | 问题 | 严重性 | 状态 | 结论 |
|---|------|--------|------|------|
| Q1 | API Gateway 定义 | 高 | ✅ | API Key + FastAPI + per-agent 配额 |
| Q2 | Queue 存储选型 | 高 | ✅ | SQLite |
| Q3 | DreamAgent 三阶段 | 高 | ✅ | 热+状态模型 |
| Q4 | Hub 节点 content | 中 | ✅ | 论文 vs 网页 + 结构化摘要 |
| Q5 | KG 查询能力 | 中 | ✅ | Q5a(外部) + Q5b(Tool) |
| Q6 | 配置方式 | 中 | ✅ | Python 配置 |
| Q7 | 错误处理 | 中 | ✅ | 程序层+LLM层分层 |
| Q8 | 生命周期 | 中 | ✅ | Nanobot AgentLoop |
| Q9 | Hook 集成机制 | 高 | ✅ | Skill + Hook 配合架构 |
| Q10 | System Prompt | 低 | ✅ | Monaco Editor |
| Q11 | 测试策略 | 中 | ✅ | 覆盖率 90%+，真实接口 |
| Q12 | Tool 逐一设计 | 高 | ✅ | inputs/outputs/forward + Q12-1~4 结论 |

### Q7：错误处理（已确认）

**设计原则**：Tool 保持原子性，重试决策在 Agent ReAct 层

**需要重试的错误**：
| 错误类型 | 来源 | 处理 |
|---------|------|------|
| Rate limit (429) | LLM/搜索 API | 等一下再试 |
| Timeout | LLM/搜索 API/Web | 重试一次 |
| Connection reset | Web Fetch | 重试一次 |

**不需要重试的错误**：
| 错误类型 | 来源 | 处理 |
|---------|------|------|
| 401/403 | API key 错误 | 直接放弃 |
| 402 | 账户欠费 | 直接放弃 |
| 404 | 资源不存在 | 直接放弃 |

### Q8：生命周期管理（已确认）

**参考**：Nanobot AgentLoop + HeartbeatService

**设计**：
- ExploreAgentDaemon：参考 AgentLoop，连续运行
- DreamAgentDaemon：参考 HeartbeatService，6 小时触发一次

---

### Q1：API Gateway（已确认）

**确认内容**：
- 认证：API Key（5 个消费者各自独立 key）
- 协议：OpenClaw Skill（主）+ REST API（辅助）
- 限流：per-agent 配额（逻辑实现，配额暂不设置）

#### 两种注册模式

**模式一：手动注册（管理员操作）**

```
消费者联系 weNix
    ↓
weNix 在 WebUI 生成 Key（输入消费者名称）
    ↓
weNix 把 Key 给消费者
    ↓
消费者配置到 openclaw.json
```

**模式二：自动注册（推荐）**

```
外部 agent 安装 Skill
    ↓
调用 CA 注册接口：POST /api/auth/register
    body: {"agent_name": "agent_r1d3"}
    ↓
CA 后台生成 API Key，存入 SQLite
    ↓
返回 {"api_key": "ca_key_xxx"}
    ↓
外部 agent 收到 Key，自动写入 Skill 配置
    ↓
CA 后台记录 agent 和 Key 的对应关系
```

**API Key 存储（SQLite）**：

```sql
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,        -- ca_key_xxx
    consumer TEXT NOT NULL,           -- agent_r1d3
    created_at TIMESTAMP DEFAULT NOW,
    enabled BOOLEAN DEFAULT TRUE
);
```

**注册接口**：

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/auth/register` | POST | agent 自动注册，获取 API Key |
| `/api/auth/keys` | GET | 管理员查看所有 Key |
| `/api/auth/keys/{consumer}` | DELETE | 管理员删除 Key |

**WebUI 功能**：

| 功能 | 说明 |
|------|------|
| API Key 生成 | 自动/手动生成 Key |
| Key 列表 | 显示所有 Key 和消费者 |
| Key 删除 | 撤销某个消费者的访问 |

---

### Q1.5：CA REST API 完整设计

#### 架构

```
Skill / Hook
    │
    └──→ CA REST API → CA 内部系统（KG/Queue/Explore/Dream）
```

**Skill 和 Hook 都是 CA API 的调用方**，内部都通过 REST API 和 CA 通信。

#### KG 操作 API

| API | 方法 | 用途 | 调用方 |
|-----|------|------|--------|
| `/api/kg/query` | POST | 查询相关知识 | Skill, Hook |
| `/api/kg/add` | POST | 添加知识 | Skill, Hook |
| `/api/kg/update-status` | POST | 更新状态（body: `{topic, status}`） | ExploreAgent |
| `/api/kg/exists` | POST | 检查 topic 是否存在 | Skill, Hook |

#### 探索操作 API

| API | 方法 | 用途 | 调用方 |
|-----|------|------|--------|
| `/api/metacognitive/check` | POST | 检查置信度 | Skill, Hook |
| `/api/curious/inject` | POST | 触发探索 | Skill, Hook |
| `/api/curious/state` | GET | 探索状态 | Skill |

#### Queue 操作 API

| API | 方法 | 用途 | 调用方 |
|-----|------|------|--------|
| `/api/queue/add` | POST | 添加 topic | Skill, Hook |
| `/api/queue/status` | GET | 队列状态（pending/done/total） | Skill |
| `/api/queue/contains` | POST | 检查 topic 是否在队列 | Skill, Hook |
| `/api/queue/claim` | POST | Atomic claim（body: `{holder_id, timeout_s}`） | ExploreAgentDaemon |
| `/api/queue/done` | POST | 标记完成（body: `{topic}`） | ExploreAgent |
| `/api/queue/failed` | POST | 标记失败（body: `{topic, reason}`） | ExploreAgent |

#### 发现操作 API

| API | 方法 | 用途 | 调用方 |
|-----|------|------|--------|
| `/api/discoveries` | GET | 获取发现列表 | Skill, Hook |
| `/api/discoveries/{id}/share` | POST | 标记已分享 | Skill |

#### 认证操作 API

| API | 方法 | 用途 | 调用方 |
|-----|------|------|--------|
| `/api/auth/register` | POST | 注册 consumer | Skill |
| `/api/auth/keys` | GET | 查看 key | (Admin) |
| `/api/auth/keys/{consumer}` | DELETE | 删除 key | (Admin) |

#### KG 元数据/状态 API

| API | 方法 | 用途 | 调用方 |
|-----|------|------|--------|
| `/api/kg/update-metadata` | POST | 更新指标（body: `{topic, heat?, quality?, confidence?}`） | Hook |
| `/api/kg/stats` | GET | KG 统计（节点数、平均热度等） | Skill |

#### 管理操作 API

| API | 方法 | 用途 | 调用方 |
|-----|------|------|--------|
| `/api/state` | GET | CA 状态 | Hook |
| `/api/stats` | GET | 整体统计 | Skill |

#### Skill → API 映射

| Skill | CA API | 说明 |
|-------|--------|------|
| `check_confidence.sh` | `POST /api/metacognitive/check` | 检查 topic 置信度 |
| `trigger_explore.sh` | `POST /api/curious/inject` | 触发探索 |
| `sync_discoveries.py` | `GET /api/discoveries` | 同步发现列表 |
| `share_new_discoveries.py` | `GET /api/discoveries?shared=false` | 获取未分享发现 |
| `query_knowledge.sh` | `POST /api/kg/query` | 查询知识 |
| `add_web_knowledge.sh` | `POST /api/kg/add` | R1D3 web_search 结果入 KG |

#### Hook → API 映射

| Hook | CA API | 说明 |
|------|---------|------|
| `gateway:startup` | `GET /api/state` | 检查 CA 状态 |
| `gateway:startup` | `GET /api/discoveries?shared=false` | 检查未分享发现 |
| `message:received` | `POST /api/kg/add` | 提取知识点入 KG |
| `message:received` | `POST /api/curious/inject` | 隐式探索意图 |
| `message:preprocessed` | `POST /api/kg/query` | 注入相关知识 |
| `message:preprocessed` | `POST /api/metacognitive/check` | 检查置信度 |
| `message:sent` | `POST /api/kg/add` | 提取 R1D3 回答中的知识 |
| `message:sent` | `POST /api/kg/update-metadata` | 更新知识热度 |
| `session:compact:after` | `POST /api/kg/add` | 会话摘要知识入 KG |
| `session:compact:after` | `POST /api/curious/inject` | 发现新 topic |

---

### Q9：CA + R1D3 Hook 集成机制（已确认）

#### CA 的五大核心能力

| # | 能力 | 性质 |
|---|------|------|
| 1 | 主动探索未知知识 | 主动 |
| 2 | 积累和管理知识 | 被动/主动 |
| 3 | 置信度感知（知道自己不知道什么） | 被动 |
| 4 | 主动分享新发现 | 主动 |
| 5 | R1D3 的后台知识库 | 被动 |

#### Skill vs Hook 的本质区别

| 维度 | Skill | Hook |
|------|-------|------|
| **触发方式** | R1D3 主动调用 | 事件自动触发 |
| **控制权** | R1D3 决定何时用 | OpenClaw 控制 |
| **用途** | 查询、触发、分享 | 自动化、知识积累 |
| **典型场景** | "帮我查一下这个topic" | 自动积累对话中的知识 |

#### Skill 和 Hook 配合设计

**原则**：
1. **Skill 处理「主动决策」** - R1D3 需要主动决定的行为
2. **Hook 处理「自动化后台」** - 不需要 R1D3 主动触发

#### 采纳的 Hook 列表

| Hook | 采纳？ | 服务的能力 |
|------|--------|-----------|
| `message:preprocessed` | ✅ 核心 | #3 置信度感知、#5 知识库 |
| `message:received` | ✅ 核心 | #1 探索、#2 积累、#3 置信度 |
| `message:sent` | ✅ 核心 | #2 积累、#3 置信度、#5 知识库 |
| `gateway:startup` | ✅ 必须 | 全部 |
| `session:compact:after` | ✅ 辅助 | #1 探索、#2 积累 |
| `session:compact:before` | ❌ 不做 | 价值低 |
| `agent:bootstrap` | ❌ 不做 | 重复 |

#### Skill 和 Hook 功能映射

| 能力 | Skill | Hook |
|------|-------|------|
| #1 主动探索 | `trigger_explore` | `message:received`（自动发现） |
| #2 积累知识 | （未来扩展） | `message:received/sent/compact` |
| #3 置信度感知 | `check_confidence` | `message:preprocessed`（自动检查+注入） |
| #4 主动分享 | `share_new_discoveries` | `gateway:startup` |
| #5 知识库 | `query_knowledge` | `message:preprocessed`（预加载） |

#### 完整配合架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      R1D3                                        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Skill 接口（主动调用）                                    │   │
│  │                                                           │   │
│  │  check_confidence.sh   ←── 置信度检查                    │   │
│  │  trigger_explore.sh    ←── 明确探索意图                  │   │
│  │  query_knowledge.sh    ←── 知识查询                      │   │
│  │  sync_discoveries.py   ←── 发现同步                      │   │
│  │  share_new_discoveries.py ← 分享新发现                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      OpenClaw Gateway                            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Hook 拦截（自动触发）                                    │   │
│  │                                                           │   │
│  │  gateway:startup                                         │   │
│  │      │ → 初始化 CA daemon                                │   │
│  │      │ → 检查并分享新发现                                 │   │
│  │      ▼                                                   │   │
│  │  message:received ──────────────────────────────────┐   │   │
│  │      │ → 提取知识点入 KG                         │   │   │
│  │      │ → 检测探索意图                          │   │   │
│  │      ▼                                          │   │   │   │
│  │  message:preprocessed ──────────────────────┐   │   │   │   │
│  │      │                                 │   │   │   │   │   │
│  │      ▼                                 ▼   │   │   │   │   │
│  │  message:sent ─────────────────────┐    │   │   │   │   │   │
│  │      │                            │    │   │   │   │   │   │
│  │      ▼                            ▼    ▼   │   │   │   │   │
│  │  session:compact:after            │    │   │   │   │   │   │
│  │      │                            │    │   │   │   │   │   │
│  └──────┼────────────────────────────┼────┼───┼───┼───┼───┘   │
│         │                            │    │   │   │   │         │
└─────────┼────────────────────────────┼────┼───┼───┼───┼─────────┘
          │                            │    │   │   │   │
          ▼                            ▼    │   │   │   │
┌─────────────────────────────────────────┼────┴───┴───┼───┐
│                      CA System                   │   │
│                                                   │   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐          │   │
│  │ KG      │  │ Queue   │  │Explore  │◀─────────┘   │
│  │(Neo4j)  │  │(SQLite) │  │Agent    │              │
│  └─────────┘  └─────────┘  └─────────┘              │
│      ▲                                              │
│      │ 能力 #2: 知识积累                            │
│      │ 能力 #3: 置信度感知                          │
│      │ 能力 #4: 主动分享                            │
│      │ 能力 #5: 知识库                              │
└──────────────────────────────────────────────────────┘
```

#### 各 Hook 详细说明

**gateway:startup**：
- 初始化 CA daemon
- 检查并分享新发现

**message:received**：
- 提取用户输入中的知识点 → 入 KG
- 检测探索意图 → 触发 ExploreAgent

**message:preprocessed**：
- 自动检查置信度 → 置信度低则标记
- 自动注入相关知识到 bodyForAgent

**message:sent**：
- 提取 R1D3 响应中的知识 → 入 KG
- 追踪知识使用 → 更新热度

**session:compact:after**：
- 从压缩摘要中提取知识 → 入 KG
- 发现新探索 topic → 入 Queue

---

### Q11：测试策略（已确认）

**目标**：覆盖率 90%+，涵盖 UT、集成、E2E

**决策结论**（2026-04-11）：
| 决策 | 结论 |
|------|------|
| 测试 DB 管理 | ✅ 共用测试 Neo4j instance（测试前后清理数据） |
| API 调用 | ✅ 真实调用（不做 VCR 录制） |
| 网络错误模拟 | ❌ 不做（真实调用下无意义） |

**测试分层**：

| 层级 | 内容 | 工具 |
|------|------|------|
| **单元测试 (UT)** | Tool 函数、KG 操作、Queue 操作 | pytest |
| **集成测试 (IT)** | Agent + Tool 串联 | pytest + 真实接口 |
| **E2E 测试** | 完整探索流程 | script（手动或 CI 触发） |

**覆盖目标**：
| 模块 | 目标 | 说明 |
|------|------|------|
| Tool 函数 | 100% | 每个 Tool 必须有 UT |
| KG/Queue 操作层 | 95%+ | 核心存储层 |
| Agent 核心流程 | 90%+ | ReAct 循环 |
| 总覆盖率 | 90%+ | 加权平均 |

#### 测试目录结构

```
tests/
├── __init__.py
├── conftest.py              # 全局 fixtures
├── unit/
│   ├── __init__.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── test_query_kg.py
│   │   ├── test_add_to_kg.py
│   │   ├── test_update_kg_status.py
│   │   ├── test_update_kg_metadata.py
│   │   ├── test_query_kg_by_status.py
│   │   ├── test_query_kg_by_heat.py
│   │   ├── test_add_to_queue.py
│   │   ├── test_claim_queue.py
│   │   ├── test_get_queue.py
│   │   ├── test_mark_done.py
│   │   ├── test_mark_failed.py
│   │   ├── test_search_web.py
│   │   ├── test_fetch_page.py
│   │   ├── test_download_paper.py
│   │   ├── test_parse_pdf.py
│   │   ├── test_process_paper.py
│   │   ├── test_llm_analyze.py
│   │   └── test_llm_summarize.py
│   ├── kg/
│   │   ├── __init__.py
│   │   ├── test_kg_node_crud.py
│   │   ├── test_kg_relations.py
│   │   ├── test_kg_heat_model.py
│   │   └── test_kg_status_transitions.py
│   └── queue/
│       ├── __init__.py
│       ├── test_queue_crud.py
│       ├── test_queue_claim_atomic.py
│       └── test_queue_timeout.py
├── integration/
│   ├── __init__.py
│   ├── test_explore_agent.py
│   ├── test_dream_agent.py
│   └── test_daemon_lifecycle.py
└── e2e/
    ├── __init__.py
    ├── test_full_exploration.py
    └── test_dream_to_explore_pipeline.py
```

#### conftest.py 全局 fixtures

```python
# tests/conftest.py
import pytest
import os

# 测试用环境变量（覆盖 .env）
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_DATABASE"] = "ca_test"  # 独立 DB
os.environ["CA_API_KEY"] = "test_key_xxx"

@pytest.fixture(scope="session")
def neo4j_driver():
    """Session 级 Neo4j driver，所有测试共用一个 connection"""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=("neo4j", os.environ.get("NEO4J_PASSWORD", "neo4j"))
    )
    yield driver
    driver.close()

@pytest.fixture(scope="function")
def clean_kg(neo4j_driver):
    """每个测试函数前后清理 KG 数据"""
    with neo4j_driver.session(database="ca_test") as session:
        session.run("MATCH (n) DETACH DELETE n")
        session.run("MATCH (q:QueueItem) DETACH DELETE q")
    yield
    with neo4j_driver.session(database="ca_test") as session:
        session.run("MATCH (n) DETACH DELETE n")
        session.run("MATCH (q:QueueItem) DETACH DELETE q")

@pytest.fixture(scope="function")
def sqlite_queue(tmp_path):
    """每个测试函数用独立的 SQLite 文件"""
    db_path = tmp_path / "test_queue.db"
    yield str(db_path)
```

#### Tool UT 示例

```python
# tests/unit/tools/test_query_kg.py
import pytest
from ca.tools.kg_tools import QueryKGTool

class TestQueryKGTool:
    @pytest.fixture
    def tool(self):
        return QueryKGTool()

    def test_query_kg_returns_nodes(self, tool, clean_kg):
        # 先添加一个节点
        add_tool = AddToKGTool()
        add_tool.forward(
            topic="Attention Mechanism",
            content="...",
            source_urls=["https://arxiv.org/abs/1706.03762"],
            relations={}
        )

        # 查询
        result = tool.forward(topic="Attention Mechanism", limit=5)

        assert "nodes" in result
        assert "confidence" in result
        assert result["confidence"] in ["high", "medium", "low"]

    def test_query_kg_nonexistent_returns_empty(self, tool, clean_kg):
        result = tool.forward(topic="NonExistentTopicXYZ", limit=5)
        assert result["nodes"] == []
        assert result["confidence"] == "low"
```

#### 覆盖率配置

```ini
# pytest.ini / pyproject.toml
[tool.coverage.run]
source = ["ca"]
omit = ["ca/frameworks/*", "tests/*", "**/__pycache__/*"]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.",
]

[tool.coverage.html]
directory = "htmlcov"
```

#### CI/CD 配置

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5.12
        env:
          NEO4J_AUTH: neo4j/neo4j
          NEO4J_PLUGINS: '["apoc"]'
        ports:
          - 7687:7687
          - 7474:7474
        options: -e NEO4J_dbms_memory_heap_max=512m

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Create test database
        run: cypher-shell -u neo4j -p neo4j "CREATE DATABASE ca_test;"

      - name: Install dependencies
        run: pip install pytest pytest-cov pytest-asyncio

      - name: Run unit + integration tests
        env:
          NEO4J_URI: bolt://localhost:7687
          NEO4J_PASSWORD: neo4j
          NEO4J_DATABASE: ca_test
        run: |
          pytest tests/unit/ tests/integration/ \
            --cov=ca \
            --cov-report=xml \
            --cov-fail-under=90

  e2e:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/')
    steps:
      - uses: actions/checkout@v4
      - name: Run E2E tests
        run: bash tests/e2e/run.sh
```

#### E2E 测试脚本

```bash
#!/bin/bash
# tests/e2e/run.sh
set -e

# 启动测试 Neo4j（如果用 Docker）
docker run -d --name ca-e2e-neo4j -p 7687:7687 neo4j:5.12

# 等待 Neo4j 就绪
sleep 10

# 执行探索
python -m ca.scripts.run_exploration --topic "Transformer Architecture"

# 验证结果
python -m ca.scripts.verify_kg "Transformer Architecture"

# 清理
docker stop ca-e2e-neo4j && docker rm ca-e2e-neo4j
```

---

## 能力 #1：主动探索未知知识（详细设计）

### 核心流程

```
用户消息 → R1D3
    ↓
R1D3 调用 CA: check_confidence(topic)
    ↓
CA 返回置信度分数
    ↓
┌─────────────────────────────────────────┐
│ 置信度高 → 直接用 CA 知识回答            │
│ 置信度低 →                             │
│   1. 先诚实回答（LLM 内化知识）          │
│   2. 触发 CA 后台探索                   │
│   3. 探索结果后续同步                   │
└─────────────────────────────────────────┘
```

### 触发条件

| 来源 | 触发方式 | 说明 |
|------|---------|------|
| R1D3 主动调用 | Skill `trigger_explore` | R1D3 明确决定探索 |
| Hook 自动检测 | `message:received` | 隐式探索意图发现 |
| DreamAgent 周期 | 6 小时心跳 | 基于 KG 热度分析 |

### R1D3 web_search 结果复用

**设计思路**：R1D3 通过 web_search 获得的知识 ≈ CA ExploreAgent 探索结果

```
R1D3: web_search("Transformer Attention")
    ↓
R1D3 获得搜索结果
    ↓
R1D3 回答用户
    ↓
R1D3 调用 Skill: add_web_knowledge(results)
    ↓
CA KG 收到知识
    ↓
后续相同 topic → 跳过重复探索
```

**好处**：
- 避免 R1D3 和 CA 重复工作
- CA KG 增长更快
- R1D3 验证过的知识更可靠

### Skill 和 Hook 去重机制

**问题**：Skill 和 Hook 可能同时添加相同 topic 到 Queue

**解决**：两层检查

```python
def add_to_queue(topic, source):
    # 1. 检查 KG 是否已有这个 topic（且质量够高）
    existing = kg.query(topic)
    if existing and existing.quality > 0.8:
        return  # KG 已有高质量节点，不需要重复探索

    # 2. 检查 Queue 是否已有这个 topic
    if queue.contains(topic):
        return  # 已经在队列中

    # 3. 添加到 Queue
    queue.add(topic, source=source)
```

### REST API 映射

| Skill | CA API | Hook | CA API |
|-------|--------|------|---------|
| `trigger_explore.sh` | `POST /api/curious/inject` | `message:received` | `POST /api/curious/inject` |
| `add_web_knowledge.sh` | `POST /api/kg/add` | `message:sent` | `POST /api/kg/add` |
| `check_confidence.sh` | `POST /api/metacognitive/check` | `message:preprocessed` | `POST /api/metacognitive/check` |

---

## 能力 #2：积累和管理知识（详细设计）

### 知识来源

**原则：知识点必须经过验证，有可靠来源才能入 KG**

| 来源 | 入 KG？ | 理由 |
|------|---------|------|
| R1D3 web_search | ✅ | 有 URL 来源验证 |
| R1D3 回答（web_search 后） | ✅ | 是搜索结果的自然产出 |
| ExploreAgent 探索 | ✅ | 结构化探索 |
| DreamAgent 反思 | ⚠️ | AI 生成，质量中等 |
| 用户输入 | ❌ | 不验证，不入 KG |

### 知识入 KG 的原则

**有 URL 的知识才能入 KG**：

```
R1D3 web_search("Transformer")
    ↓
R1D3 获得结果（有 URL）
    ↓
R1D3 回答用户
    +
R1D3 调用 add_web_knowledge(topic, content, url) ✅
    ↓
CA KG 收到有来源验证的知识

vs

R1D3 纯内化回答（无 web_search）
    ↓
没有 URL
    ↓
不调用 add_web_knowledge ❌
    ↓
知识不进入 CA KG
```

### Skill add_web_knowledge 设计

```bash
# 必需参数：topic, content, url
bash scripts/add_web_knowledge.sh "$topic" "$content" "$url"

# 如果知识点没有 URL，就不要调用这个 Skill
```

| 参数 | 必须 | 说明 |
|------|------|------|
| topic | ✅ | 知识主题 |
| content | ✅ | 知识内容 |
| url | ✅ | 来源 URL（必须有） |

### Hook 的知识提取范围

| Hook | 提取知识？ | 说明 |
|------|-----------|------|
| `message:received` | ❌ | 用户输入不验证 |
| `message:sent` | ❌ | 看不到 web_search 调用历史，无法获取 URL |
| `session:compact:after` | ❌ | 同上 |

**结论**：知识积累主要通过 Skill `add_web_knowledge` 完成，Hook 不做知识提取。

---

## 能力 #3：置信度感知（详细设计）

### 核心流程

```
用户问题 → 先查 KG
    ↓
KG 返回结果 + 置信度标签
    ↓
┌─────────────────────────────────────┐
│ high → 直接用 KG 知识回答           │
│ medium → 用 KG 知识 + 补充         │
│ low →                             │
│   1. 诚实回答（LLM 内化知识）      │
│   2. 触发 trigger_explore          │
└─────────────────────────────────────┘
```

### 置信度三级

| 级别 | 条件 | 行为 |
|------|------|------|
| **high** | KG 存在 topic **且有关联知识** | 直接用 CA 知识回答 |
| **medium** | KG 存在 topic **但孤立**（无关联） | 可以用，但关联不强 |
| **low** | KG **检索不到** topic | 依赖 LLM 内化知识 |

### 置信度判断逻辑

```
query_kg(topic)
    ↓
查询 KG: topic 是否存在？
    ↓
┌─────────────────────────────────┐
│ 不存在 → confidence = low       │
│                                 │
│ 存在 → 有关联知识？            │
│         ↓ 是     → confidence = high │
│         ↓ 否     → confidence = medium │
└─────────────────────────────────┘
```

### Skill query_knowledge 设计

```bash
curl -X POST http://localhost:4848/api/kg/query \
  -d '{"topic": "Transformer"}'
```

返回：
```json
{
  "topic": "Transformer",
  "confidence": "high",  // "high" | "medium" | "low"
  "nodes": [...],
  "relations": [...]
}
```

### R1D3 使用逻辑

```python
result = query_knowledge("Transformer")

if result.confidence == "low":
    # 诚实回答 + 触发探索
    answer_with_llm()
    trigger_explore("Transformer")
elif result.confidence == "medium":
    answer_with_kg_medium(result)
else:
    answer_with_kg_high(result)
```

---

## 能力 #4：主动分享新发现（详细设计）

### 核心流程

```
R1D3 心跳触发
    ↓
调用 CA Skill: share_new_discoveries
    ↓
CA 查询 KG，返回未分享的发现
    ↓
R1D3 获取发现列表
    ↓
R1D3 决定是否分享给用户
    ↓
R1D3 主动告诉用户新发现
```

### 现有 Skill

| Skill | 用途 |
|-------|------|
| `sync_discoveries.py` | 同步发现到 memory |
| `share_new_discoveries.py` | 获取未分享发现，返回给 R1D3 |

### 分享内容

| 内容 | 说明 |
|------|------|
| 新发现的知识点 | ExploreAgent 新增的 KG 节点 |
| 置信度变化 | topic 置信度从 medium 变成 high |

### 结论

**现有设计已经覆盖能力 #4**：R1D3 心跳调用 CA Skill，CA 返回未分享发现，R1D3 决定是否分享给用户。

---

## 能力 #5：R1D3 后台知识库（详细设计）

### 核心流程

```
用户问题 → Hook message:preprocessed
    ↓
R1D3 调用 query_knowledge(topic)
    ↓
CA KG 返回知识 + 置信度
    ↓
知识注入 R1D3 上下文
    ↓
R1D3 回答用户
```

### Hook 配合

| Hook | 作用 |
|------|------|
| `message:preprocessed` | 自动注入 CA 知识到 R1D3 上下文 |

### 结论

**能力 #5 已融入能力 #1 和 #3 的设计**：query_knowledge 返回知识 + 置信度，R1D3 根据置信度决定如何回答。

---

## 9. 遗留任务

| # | 任务 | 状态 | 待讨论/待完成内容 |
|---|------|------|------------------|
| 1 | Q1 API Gateway 详细设计 | ✅ 已完成 | 自动/手动两种注册模式 |
| 2 | Q9 Hook 集成详细设计 | ✅ 已完成 | Skill + Hook 配合架构 |
| 3 | 能力 #1 详细设计 | ✅ 已完成 | 探索流程 + 去重机制 + R1D3 web_search 复用 |
| 4 | 能力 #2 详细设计 | ✅ 已完成 | 知识来源 + add_web_knowledge 设计 |
| 5 | 能力 #3 详细设计 | ✅ 已完成 | 置信度 = query_kg 返回标签 (high/medium/low) |
| 6 | 能力 #4 详细设计 | ✅ 已完成 | 心跳调用 share_new_discoveries Skill |
| 7 | 能力 #5 详细设计 | ✅ 已完成 | 融入能力 #1/#3 设计 |
| 8 | Tool 逐一设计 | ✅ 已完成 | 12 个 Tool inputs/outputs + 4 个设计问题结论 |
| 9 | 测试框架搭建 | ✅ 已完成 | pytest 配置 + 目录结构 + fixtures + CI/CD | |

---

## 10. 数据存储 Schema

### Neo4j KG Schema

**节点类型**：`KnowledgeNode`

```cypher
// 创建节点
CREATE (n:KnowledgeNode {
    title: String,           // 知识主题（唯一索引）
    content: String,         // 知识内容
    source_urls: List[String], // 来源 URL 列表
    relations: Map,          // 关系字典（derived_from/cites/related_to/supersedes/superseded_by）
    status: String,          // VALID | DEPRECATED | DISPUTED | ARCHIVED
    created_at: DateTime,
    last_accessed: DateTime,
    heat: Float,             // 0.0 ~ 1.0
    quality: Float,           // 0.0 ~ 10.0
    confidence: Float        // 0.0 ~ 1.0
})

// 索引
CREATE INDEX knowledge_node_title IF NOT EXISTS FOR (n:KnowledgeNode) ON (n.title);
CREATE INDEX knowledge_node_status IF NOT EXISTS FOR (n:KnowledgeNode) ON (n.status);
CREATE INDEX knowledge_node_heat IF NOT EXISTS FOR (n:KnowledgeNode) ON (n.heat);
```

**关系类型**：

```cypher
// 知识关系
(n1:KnowledgeNode)-[:CITES {weight: Float}]->(n2:KnowledgeNode)
(n1:KnowledgeNode)-[:DERIVED_FROM]->(n2:KnowledgeNode)
(n1:KnowledgeNode)-[:RELATED_TO {weight: Float}]->(n2:KnowledgeNode)
(n1:KnowledgeNode)-[:SUPERSEDES]->(n2:KnowledgeNode)
(n1:KnowledgeNode)-[:SUPERSEDED_BY]->(n2:KnowledgeNode)
```

### SQLite Queue Schema

```sql
CREATE TABLE queue_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'manual',
    priority INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | claimed | done | failed
    holder_id TEXT,                            -- claim 时写入
    claim_time DATETIME,                       -- claim 时间戳
    done_time DATETIME,
    fail_reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_queue_status ON queue_items(status);
CREATE INDEX idx_queue_priority ON queue_items(priority DESC);
CREATE INDEX idx_queue_topic ON queue_items(topic);
```

### configs/ 目录结构

```
configs/
├── llm.yaml              # LLM Provider 配置
├── neo4j.yaml            # Neo4j 连接配置
├── sqlite.yaml           # SQLite 路径配置
├── agent_explore.yaml    # ExploreAgent 配置
└── agent_dream.yaml      # DreamAgent 配置
```

### volcengine LLM 配置

```yaml
# configs/llm.yaml
provider: volcengine
model: ${VOLCENGINE_MODEL}          # e.g., doubao-pro-32k
api_key: ${VOLCENGINE_API_KEY}
base_url: https://ark.cn-beijing.volces.com/api/v3
timeout: 60
max_retries: 3
```

### Neo4j 连接配置

```yaml
# configs/neo4j.yaml
uri: ${NEO4J_URI}          # bolt://localhost:7687
database: ${NEO4J_DATABASE} # ca_production
auth:
  username: ${NEO4J_USER}  # neo4j
  password: ${NEO4J_PASSWORD}
```

### SQLite 配置

```yaml
# configs/sqlite.yaml
database: ${CA_SQLITE_PATH}  # data/curious_agent.db
```

### 环境变量清单

```bash
# CA 运行时必须的环境变量
NEO4J_URI=bolt://localhost:7687
NEO4J_DATABASE=ca_production
NEO4J_USER=neo4j
NEO4J_PASSWORD=xxx

CA_SQLITE_PATH=data/curious_agent.db

VOLCENGINE_API_KEY=xxx
VOLCENGINE_MODEL=doubao-pro-32k

CA_API_KEY=ca_key_xxx  # API Gateway 认证
CA_PORT=4848           # REST API 端口

# Skill/Hook 消费者视角
CA_BASE_URL=http://localhost:4848
```

### FastAPI 框架确认

**使用 FastAPI**，基于以下理由：
- 与 OpenClaw 技术栈一致（OpenClaw 用 Starlette，FastAPI 是 Starlette 的子类）
- 自动 OpenAPI 文档生成
- Pydantic 原生支持
- 生态丰富，易于扩展

---

## 11. 开发计划

### Phase 0：框架搭建（最高优先级）

1. 复制 frameworks 模块（error_classifier、retry_utils、heartbeat_service）
2. 搭建项目结构（configs/、tools/、agents/、daemon/）
3. 实现 Tool 基类（`BaseTool`）和注册表（`ToolRegistry`）
4. 实现 KG Tools（6 个）
5. 实现 Queue Tools（5 个）
6. 实现 Search Tools（5 个）
7. 实现 LLM Tools（2 个）
8. 实现 FastAPI 骨架 + 所有 REST API 端点
9. 配置管理（configs/ 目录 + 环境变量加载）
10. 搭建测试框架（pytest + conftest.py + 覆盖率配置）

### Phase 1：ExploreAgent

1. 实现 ExploreAgent 类（ReAct 循环 + Tool 调用）
2. 实现 ExploreAgentDaemon（连续运行 + claim/done/fail 循环）
3. 集成 search/fetch/llm tools
4. 实现从 claim 到 mark_done/fail 的完整生命周期
5. 测试探索流程

### Phase 2：DreamAgent

1. 配置 DreamAgentHeartbeat（6 小时触发）
2. 实现多周期批处理引擎（3-4 个 Mini-Cycles）
3. 实现四层工序（L1: Light / L2: Deep / L3: Filtering / L4: REM → Queue）
4. 实现并行评分和阈值门控逻辑
5. 实现 Queue 生成（DreamAgent 不写 KG，只生成 topic）
6. 测试 heartbeat 触发 + 多周期协调

### Phase 3：集成测试 + API Gateway

1. 端到端测试（完整探索 pipeline）
2. FastAPI API Gateway（认证 + 限流）
3. Skill 接口实现（check_confidence、trigger_explore、query_knowledge 等）
4. WebUI 集成

---

## 附录：Nanobot 开发参考

详见 `/root/dev/nanobot/` 源码。

### Nanobot 核心模块位置

```
/root/dev/nanobot/
├── nanobot/agent/
│   ├── loop.py          # AgentLoop.run()
│   ├── tools/
│   │   ├── registry.py  # ToolRegistry
│   │   └── base.py      # Tool 基类
│   └── heartbeat/
│       └── service.py   # HeartbeatService
└── nanobot/skills/      # Skill 定义
```
