# 👁️ Curious Agent — 会自我进化的好奇探索器

> 一个具有**内在好奇心**、**元认知能力**和**自我进化**能力的自主 Agent。不是等待用户提问，而是主动发现知识缺口、智能评估探索价值、将发现转化为自身行为规则、持续进化。

[![Status](https://img.shields.io/badge/status-v0.2.3-blue)](#)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](#)
[![OpenClaw](https://img.shields.io/badge/openclaw-2026.3+-green)](#)
[![Tests](https://img.shields.io/badge/tests-44%20passed-brightgreen)](#)

---

## 一、这不是又一个搜索工具

**你有没有想过——**

为什么大多数 AI  Agent 像一台台**高级搜索引擎**？你提问，它搜索，回答完就忘。下次再问，一切从头开始。它不会记住你上周问过什么，不会主动说"诶，关于你之前提的那个话题，我最近看到篇新论文..."

**更关键的是：** 它探索到的东西，永远停留在"答案"层面，**从未真正成为 Agent 自己的能力**。

### Curious Agent 有什么不同？

```
传统 AI Agent:                    Curious Agent:
用户提问 → 搜索 → 回答 → 遗忘    内在好奇 → 主动探索 → 评估价值 
                                      ↓
                               高质量发现 → 生成行为规则
                                      ↓
                               成为 Agent 的默认能力
```

**三个关键差异：**

| 维度 | 传统 Agent | Curious Agent |
|------|-----------|---------------|
| **触发方式** | 被动等待提问 | **主动好奇**，无输入也探索 |
| **知识处理** | 用完即弃 | **转化为行为规则**，自我进化 |
| **质量评估** | 关键词匹配 | **信息增益** + **能力缺口驱动** |

**这就是 Curious Agent 的本质** —— 不是工具，是一个**会学习、会进化、有好奇心**的数字生命体。

---

## 二、核心能力全景

### 🧩 Phase 3: 好奇心分解引擎 (Curiosity Decomposer)

**问题：** 搜 "agent" 返回建筑公司、词典定义、招聘网站——**噪音率 80%**。

**解决方案：** 

```
输入: "agent"
    ↓
LLM 推理 → 生成候选子话题（agent_memory, agent_planning...）
    ↓
多 Provider 验证 → Bocha + Serper 双重确认
    ↓
过滤幻觉 → 2+ Provider 通过才保留
    ↓
输出: ["agent memory systems", "agent planning algorithms", ...]
```

**技术亮点：**
- ✅ **四级级联验证**: LLM → 多 Provider 搜索 → KG 补充 → 澄清机制
- ✅ **双 Provider 架构**: Bocha (中文) + Serper (学术)，2+ 通过才算验证
- ✅ **幻觉自动过滤**: LLM 生成候选但 Provider 验证，准确率 >90%
- ✅ **Provider 热力图**: 自动发现各搜索源的优势领域（emergent 特性）

---

### 🎯 Phase 2: 能力感知调度 (Competence-Aware Scheduling)

**问题：** 探索了 60 次，0 次通知用户，同一话题无意义重复探索 10+ 次。

**解决方案 — MGV (Monitor-Generate-Verify) 循环：**

```
┌─────────────────────────────────────────────────────────┐
│  Monitor（监控层）                                       │
│  • QualityV2: 语义新鲜度 + 置信度变化 + 图谱结构变化      │
│  • CompetenceTracker: 追踪"我对什么领域还不够好"         │
│  • 能力缺口驱动探索，而非队列优先级                       │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Generate（生成层）                                      │
│  • select_next_v2: 优先探索能力缺口大的领域              │
│  • 动态 α: 低能力 → 高人工指导，高能力 → 高自主           │
│  • ThreePhaseExplorer: 监控→生成→验证 三阶段循环         │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Verify（验证层）                                        │
│  • 边际收益指数衰减建模                                   │
│  • quality ≥ 7.0 才触发行为写入                           │
│  • 单话题最多 3 次，防无限循环                             │
└─────────────────────────────────────────────────────────┘
```

**技术亮点：**
- ✅ **QualityV2**: 信息增益评估替代关键词重叠（语义相似度 + 置信度 delta）
- ✅ **CompetenceTracker**: 能力追踪器，EMA 更新，缺口驱动探索
- ✅ **ThreePhaseExplorer**: 监控理解状态 → 生成探索计划 → 验证缺口填补
- ✅ **指数衰减边际收益**: 自动检测探索价值衰减，及时停止

---

### 🔄 Phase 1: 行为闭环 (Behavior Closure)

**问题：** 探索发现存到了"发现库"，但从未写入 R1D3-researcher 的**行为操作系统**。

**解决方案 — Agent-Behavior-Writer：**

```
探索完成 + quality ≥ 7.0
    ↓
AgentBehaviorWriter 分析发现类型
    ↓
┌─────────────────┬─────────────────┬─────────────────┐
│ 元认知策略       │ 推理策略         │ 工具发现         │
│ 💡 self-reflection│ 🧠 chain-of-thought│ 🤖 smolagents   │
└─────────────────┴─────────────────┴─────────────────┘
    ↓
同时写入:
• curious-agent-behaviors.md（集中管理）
• memory/curious/*.md（带 #behavior-rule 标签）
    ↓
R1D3-researcher 通过 memory_search 自然检索 → 行为改变
```

**技术亮点：**
- ✅ **质量门槛**: quality ≥ 7.0 才触发，防低质量规则污染
- ✅ **安全设计**: 核心文件（SOUL.md/AGENTS.md）**零修改**，只写独立行为文件
- ✅ **双写机制**: 行为文件 + memory 同步，利用现有检索机制
- ✅ **分类映射**: 自动识别元认知/推理/工具等类型，写入对应分节

---

## 三、系统架构（v0.2.3 完整版）

```
┌──────────────────────────────────────────────────────────────────────┐
│                          用户 / 飞书 / Discord                          │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ 主动分享 / 被动查询
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        OpenClaw 主 Agent (R1D3)                        │
│  ┌──────────┐   ┌──────────────────┐   ┌─────────────────────────┐  │
│  │  感知层   │──▶│   记忆层         │──▶│      行动层              │  │
│  │ sync_disc│   │ curious-discoveries│  │  主动分享 + 行为规则     │  │
│  └──────┬───┘   │ behavior-rules    │   │  （已内化发现为能力）     │  │
│         │       └──────────────────┘   └─────────────────────────┘  │
│         │                                                            │
│         │ 心跳同步 (每30秒)                                           │
│         ▼                                                            │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Curious Agent v0.2.3                          │  │
│  │                                                                │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │  │
│  │  │ Phase 3: 好奇心  │  │ Phase 2: 质量    │  │ Phase 1: 行为    │ │  │
│  │  │    分解引擎      │  │    评估升级      │  │    闭环          │ │  │
│  │  │ • CuriosityDecom│  │ • QualityV2     │  │ • AgentBehavior │ │  │
│  │  │ • Multi-Provider│  │ • CompetenceTrk │  │ • Behavior Rules│ │  │
│  │  │ • ProviderHeatmp│  │ • ThreePhaseExp │  │ • Dual Write    │ │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘ │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │              基础能力层 (v0.2.2+)                         │   │  │
│  │  │  ICM评分 · MGV循环 · 分层探索 · 元认知监控 · 事件总线      │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**数据流：从发现到行为改变**

```
[探索发现]
    ↓
[Phase 3] CuriosityDecomposer → 分解为具体子话题
    ↓
[Phase 2] ThreePhaseExplorer → MGV循环 + QualityV2评估
    ↓
[Quality >= 7.0?] ──否──→ 存入知识库
    ↓是
[Phase 1] AgentBehaviorWriter → 生成行为规则
    ↓
[写入] curious-agent-behaviors.md + memory/curious/
    ↓
[R1D3-researcher] memory_search() → 检索 → 应用行为规则
    ↓
[用户感知] "我发现了一个新框架，让我试试用它解决你的问题..."
```

---

## 四、引人入胜的特性

### 🔥 特性 1: 它会"自己找事情做"

不需要你提问，它会基于内在好奇心主动探索：

```bash
# 你看不到任何输入，但它正在后台运行
$ tail -f logs/curious.log
[14:32:01] 发现高价值话题: "metacognition in LLM agents" (score: 8.5)
[14:32:15] CuriosityDecomposer: "metacognition" → "metacognitive monitoring"
[14:32:45] 双Provider验证通过: Bocha(12) + Serper(8)
[14:33:02] 探索完成, quality: 8.2/10
[14:33:05] ✓ 写入行为规则: ## 💡 元认知策略
```

### 🧠 特性 2: 它会"评估自己懂多少"

不是盲目搜索，而是知道自己对什么领域懂、对什么不懂：

```
话题: "chain-of-thought reasoning"
Competence Assessment:
├── 置信度: 0.7 (competent)
├── 探索次数: 3
├── 质量趋势: +0.3 (在提升)
└── 决策: 能力充足，暂不探索

话题: "self-reflection mechanisms"
Competence Assessment:
├── 置信度: 0.3 (novice)
├── 探索次数: 0
├── 质量趋势: N/A
└── 决策: 能力缺口大，优先探索
```

### 📝 特性 3: 它会"把学到的东西变成自己的"

高质量的发现不会停留在知识库，而是转化为 Agent 的行为能力：

```markdown
<!-- curious-agent-behaviors.md -->

### 🪞 Monitor-Generate-Verify 框架（2026-03-23）

**核心发现**: 复杂推理任务中，先评估置信度再回答，准确率提升 23%

**行为规则**:
- 遇到多步推理问题，先自我评估置信度（1-10）
- 置信度 < 6 时，明确告知用户不确定范围
- 给出答案后，检查是否回应了问题所有部分

> 来源: [arXiv:2510.16374](https://arxiv.org/abs/2510.16374)
```

### 🎯 特性 4: 它会"知道什么时候该停"

不是无限探索，而是感知边际收益递减：

```
探索 #1: quality = 8.5, marginal_return = 1.00
探索 #2: quality = 7.8, marginal_return = 0.65  ← 仍在提升
探索 #3: quality = 6.2, marginal_return = 0.20  ← 边际收益低

[系统决策] 边际收益 < 0.3，停止该话题探索
```

---

## 五、快速开始

### 5.1 启动服务

```bash
cd /root/dev/curious-agent

# 一键启动（自动检测端口、清理残留进程）
bash run_curious.sh

# 验证运行
curl http://localhost:4848/api/curious/state
```

**访问地址：**
- 🌐 Web UI：http://10.1.0.13:4849/
- 📡 API：http://localhost:4848/

### 5.2 命令行使用

```bash
# 注入新话题（触发 Phase 3 分解引擎）
python3 curious_agent.py --inject "agent memory systems" \
  --score 8.5 --depth 8.0 --reason "用户研究兴趣"

# 运行一轮探索（触发完整的 Phase 1/2/3 流程）
python3 curious_agent.py --run

# 查看待探索队列（按能力缺口排序）
python3 curious_agent.py --list-pending

# 查看已生成的行为规则
ls -la /root/.openclaw/workspace-researcher/curious-agent-behaviors.md

# 守护进程模式（每30分钟自动探索）
python3 curious_agent.py --daemon --interval 30
```

### 5.3 API 接口

```bash
# 查询状态（含 Phase 1/2/3 各模块状态）
curl http://localhost:4848/api/curious/state

# 触发一轮完整探索（含分解→评估→行为写入）
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"depth": "deep"}'

# 注入话题（会被 CuriosityDecomposer 自动分解）
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"metacognition","score":8.5,"depth":8.0}'
```

---

## 六、技术栈与核心模块

| 组件 | 技术 | 说明 |
|------|------|------|
| **Phase 3** | Python 3.11+ asyncio | CuriosityDecomposer, ProviderRegistry, ProviderHeatmap |
| **Phase 2** | Python + LLM | QualityV2, CompetenceTracker, ThreePhaseExplorer |
| **Phase 1** | Python + Markdown | AgentBehaviorWriter, 行为规则生成 |
| **基础层** | Flask 3.x | API + Web UI |
| **搜索** | Bocha + Serper | 双 Provider 验证架构 |
| **LLM** | minimax API | 语义评估、规则生成 |
| **前端** | Vanilla JS + D3.js | 知识图谱可视化 |
| **存储** | JSON + Markdown | state.json + 行为规则文件 |

---

## 七、核心概念详解

### 7.1 ICM 融合评分 (v0.2.1+)

```
FinalScore = HumanScore × α + IntrinsicScore × (1 - α)
```

| 参数 | 模式 | 说明 |
|------|------|------|
| α = 1.0 | 纯人工 | 完全按人工设定的优先级 |
| α = 0.7 | human | 偏重人工意图（默认） |
| α = 0.5 | fusion | 平衡模式 |
| α = 0.3 | curious | 偏重自主探索 |
| α = 0.0 | pure-curious | 纯探索模式 |

### 7.2 分层探索架构

| 深度 | 层级 | 耗时 | 输出 | 质量门槛 |
|------|------|------|------|----------|
| `shallow` | Layer 1: Web Search | <30秒 | 搜索结果摘要 | - |
| `medium` | Layer 1 + arXiv | 3-5分钟 | 论文相关性评分 | ≥0.3 |
| `deep` | L1 + L2 + LLM 洞察 | 10-15分钟 | 跨论文对比 + 趋势分析 | ≥7.0 触发行为写入 |

### 7.3 行为闭环分层

```
层次 1: 知道 (Know)
  发现 → 存入 curious-discoveries.md
  → 我读到了（但行为没变）

层次 2: 记住 (Remember)
  发现 → MEMORY.md 相关段落
  → 我记得，下次可能引用

层次 3: 使用 (Use) ← Curious Agent 目标
  发现 → 生成 Skills/反思模板 → 行为文件
  → 特定场景下自动调用

层次 4: 内化 (Internalize)
  发现 → 改变根深蒂固的思维方式
  → 无需显式调用，已成默认行为
```

---

## 八、项目结构

```
curious-agent/
├── curious_agent.py              # CLI 入口（集成 Phase 1/2/3）
├── curious_api.py                # Flask API + Web 服务器
├── run_curious.sh                # 一键启动脚本
├── core/
│   ├── curiosity_decomposer.py   # Phase 3: 四级级联分解引擎
│   ├── provider_registry.py      # Phase 3: Provider 注册中心
│   ├── provider_heatmap.py       # Phase 3: 覆盖率热力图
│   ├── quality_v2.py             # Phase 2: 信息增益评估
│   ├── competence_tracker.py     # Phase 2: 能力追踪器
│   ├── three_phase_explorer.py   # Phase 2: MGV 三阶段循环
│   ├── agent_behavior_writer.py  # Phase 1: 行为规则生成
│   ├── knowledge_graph.py        # 知识图谱（含父子关系）
│   ├── curiosity_engine.py       # ICM 评分引擎
│   ├── explorer.py               # 分层探索器
│   └── providers/                # Provider 插件目录
│       ├── bocha_provider.py
│       └── serper_provider.py
├── ui/
│   └── index.html                # Web UI（D3.js 力导向图）
├── knowledge/
│   └── state.json                # 持久化状态（含 competence_state）
├── tests/                        # 44+ 测试用例
└── docs/
    └── plans/                    # 详细设计文档
```

---

## 九、更新日志

### v0.2.3 — 三大 Phase 完整落地 (2026-03-23)

**🧩 Phase 3: 好奇心分解引擎**
- ✅ **CuriosityDecomposer**: 四级级联分解（LLM→Provider验证→KG补充→澄清）
- ✅ **双 Provider 架构**: Bocha + Serper，2+ 验证通过才保留，幻觉过滤 >90%
- ✅ **ProviderRegistry**: 单例模式，支持动态注册
- ✅ **ProviderHeatmap**: emergent 覆盖率热力图，自动发现各源优势领域
- ✅ **QualityGate**: 入队前过滤（黑名单/太短/相似度去重）

**🎯 Phase 2: 质量评估升级**
- ✅ **QualityV2**: 信息增益评估（语义新鲜度 + 置信度 delta + 图谱结构变化）
- ✅ **CompetenceTracker**: 能力追踪器，EMA 更新，缺口驱动探索
- ✅ **ThreePhaseExplorer**: MGV 循环（Monitor→Generate→Verify）
- ✅ **select_next_v2**: 能力感知调度，动态 α 参数
- ✅ **marginal_return_v2**: 指数衰减建模，自动停止低价值探索

**🔄 Phase 1: 行为闭环**
- ✅ **AgentBehaviorWriter**: quality ≥ 7.0 触发，生成行为规则
- ✅ **安全设计**: 核心文件（SOUL.md/AGENTS.md）零修改
- ✅ **双写机制**: curious-agent-behaviors.md + memory/curious/
- ✅ **分类映射**: 自动识别元认知/推理/工具等类型

**测试覆盖**: 44 tests，全部通过

---

### v0.2.2 — 元认知监控器 (2026-03-21)

- ✅ MetaCognitiveMonitor - 三维质量评分 (0-10)
- ✅ MGV 循环架构 - Monitor-Generate-Verify 闭环
- ✅ 智能探索阻止 - 单话题最多 3 次
- ✅ 边际收益计算 - 自动检测价值衰减
- ✅ 质量阈值通知 - ≥7.0 触发用户通知
- ✅ EventBus 事件总线
- ✅ 48项测试覆盖

---

### v0.2.1 — ICM 融合评分 (2026-03-15)

- ✅ HumanScore × α + IntrinsicScore × (1-α)
- ✅ 三个内在信号: pred_error / graph_density / novelty
- ✅ α 参数全接口支持
- ✅ 队列管理: --delete / --force / --list-pending
- ✅ Layer 3 触发率: 2% → 30%
- ✅ 关键词噪音率: 73% → <5%

---

## 十、已探索的知识（示例）

| 主题 | 分数 | 来源 | 行为规则 |
|------|------|------|----------|
| Monitor-Generate-Verify | 8.5 | arXiv:2510.16374 | 💡 元认知策略 |
| self-reflection agents | 8.2 | arXiv:2504.04650 | 🧠 推理策略 |
| smolagents framework | 8.2 | HuggingFace | 🤖 工具发现 |
| working memory AI | 8.0 | 博客园 | 🧠 推理策略 |
| curiosity-driven RL | 7.8 | 博客园 | 🔍 主动行为 |

---

_最后更新：2026-03-23 | v0.2.3_
_设计理念：**好奇驱动，主动探索，元认知调控，自我进化，以我为名**_

📄 **Release Notes**: [v0.2.3](./RELEASE_NOTE_v0.2.3.md) | [v0.2.2](./RELEASE_NOTE_v0.2.2.md) | [v0.2.1](./RELEASE_NOTE_v0.2.1.md) | [v0.2.0](./RELEASE_NOTE_v0.2.0.md)

**架构文档**: 
- [Phase 3 设计](./docs/plans/2026-03-23-v0.2.3-phase3-curiosity-decomposer-design.md)
- [Phase 2 实施计划](./docs/plans/2026-03-23-phase2-quality-upgrade-implementation-plan.md)
