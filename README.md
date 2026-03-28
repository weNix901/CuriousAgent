# 👁️ Curious Agent — 会自我进化的知识图谱探索器

> 不是等待提问的搜索引擎，而是**主动构建知识图谱**、**持续追踪知识缺口**、**把发现内化为行为**的自主 Agent。
> 把 Curious Agent 接入你的 AI，它就变成了你的数字研究伙伴——越用越懂你，越探索越聪明。

[![Status](https://img.shields.io/badge/status-v0.2.5-blue)](#)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](#)
[![OpenClaw](https://img.shields.io/badge/openclaw-2026.3+-green)](#)
[![Tests](https://img.shields.io/badge/tests-45%20modules-brightgreen)](#)

---

## 一、它不只是搜索，而是会织网的探索者

**你用过多少次 AI 搜索，每次都像在沙漠里挖水？**

问一次，出一堆链接，关掉窗口，下次再问——**每次从零开始，从不记得上次挖到过什么。**

搜索只是挖坑，而 Curious Agent 在**织网**。

```
你问它: "帮我研究一下 agent memory"
    ↓
它没有立刻去搜
    ↓
它先想: "这个话题上次探索到哪里了？
         我现在懂多少？不懂多少？
         从哪里切入最能补上我的知识缺口？"
    ↓
它规划: "从 agent memory → metacognitive monitoring → self-reflection"
         （不是随机关键词，是一条知识路径）
    ↓
蜘蛛引擎启动，沿着这条路径自主探索
         节点越来越多 → 图谱越来越大 → 知识越来越深
    ↓
探索完成后，你的 AI 里多了一张知识网
         不是十条摘要，是一张有结构的图
         agent memory 在这里，self-reflection 在那里，中间怎么连的，一目了然
```

**最大的区别：**

普通 AI 的知识是**散的**，每次搜索都是独立的点。

Curious Agent 的知识是**织出来的网**——探索越多，网越密，越能发现那些"两个完全不同方向居然共享同一个底层机制"。

---

## 二、它有三项"超能力"

### 🕸️ 超能力一：像蜘蛛一样织网，不是像锄头一样挖坑

**传统 AI 搜索** = 锄头模式：
- 你挖一下，它动一下
- 挖完就完，网还是那张网

**Curious Agent** = 蜘蛛织网：
- 它会自己找到知识之间的连接点
- 每个发现都自动写入知识图谱
- 新发现和老发现之间自动建立关联
- 下次探索时，会先看这张网，找到真正缺的地方下手

```
锄头挖的:  agent memory → 10条摘要（各自独立）
蜘蛛织的:  agent memory
              ├── short-term memory
              │      ├── working memory capacity ← 刚探索到，有新连线
              │      └── episodic buffer
              └── long-term memory
                     └── metacognitive monitoring ← 新发现！
                            └── self-reflection ← 深入到这里了

两条完全独立的发现方向，在"元认知"这个节点上汇聚了。
这就是织网的价值。
```

**你问它任何问题，它都在用整张网回答，不是在用单次搜索的结果。**

---

### 📈 超能力二：知道该探索什么，不该探索什么

**普通 AI 的探索是盲目的** — 同一个话题搜10遍，从不觉得腻。

**Curious Agent 有元认知监控** — 它知道：

```
话题: "chain-of-thought"
├── 我已经探索过 3 次了
├── 每次质量都在下降（8.5 → 7.8 → 6.2）
├── 边际收益已经很低了
└── 结论: 停，去探索别的

话题: "self-reflection in LLM agents"
├── 我完全没接触过这个方向
├── 置信度只有 0.3
├── 知识图谱上这里几乎是空白
└── 结论: 这是我的知识缺口，优先探索！
```

**它不是什么都搜，是专门搜自己不懂的。** 而且探索过程中，它会持续评估"这次探索值不值"——不值就立刻停，把精力花在刀刃上。

---

### 🔄 超能力三：把发现变成自己的行为，不只是记笔记

这是最不一样的地方。

大多数 AI "学到"的东西，就躺在数据库里，下次遇到还是一脸茫然。

Curious Agent 学到东西之后，会做一件事：**写成行为规则，内化到自己的能力里。**

```
它探索时发现:
"在复杂推理任务中，评估自己的置信度再回答，准确率提升 23%。"
    ↓
它不会说"好的已存入知识库"然后忘掉
    ↓
它把这个发现变成行为规则:
    ## 🪞 Monitor-Generate-Verify 框架（已内化）
    
    遇到复杂问题时，我必须：
    1. 先评估自己有多大把握（1-10 分）
    2. 把握不足 6 分时，明确告诉对方我不确定
    3. 回答完检查有没有漏掉问题的关键部分
    
    来源: arXiv:2510.16374
    ↓
以后每次遇到复杂推理，它都会自动调用这个框架
    不需要你提醒，不需要检索，它已经"会了"
```

**这就是进化：今天的它比昨天真的更聪明了，不是因为存了更多数据，而是因为它把知识变成了能力。**

---

## 三、这四个特点，让它从工具变成了伙伴

### 🔥 特点一：接入你的 AI，它就成了你的数字分身

Curious Agent 不是单独存在的。它通过 `shared_knowledge/` 双向同步接口接入你的主 AI（比如 R1D3）：

```
R1D3 问: "metacognitive monitoring 是什么？"
    ↓
R1D3 不知道，但 Curious Agent 可能探索过
    ↓
R1D3 调用 curious_check_confidence("metacognitive monitoring")
    → 返回置信度 + 最近探索质量
    ↓
R1D3 决定: 置信度低 → 请 Curious Agent 先探索
    ↓
探索完成后，结果写回 shared_knowledge/
    ↓
R1D3 读到新发现，用这个知识回答用户
    ↓
R1D3 告诉用户: "我刚研究过这个，有个重要框架..."
```

** Curious Agent 在后台默默织网，你的 AI 在前台帮你回答——它越探索，你的 AI 就越懂这些问题。**

---

### 🧠 特点二：知识像树一样生长，不是像列表一样堆积

传统 AI 的知识是列表：新发现append在最后，旧发现被淹没。

Curious Agent 的知识是**树状结构**：

```
你注入一个话题: "agent"
    ↓
分解: agent memory, agent planning, multi-agent...
    ↓
每个子话题继续分解
    ↓
树越长越大，枝干之间开始产生连接
    ↓
"哦，metacognitive monitoring 是 agent planning 和 agent memory 的共同上游"
"self-reflection 同时连接了 planning 和 learning 两个分支"
    ↓
这些跨枝干的连接，是纯搜索永远发现不了的洞察
```

**树状结构让"理解"成为可能。列表只能存储，结构才能推理。**

---

### 🎯 特点三：知道什么时候停，不钻牛角尖

```
第 1 次探索: 质量 8.5 — 大有收获
第 2 次探索: 质量 7.8 — 还能挖点
第 3 次探索: 质量 6.2 — 边际收益很低了

Curious Agent 判断:
"这个话题的探索价值已经很低了。
 我还有很多空白区域要去填补，把精力花在刀刃上。"
 → 自动停止，跳转下一个知识缺口
```

**不是搜索引擎那种"你搜多少我给你多少结果"，而是真正的研究员的判断力：知道什么时候够了，什么时候该换方向。**

---

### 🛡️ 特点四：发现质量不够，绝不污染知识图谱

Curious Agent 有严格的质量门控：

```
探索完成 → 质量评估
    ↓
质量 ≥ 7.0 ?  → YES → 写入行为规则 + 知识图谱 + shared_knowledge
              ↓ NO  → 静默丢弃，不污染知识库
```

不是所有发现都有资格被记住。只有**真正有价值的发现**才会进入知识图谱和共享知识层。

**这保证了接入 Curious Agent 的 AI，拿到的都是经过筛选的高质量洞察，不是搜索结果的大杂烩。**

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
│  │                    Curious Agent v0.2.5                          │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │              核心能力层                                  │   │  │
│  │  │  • 话题分解引擎: LLM推理 + 多Provider验证 + 幻觉过滤     │   │  │
│  │  │  • 质量评估系统: 信息增益 + 置信度追踪 + 边际收益建模     │   │  │
│  │  │  • 能力调度器: 缺口驱动 + 动态调度 + 三阶段探索          │   │  │
│  │  │  • 行为写入器: 质量门槛 + 安全设计 + 双写机制            │   │  │
│  │  │  • InsightSynthesizer: 跨话题洞察合成 + 假设生成         │   │  │
│  │  │  • KG根技术追溯: 扩散激活算法 + 根技术池 + 因果链路      │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │              基础能力层                                  │   │  │
│  │  │  ICM评分 · 好奇心队列 · 知识图谱 · Spider引擎 · 事件总线  │   │  │
│  │  │  SpiderEngine · KGGraph · R1D3Watcher · 检查点机制      │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │              R1D3集成层 (v0.2.4新增)                      │   │  │
│  │  │  • R1D3ToolHandler: 置信度查询 + 话题注入 + 优先级队列   │   │  │
│  │  │  • R1D3Sync: 发现双向同步 + 共享状态管理                 │   │  │
│  │  │  • R1D3Watcher: 学习需求监听 + 命题扫描                  │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │              KG根技术追溯层 (v0.2.5新增)                   │   │  │
│  │  │  • 扩散激活算法: Collins & Loftus 激活传播模型         │   │  │
│  │  │  • 根技术池: 跨领域根技术浮现 + root_score 排序        │   │  │
│  │  │  • 因果链路: 从任意知识点追溯根技术的激活路径           │   │  │
│  │  │  • Cross-Subgraph: 多路径汇聚检测根技术                │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**数据流：从发现到行为改变 (v0.2.5)**

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
[扩散激活追溯] → 从发现追溯根技术 → 生成因果链路
    ↓
[根技术池更新] → 跨域连接累计 → 根技术浮现
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
- 🌐 Web UI：http://0.0.0.0:4849/
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

# v0.2.5 新增: KG根技术追溯
curl "http://localhost:4848/api/kg/trace/metacognitive%20monitoring"

# v0.2.5 新增: 查询根技术池
curl http://localhost:4848/api/kg/roots

# v0.2.5 新增: KG全局视图
curl http://localhost:4848/api/kg/overview

# v0.2.5 新增: 手动升权根候选
curl -X POST http://localhost:4848/api/kg/promote \
  -H "Content-Type: application/json" \
  -d '{"topic":"your_topic","domains":["LLM","RL"]}'
```

---

## 六、技术栈与核心模块

| 组件 | 技术 | 说明 |
|------|------|------|
| **话题分解** | Python 3.11+ asyncio | CuriosityDecomposer, ProviderRegistry, ProviderHeatmap |
| **质量评估** | Python + LLM | QualityV2, CompetenceTracker, ThreePhaseExplorer |
| **行为闭环** | Python + Markdown | AgentBehaviorWriter, 行为规则生成 |
| **Spider引擎** | Python + 检查点机制 | SpiderEngine, SpiderRuntimeState, SpiderCheckpoint |
| **洞察合成** | Python + LLM | InsightSynthesizer, 跨话题模式发现, 假设生成 |
| **KG根技术追溯** | Python | 扩散激活算法, 根技术池, 因果链路追溯 (v0.2.5) |
| **R1D3集成** | Python + REST API | R1D3ToolHandler, R1D3Sync, R1D3Watcher |
| **知识图谱** | Python | KGGraph, 多父节点支持, 高优先级未探索节点发现 |
| **存储层** | Repository模式 | JSONKnowledgeRepository, Topic模型, 迁移机制 |
| **基础层** | Flask 3.x | API + Web UI |
| **搜索** | Bocha + Serper | 双 Provider 验证架构 |
| **LLM** | minimax API | 语义评估、规则生成 |
| **前端** | Vanilla JS + D3.js | 知识图谱可视化 |
| **存储** | JSON + Markdown | state.json + 行为规则文件 + shared_knowledge/ |

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
├── spider_engine.py              # Spider Engine 主引擎
├── run_curious.sh                # 一键启动脚本
├── core/
│   ├── curiosity_decomposer.py   # 话题分解引擎（四级级联验证）
│   ├── provider_registry.py      # Provider 注册中心
│   ├── provider_heatmap.py       # 覆盖率热力图
│   ├── quality_v2.py             # 信息增益质量评估
│   ├── competence_tracker.py     # 能力追踪器
│   ├── three_phase_explorer.py   # 三阶段探索循环
│   ├── agent_behavior_writer.py  # 行为规则生成
│   ├── knowledge_graph.py        # 知识图谱（含父子关系 + 根技术追溯）
│   ├── curiosity_engine.py       # ICM 评分引擎
│   ├── explorer.py               # 分层探索器
│   ├── insight_synthesizer.py    # 洞察合成器 Layer 3
│   ├── kg_graph.py               # KG Graph 结构管理（Repository 封装）
│   ├── r1d3_watcher.py          # R1D3 学习需求监听
│   ├── reasoning_compressor.py   # 推理压缩器
│   ├── surprise_detector.py      # 惊喜检测器
│   ├── discovery_writer.py       # 发现写入器
│   ├── api/
│   │   └── r1d3_tools.py         # R1D3 Tool Handler
│   ├── sync/
│   │   └── r1d3_sync.py         # R1D3 双向同步
│   ├── spider/
│   │   ├── state.py              # Spider 运行时状态
│   │   └── checkpoint.py         # Spider 检查点机制
│   ├── repository/
│   │   ├── base.py              # Repository 抽象基类
│   │   └── json_repository.py    # JSON Repository 实现
│   ├── models/
│   │   └── topic.py             # Topic 数据模型
│   └── providers/               # Provider 插件目录
│       ├── bocha_provider.py
│       └── serper_provider.py
├── scripts/
│   ├── migrate_kg_parents.py    # v0.2.5 KG schema 迁移脚本
│   └── sync_kg_to_r1d3.py       # v0.2.5 KG→R1D3 同步脚本
├── ui/
│   └── index.html                # Web UI（D3.js 力导向图）
├── knowledge/
│   └── state.json               # 持久化状态（含 competence_state）
├── shared_knowledge/            # 共享知识层
│   ├── r1d3/learning_needs/    # R1D3 学习需求
│   ├── curious/                 # Curious Agent 发现
│   └── cross_validation/        # 交叉校验记录
├── tests/                       # 45+ 测试模块
│   ├── api/                    # API 测试
│   ├── core/                   # 核心模块测试
│   ├── spider/                 # Spider Engine 测试
│   ├── repository/             # Repository 测试
│   └── models/                 # 模型测试
└── docs/
    ├── curious-agent-installation-guide.md  # 接入手册
    ├── 参考架构设计.md          # 架构参考设计
    └── plans/                  # 详细设计文档
```

---

## 九、更新日志

### v0.2.5 — KG根技术追溯能力 (2026-03-28)

**🌐 KG根技术追溯**
- ✅ **扩散激活算法**: Collins & Loftus 激活传播模型，从任意知识点追溯根技术
- ✅ **根技术池**: 跨领域根技术浮现，root_score 排序，初始种子注入
- ✅ **因果链路**: `get_spreading_activation_trace()` 返回激活路径和根技术列表
- ✅ **Cross-Subgraph检测**: 多路径汇聚自动识别根候选（paths >= 2）
- ✅ **根技术池初始化**: `init_root_pool(seeds)` 支持 6 个初始种子

**📊 Topic Schema 扩展**
- ✅ **parents字段**: List[str]，记录 topic 的父节点
- ✅ **explains字段**: List[dict]，记录 topic 解释了哪些子节点
- ✅ **cross_domain_count**: 跨域计数，触发根候选升权
- ✅ **is_root_candidate / root_score**: 根候选标记和评分
- ✅ **first_observed**: 首次观察时间戳

**🔗 双向父子关系写入**
- ✅ **_update_parent_relation()**: 内部函数，双向写入 parents + explains
- ✅ **add_child() 集成**: 末尾追加 `_update_parent_relation()` 调用
- ✅ **mark_topic_done() 集成**: 末尾追加父 topic 查找逻辑

**🛠️ 新增脚本**
- ✅ **scripts/migrate_kg_parents.py**: v0.2.4 → v0.2.5 schema 迁移
- ✅ **scripts/sync_kg_to_r1d3.py**: KG 数据同步到 R1D3 可读格式（trace/roots/overview）

**📡 新增API端点**
- ✅ `GET /api/kg/trace/<topic>`: 扩散激活追溯，返回因果链路
- ✅ `GET /api/kg/roots`: 查询根技术池
- ✅ `GET /api/kg/overview`: KG 全局视图（节点+边）
- ✅ `POST /api/kg/promote`: 手动升权根候选

**🔔 事件总线增强**
- ✅ 新增事件类型: `root_candidate_elevated`

---

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

_最后更新：2026-03-28 | v0.2.5_
_设计理念：**好奇驱动，主动探索，元认知调控，自我进化，以我为名**_

📄 **Release Notes**: [v0.2.4](./RELEASE_NOTE_v0.2.4.md) | [v0.2.3](./RELEASE_NOTE_v0.2.3.md) | [v0.2.2](./RELEASE_NOTE_v0.2.2.md) | [v0.2.1](./RELEASE_NOTE_v0.2.1.md) | [v0.2.0](./RELEASE_NOTE_v0.2.0.md)
