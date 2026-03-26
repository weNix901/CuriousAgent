# 👁️ Curious Agent — 会自我进化的好奇探索器

> 一个具有**内在好奇心**、**元认知能力**和**自我进化**能力的自主 Agent。不是等待用户提问，而是主动发现知识缺口、智能评估探索价值、将发现转化为自身行为规则、持续进化。

[![Status](https://img.shields.io/badge/status-v0.2.4-blue)](#)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](#)
[![OpenClaw](https://img.shields.io/badge/openclaw-2026.3+-green)](#)
[![Tests](https://img.shields.io/badge/tests-45%20modules-brightgreen)](#)

---

## 一、它不只是搜索，而是会思考的研究助手

**想象一下这个场景：**

你问 ChatGPT："帮我查一下 agent 相关的最新研究。" 它给你 10 篇论文摘要，你看完关掉窗口。一周后你又问同样的问题——它**从零开始**，给你**完全不同的 10 篇**，好像上周的对话从未发生。

**更糟的是**，它从不主动告诉你："对了，关于你上周问的那个方向，我发现一个超重要的突破..."

### Curious Agent 彻底改变了这个逻辑

**传统 AI 就像雇佣了一个临时工：**
- 你喊他，他才动
- 干完活就忘  
- 下次重来一遍

**Curious Agent 像养了一个研究生：**
- 会自己找课题做
- 越做越懂你
- 把学到的东西变成自己的本事
- 主动找你汇报进展

```
你: "帮我看看 agent 方向"
    ↓
它: （默默钻研了一周）
    ↓
它: "我发现一个超重要的框架！已经帮你整理成我的思考方式了，
       以后遇到类似问题我会自动用这个思路分析。"
```

**简单说：它不是工具，是你数字世界的分身，越用越懂你。**

---

## 二、它有三项"超能力"

### 🔍 超能力一：想搜什么，一说就懂

**你遇到过这种尴尬吗？**

搜 "agent"，结果前三个是：
1. 房产中介公司
2. 英语词典释义  
3. 招聘网站的 agent 职位

**有用的学术内容被淹没在噪音里。**

**Curious Agent 的做法：**

你说 "agent"，它不会傻傻去搜这个词。而是先理解你的意图——你八成是在说 AI Agent、智能体——然后自动分解出精准的关键词：

```
你: "帮我看看 agent"
    ↓
它: （思考 2 秒）
    "用户说的是 AI 领域的 Agent，不是房产中介"
    ↓
自动分解出: agent memory、agent planning、multi-agent...
    ↓
用多个搜索引擎交叉验证
    ↓
过滤掉不靠谱的结果
    ↓
给你: "agent memory systems"、"agent planning algorithms"...
```

**就像你和一个懂行的朋友聊天**，你说个大概，他立刻 get 到你想问什么。

---

### 🧠 超能力二：有自知之明，不瞎折腾

**普通 AI 的问题：**

- 同一个话题重复探索 10 遍，从不觉得腻
- 探索了 60 次，一次都不告诉你发现了啥
- 不知道自己懂什么、不懂什么

**Curious Agent 像一个成熟的研究者：**

**1. 它知道自己懂多少**

```
话题: "chain-of-thought"
├── 我探索过 3 次了
├── 每次质量都不错
├── 这个领域我挺熟的（置信度 0.7）
└── 决策: 暂时不用深挖了

话题: "self-reflection"
├── 完全没接触过
├── 置信度只有 0.3
└── 决策: 这是知识盲区，优先安排！
```

**2. 它知道什么时候该停**

```
第 1 次探索: 质量 8.5，收获满满
第 2 次探索: 质量 7.8，还能挖点东西
第 3 次探索: 质量 6.2，边际收益很低了

它: "这个话题差不多了，继续投入性价比不高，
      我去看看别的方向。"
```

**3. 它只把有价值的东西告诉你**

不是什么都汇报（那叫骚扰），而是质量 ≥ 7 分才通知你。

---

### 🔄 超能力三：学了就用，用完就改

**最厉害的来了。**

普通 AI "学"到的东西，就躺在知识库里吃灰。Curious Agent **会把学到的东西变成自己的行为习惯**。

**举个例子：**

它通过阅读论文发现："在多步推理任务中，先评估自己的置信度再回答，准确率能提升 23%。"

普通 AI：把这个结论存进数据库，完事。

Curious Agent：
1. 分析这个发现的类型（这是元认知策略）
2. 自动写成行为规则：
   ```markdown
   ## 🪞 新学到的：Monitor-Generate-Verify 框架
   
   以后遇到复杂问题，我要：
   1. 先评估自己有多大把握（1-10 分）
   2. 把握不足 6 分时，明确告诉用户我不太确定
   3. 回答完检查是否覆盖了问题的所有部分
   
   来源: arXiv:2510.16374
   ```
3. 写入自己的行为手册（curious-agent-behaviors.md）
4. **以后遇到类似问题，自动用这个新思路处理**

**简单说：它在进化。今天的它比昨天更聪明，因为昨天的它学到了新东西，并内化成了能力。**

---

## 三、这四个特点，让它不像个工具，更像个伙伴

### 🔥 特点一：不用你催，它会自己找事做

你不需要天天盯着它问"今天有什么新发现"。把它跑起来，它会在后台自己运转：

```bash
# 你在忙别的事，它在默默工作
$ tail -f logs/curious.log
[14:32:01] 发现个有意思的方向: "metacognition in LLM agents" (评分 8.5)
[14:32:15] 细化为: "metacognitive monitoring"
[14:32:45] 多源验证通过 ✓
[14:33:02] 探索完成，质量 8.2/10，值得记录
[14:33:05] 已写入新的行为规则: 元认知策略
```

**就像雇了一个不用睡觉的研究助理**，你专心做自己的事，它帮你盯着前沿动态。

---

### 🧠 特点二：它知道自己几斤几两

不像某些 AI 不懂装懂，Curious Agent **清楚自己懂什么、不懂什么**：

```
问它: "chain-of-thought 是怎么回事？"

它心里会想:
├── 这个话题我研究过 3 次了
├── 之前的探索质量都不错
├── 这个领域我算是熟了（置信度 70%）
└── 结论: 我可以自信地回答

问它: "self-reflection 在 AI 里怎么实现？"

它心里会想:
├── 这个领域我接触得不多
├── 置信度只有 30%
└── 结论: 我得先去补补课，再给你靠谱的答案
```

**有自知之明，不瞎说，这是好研究员的基本素质。**

---

### 📝 特点三：学到真本事，不是记笔记

普通 AI "学"完就忘，Curious Agent 会把学到的东西**内化成本能**：

**举个例子：**

它读到一篇论文说："在多步推理任务中，先评估自己的置信度再回答，准确率能提升 23%。"

普通 AI："好的，已存入知识库。"（然后就忘了）

Curious Agent：
1. 分析：这是元认知策略，可以用在我以后的推理中
2. 提炼：写成自己的行为准则
3. 内化：以后遇到复杂问题，**自动**用这个新思路处理

```markdown
## 新掌握的技能：Monitor-Generate-Verify 框架

以后遇到复杂问题，我要：
1. 先掂量掂量自己有多大把握（1-10 分）
2. 把握不足 6 分时，老实告诉用户我不太确定
3. 回答完再检查一遍，确保没有漏掉问题的任何部分

（来自 arXiv:2510.16374）
```

**简单说：它在成长。今天的它比昨天更聪明。**

---

### 🎯 特点四：不钻牛角尖，懂见好就收

有些 AI 会死磕一个话题，一遍又一遍地重复搜索。Curious Agent 知道**什么时候该停**：

```
第 1 次探索这个话题: 挖到不少好东西（质量 8.5）
第 2 次: 还能找到一些补充（质量 7.8）
第 3 次: 收获越来越少了（质量 6.2）

它判断: "边际收益已经很低了，继续投入不值得，
          我还有很多其他方向可以研究。"
```

**聪明的研究者，知道把精力花在刀刃上。**

---

## 四、系统架构

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
│  │                    Curious Agent v0.2.4                          │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │              核心能力层                                  │   │  │
│  │  │  • 话题分解引擎: LLM推理 + 多Provider验证 + 幻觉过滤     │   │  │
│  │  │  • 质量评估系统: 信息增益 + 置信度追踪 + 边际收益建模     │   │  │
│  │  │  • 能力调度器: 缺口驱动 + 动态调度 + 三阶段探索          │   │  │
│  │  │  • 行为写入器: 质量门槛 + 安全设计 + 双写机制            │   │  │
│  │  │  • InsightSynthesizer: 跨话题洞察合成 + 假设生成         │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │              基础能力层                                  │   │  │
│  │  │  ICM评分 · 好奇心队列 · 知识图谱 · 分层探索 · 事件总线    │   │  │
│  │  │  SpiderEngine · KGGraph · R1D3Watcher · 检查点机制       │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │              R1D3集成层 (v0.2.4新增)                      │   │  │
│  │  │  • R1D3ToolHandler: 置信度查询 + 话题注入 + 优先级队列   │   │  │
│  │  │  • R1D3Sync: 发现双向同步 + 共享状态管理                 │   │  │
│  │  │  • R1D3Watcher: 学习需求监听 + 命题扫描                  │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**数据流：从发现到行为改变 (v0.2.4)**

```
[探索发现] / [R1D3注入话题]
    ↓
[话题分解引擎] → 分解为具体子话题
    ↓
[SpiderEngine] → 状态管理 + 检查点恢复
    ↓
[三阶段探索循环] → 监控→生成→验证
    ↓
[质量评估] → quality ≥ 7.0 ?
    ↓是
[行为写入器] → 生成行为规则
    ↓
[InsightSynthesizer] → 跨话题洞察合成 (Layer 3)
    ↓
[双写] → 行为文件 + memory/curious/ + shared_knowledge/
    ↓
[R1D3Sync] → 双向同步发现到外部Agent
    ↓
[Agent 检索] → memory_search() → 应用行为规则
    ↓
[用户感知] "我发现了一个新框架，让我试试用它解决你的问题..."
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
# 注入新话题（触发话题分解引擎）
python3 curious_agent.py --inject "agent memory systems" \
  --score 8.5 --depth 8.0 --reason "用户研究兴趣"

# 运行一轮完整探索（话题分解→质量评估→行为写入）
python3 curious_agent.py --run

# 查看待探索队列（按能力缺口排序）
python3 curious_agent.py --list-pending

# 查看已生成的行为规则
cat /root/.openclaw/workspace-researcher/curious-agent-behaviors.md

# 守护进程模式（每30分钟自动探索）
python3 curious_agent.py --daemon --interval 30
```

### 5.3 API 接口

```bash
# 查询状态（含各模块状态）
curl http://localhost:4848/api/curious/state

# 触发一轮完整探索（含分解→评估→行为写入）
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"depth": "deep"}'

# 注入话题（会被自动分解）
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"metacognition","score":8.5,"depth":8.0}'

# v0.2.4 新增: R1D3 置信度查询
curl "http://localhost:4848/api/r1d3/confidence?topic=agent+memory"

# v0.2.4 新增: 查询已完成话题
curl http://localhost:4848/api/metacognitive/topics/completed

# v0.2.4 新增: 检查话题状态
curl "http://localhost:4848/api/metacognitive/check?topic=your_topic"

# v0.2.4 新增: 查询待探索队列
curl http://localhost:4848/api/curious/queue/pending

# v0.2.4 新增: 删除话题
curl -X DELETE http://localhost:4848/api/curious/queue \
  -H "Content-Type: application/json" \
  -d '{"topic":"过时话题"}'
```

---

## 六、技术栈与核心模块

| 组件 | 技术 | 说明 |
|------|------|------|
| **话题分解** | Python 3.11+ asyncio | CuriosityDecomposer, ProviderRegistry, ProviderHeatmap |
| **质量评估** | Python + LLM | QualityV2, CompetenceTracker, ThreePhaseExplorer |
| **行为闭环** | Python + Markdown | AgentBehaviorWriter, 行为规则生成 |
| **Spider引擎** | Python + 检查点机制 | SpiderEngine, SpiderRuntimeState, SpiderCheckpoint (v0.2.4) |
| **洞察合成** | Python + LLM | InsightSynthesizer, 跨话题模式发现, 假设生成 (v0.2.4) |
| **R1D3集成** | Python + REST API | R1D3ToolHandler, R1D3Sync, R1D3Watcher (v0.2.4) |
| **知识图谱** | Python | KGGraph, 多父节点支持, 高优先级未探索节点发现 (v0.2.4) |
| **存储层** | Repository模式 | JSONKnowledgeRepository, Topic模型, 迁移机制 (v0.2.4) |
| **基础层** | Flask 3.x | API + Web UI |
| **搜索** | Bocha + Serper | 双 Provider 验证架构 |
| **LLM** | minimax API | 语义评估、规则生成 |
| **前端** | Vanilla JS + D3.js | 知识图谱可视化 |
| **存储** | JSON + Markdown | state.json + 行为规则文件 + shared_knowledge/ (v0.2.4) |

---

## 七、核心概念详解

### 7.1 ICM 融合评分

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
├── curious_agent.py              # CLI 入口（集成所有能力）
├── curious_api.py                # Flask API + Web 服务器
├── spider_engine.py              # Spider Engine 主引擎 (v0.2.4)
├── run_curious.sh                # 一键启动脚本
├── core/
│   ├── curiosity_decomposer.py   # 话题分解引擎（四级级联验证）
│   ├── provider_registry.py      # Provider 注册中心
│   ├── provider_heatmap.py       # 覆盖率热力图
│   ├── quality_v2.py             # 信息增益质量评估
│   ├── competence_tracker.py     # 能力追踪器
│   ├── three_phase_explorer.py   # 三阶段探索循环
│   ├── agent_behavior_writer.py  # 行为规则生成
│   ├── knowledge_graph.py        # 知识图谱（含父子关系）
│   ├── curiosity_engine.py       # ICM 评分引擎
│   ├── explorer.py               # 分层探索器
│   ├── insight_synthesizer.py    # 洞察合成器 Layer 3 (v0.2.4)
│   ├── kg_graph.py               # KG Graph 结构管理 (v0.2.4)
│   ├── r1d3_watcher.py           # R1D3 学习需求监听 (v0.2.4)
│   ├── api/
│   │   └── r1d3_tools.py         # R1D3 Tool Handler (v0.2.4)
│   ├── sync/
│   │   └── r1d3_sync.py          # R1D3 双向同步 (v0.2.4)
│   ├── spider/
│   │   ├── state.py              # Spider 运行时状态 (v0.2.4)
│   │   └── checkpoint.py         # Spider 检查点机制 (v0.2.4)
│   ├── repository/
│   │   ├── base.py               # Repository 抽象基类 (v0.2.4)
│   │   └── json_repository.py    # JSON Repository 实现 (v0.2.4)
│   ├── models/
│   │   └── topic.py              # Topic 数据模型 (v0.2.4)
│   └── providers/                # Provider 插件目录
│       ├── bocha_provider.py
│       └── serper_provider.py
├── ui/
│   └── index.html                # Web UI（D3.js 力导向图）
├── knowledge/
│   └── state.json                # 持久化状态（含 competence_state）
├── shared_knowledge/             # 共享知识层 (v0.2.4)
│   ├── r1d3/learning_needs/      # R1D3 学习需求
│   ├── curious/                  # Curious Agent 发现
│   └── cross_validation/         # 交叉校验记录
├── tests/                        # 45+ 测试模块
│   ├── api/                      # API 测试
│   ├── core/                     # 核心模块测试
│   ├── spider/                   # Spider Engine 测试 (v0.2.4)
│   ├── repository/               # Repository 测试 (v0.2.4)
│   └── models/                   # 模型测试 (v0.2.4)
└── docs/
    └── plans/                    # 详细设计文档
```

---

## 九、更新日志

### v0.2.4 — R1D3集成与架构升级 (2026-03-26)

**🔗 R1D3双向集成**
- ✅ **R1D3ToolHandler**: Tool Call API支持，置信度查询(`curious_check_confidence`)，话题注入(`curious_agent_inject`)
- ✅ **R1D3Sync**: 发现双向同步机制，共享状态管理，`shared_knowledge/`统一存储层
- ✅ **R1D3Watcher**: 学习需求监听，命题扫描，自动触发探索
- ✅ **三大读写契约**: Learning Needs(输入)、Findings(输出)、Cross Validation(校验)

**🧠 InsightSynthesizer Layer 3**
- ✅ **跨话题洞察合成**: 自动发现子话题间的模式和关联
- ✅ **假设生成引擎**: 基于证据生成可验证的假设
- ✅ **置信度评估**: 多维置信度计算(0-1)，支持证据强度评估
- ✅ **结构化洞察输出**: Insight/Pattern/Hypothesis数据类定义

**🕸️ Spider Engine与状态管理**
- ✅ **SpiderEngine**: 自主探索主引擎，支持异步执行
- ✅ **SpiderRuntimeState**: 运行时状态管理
- ✅ **SpiderCheckpoint**: 检查点机制，支持崩溃恢复
- ✅ **SpiderConfig**: 统一配置管理

**💾 Repository模式重构**
- ✅ **JSONKnowledgeRepository**: Repository模式实现，支持Topic模型
- ✅ **Topic数据模型**: 规范化Topic结构，支持多父节点
- ✅ **迁移机制**: 旧state.json平滑迁移到新模型
- ✅ **KGGraph**: 知识图谱结构管理，支持`should_explore`四态返回

**🔄 架构改进**
- ✅ **shared_knowledge/统一层**: R1D3与Curious Agent共享知识目录结构
- ✅ **事件总线持久化**: EventBus持久化支持
- ✅ **惊喜检测**: SurpriseDetector，识别意外发现
- ✅ **推理压缩**: ReasoningCompressor，优化长推理链

**测试覆盖**: 45+ 测试模块，覆盖核心模块、API、Spider Engine、Repository层

---

### v0.2.3 — 完整能力落地 (2026-03-23)

**🧩 话题分解与验证**
- ✅ **CuriosityDecomposer**: 四级级联分解（LLM→Provider验证→KG补充→澄清）
- ✅ **双 Provider 架构**: Bocha + Serper，2+ 验证通过才保留，幻觉过滤 >90%
- ✅ **ProviderRegistry**: 单例模式，支持动态注册
- ✅ **ProviderHeatmap**: emergent 覆盖率热力图，自动发现各源优势领域
- ✅ **QualityGate**: 入队前过滤（黑名单/太短/相似度去重）

**🎯 元认知质量评估**
- ✅ **QualityV2**: 信息增益评估（语义新鲜度 + 置信度 delta + 图谱结构变化）
- ✅ **CompetenceTracker**: 能力追踪器，EMA 更新，缺口驱动探索
- ✅ **ThreePhaseExplorer**: MGV 循环（Monitor→Generate→Verify）
- ✅ **动态调度**: 能力缺口大的领域优先，动态 α 参数
- ✅ **指数衰减边际收益**: 自动检测探索价值衰减，及时停止

**🔄 行为闭环与自我进化**
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

_最后更新：2026-03-26 | v0.2.4_
_设计理念：**好奇驱动，主动探索，元认知调控，自我进化，以我为名**_

📄 **Release Notes**: [v0.2.4](./RELEASE_NOTE_v0.2.4.md) | [v0.2.3](./RELEASE_NOTE_v0.2.3.md) | [v0.2.2](./RELEASE_NOTE_v0.2.2.md) | [v0.2.1](./RELEASE_NOTE_v0.2.1.md) | [v0.2.0](./RELEASE_NOTE_v0.2.0.md)
