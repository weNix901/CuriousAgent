# 👁️ Curious Agent — 好奇探索器

> 一个具有**内在好奇心**的自主探索 Agent。不是等待用户提问，而是主动发现知识缺口、持续积累、主动分享。

[![Status](https://img.shields.io/badge/status-v0.2.1-blue)](#)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](#)
[![Release](https://img.shields.io/badge/release-v0.2.1-green)](./RELEASE_NOTE_v0.2.1.md)

---

## 一、设计初衷

**你有没有过这种感觉？**

- 问了一个 AI 问题，它答了，然后没了
- 它不会主动告诉你"其实这个领域我最近看到篇新论文..."
- 每次对话都是全新的，从零开始，没有任何积累
- 好的回答随会话消散，下次还得重新描述上下文

**传统 AI Agent 也是这样。**

它们像一台台应答机器——你敲一下，它动一下。不问、不好奇、不主动发现。关掉对话窗口，所有"知识"就消失了。

**但真正的智能不一样。**

想象一个会自己问问题的 Agent：
- 它知道你的研究兴趣
- 它会主动发现"这个方向我还不太清楚"，然后去查
- 它把每次探索的结果积累成自己的知识
- 它在合适的时机告诉你："哎，我最近好奇了一个东西，挺有意思..."

**这就是 Curious Agent 的设计初衷。**

不是工具，不是插件，是让 Agent 拥有**好奇心**——像人一样主动学、主动记、主动分享。

---

## 二、用户价值

> **"不用我去找，它会来找我。"**

这是 Curious Agent 能给你的最重要的事。

---

**如果你是一个研究者**

你不需要每天手动搜 arXiv、刷 Twitter、在十几个标签里找信号。Curious Agent 会持续盯着 AI Agent 领域的最新动态，发现有意思的东西会主动告诉你——不是 RSS 推送，是它用"我"的口吻分享它的好奇。

**如果你是一个开发者**

你想给 AI 加上"主动探索"能力，却不知道从哪里下手？Curious Agent 提供了一个完整的参考实现——评分算法、知识图谱、探索流程、UI 界面，全部开源，可以直接看、直接改、直接集成。

**如果你只是对 AI 好奇**

你告诉它你对什么感兴趣（比如"大模型幻觉"、"Agent 规划"），它会持续挖掘，每隔 30 分钟探索一个角落，定期汇报发现。像是雇了一个永不疲倦的实习生，专门帮你盯着这个领域。

---

| 你关心的是 | Curious Agent 给你的 |
|-----------|-------------------|
| 节省搜索时间 | 自动追踪最新论文和框架 |
| 知识不丢失 | 探索结果永久积累到知识图谱 |
| 有洞察才分享 | 不是机械推送，是"我有感而发才说" |
| 看得见摸得着 | Web 界面实时查看，透明可控 |
| 下一代 AI Agent | 开源参考实现，可改造、可集成 |

---

## 三、架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        用户 / R1D3                          │
│              (Web UI / 自然语言 / 飞书通知)                 │
└────────────────────────┬──────────────────────────────────┘
                         │
┌────────────────────────▼──────────────────────────────────┐
│                   好奇 Agent 系统                           │
│                                                             │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────┐       │
│  │  调度器   │──▶│  好奇心引擎  │──▶│   探索器    │       │
│  │Scheduler │   │Curiosity Eng│   │  Explorer   │       │
│  └──────────┘   └──────┬───────┘   └──────┬──────┘       │
│         │               │                  │              │
│         │               ▼                  ▼              │
│         │        ┌────────────────┐  ┌────────────┐       │
│         │        │  知识图谱      │  │  状态文件  │       │
│         │        │KnowledgeGraph │  │state.json  │       │
│         │        └────────────────┘  └────────────┘       │
│         │               │                               │
│         │               ▼                               │
│         │        ┌────────────────┐                      │
│         │        │  飞书通知 /    │                      │
│         │        │  Web UI       │                      │
│         │        └────────────────┘                      │
└─────────┼─────────────────────────────────────────────────┘
          │ 定时 Cron（每30分钟）
          ▼
    被 OpenClaw 主 Agent 内化
    → 探索结果融入长期记忆
    → 以"我"的口吻主动分享
```

---

## 四、核心原理

### 4.1 好奇心评分算法

```
Score = Relevance × 0.35 + Recency × 0.25 + Depth × 0.25 + Surprise × 0.15
```

| 维度 | 含义 | 计算方式 |
|------|------|---------|
| **Relevance** | 与用户兴趣的相关性 | 匹配关键词 +1.5/命中 |
| **Recency** | 遗忘效应 | 每24小时 +1 分，上限 10 |
| **Depth** | 知识缺口深度 | 直接使用，越深越想探索 |
| **Surprise** | 意外程度 | 图谱中越少相关节点越惊喜 |

### 4.2 探索执行流程

```
① 选择 Top 1 好奇心（评分最高）
         ↓
② Bocha Web Search → 获取搜索结果
         ↓ (无结果)
③ 深度推理 → 基于已有知识推导
         ↓
④ 综合发现 → 生成摘要
         ↓
⑤ 判断通知 → 分数 ≥ 7 → 飞书推送 + 写入发现库
         ↓
⑥ 更新知识图谱 → 状态 → done
         ↓
⑦ 下一轮循环（30分钟后）
```

### 4.3 知识图谱状态模型

```json
{
  "knowledge": {
    "topics": {
      "topic_name": {
        "known": true,
        "depth": 8,           // 理解深度 0-10
        "last_updated": "ISO",
        "summary": "...",
        "sources": ["url1", "url2"]
      }
    }
  },
  "curiosity_queue": [
    {
      "topic": "metacognition AI",
      "score": 8.5,
      "reason": "理解用户研究方向",
      "status": "pending|investigating|done"
    }
  ],
  "exploration_log": [...]
}
```

---

## 五、使用方式

### 5.1 Web 界面（推荐）

```bash
cd /root/dev/curious-agent
python3 curious_api.py
# 🌐 http://10.1.0.13:4849/
```

**界面功能**：
- 📊 状态面板（知识节点/待探索/历史）
- 🔥 好奇心队列（评分可视化，点击查看详情）
- 📚 知识图谱（点击查看完整摘要和来源链接）
- 📋 探索历史（点击查看完整发现）
- ➕ 注入新好奇心（话题/相关性/深度/原因）
- ⚡ 快捷探索按钮
- ▶ 一键运行探索
- 💬 控制台日志

**图谱可视化**：
- 🔮 独立图谱视图（Tab 切换），全屏 D3.js 力导向图
- 🔴🟡🟢 节点颜色按理解深度区分（红=深度8-10，黄=5-7，绿=1-4）
- ⭕ 节点大小按深度成比，白边 = 当前待探索队列中的话题
- 🔗 连线 = 主题之间存在共同关键词，粗细反映相关强度
- 🖱️ 支持拖拽节点、滚轮缩放、点击节点查看详情弹窗
- ⚡ 控制台共享，两个视图均可见

### 5.2 命令行

```bash
# 查看状态
python3 curious_agent.py --status

# 运行一轮探索
python3 curious_agent.py --run

# 守护进程（每30分钟自动探索）
python3 curious_agent.py --daemon

# 注入新好奇心
python3 curious_agent.py --inject "transformer attention" \
    --score 8.0 --depth 7.0 --reason "用户注入"
```

### 5.3 API

```bash
# 查看状态
curl http://10.1.0.13:4849/api/curious/state

# 运行探索
curl -X POST http://10.1.0.13:4849/api/curious/run

# 注入好奇心
curl -X POST http://10.1.0.13:4849/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"smolagents","relevance":9,"depth":8,"reason":"调研极简Agent框架"}'
```

### 5.4 定时探索（Cron）

```bash
# 编辑 crontab
crontab -e
# 添加：每30分钟运行一次
*/30 * * * * cd /root/dev/curious-agent && python3 curious_agent.py --run >> logs/curious.log 2>&1
```

---

## 六、与主 Agent 的集成

Curious Agent 已**内化为 OpenClaw 主 Agent 的能力模块**：

| 层次 | 实现 |
|------|------|
| **感知层** | `sync_discoveries.py` 每次心跳同步新发现 |
| **记忆层** | 探索结果写入 `memory/curious-discoveries.md` |
| **意识层** | SOUL.md 声明好奇探索是核心特质 |
| **行动层** | 以"我"的口吻主动分享 + 对话中自然引用 |

**主 Agent 的主动行为规范**：
- 读取发现库，找到最新/最有价值的探索结果
- 以"我"的口吻主动分享："我最近好奇了 X，有几个有意思的发现..."
- 对话中遇到相关话题，自然引用探索结论
- 发现是我的想法，不做机械推送

---

## 七、项目结构

```
curious-agent/
├── curious_agent.py           # CLI 入口
├── curious_api.py            # 🌐 Flask API + Web 服务器
├── core/
│   ├── knowledge_graph.py    # 知识图谱 + 持久化（JSON）
│   ├── curiosity_engine.py   # 好奇心引擎（评分算法）
│   ├── explorer.py           # 探索器（分层架构）
│   ├── arxiv_analyzer.py     # 📄 Layer 2: arXiv 论文分析
│   └── llm_client.py         # 🤖 Layer 3: minimax LLM 客户端
├── ui/
│   └── index.html           # 🌐 单页 Web 界面
├── knowledge/
│   └── state.json           # 持久化状态
├── logs/
│   └── curious.log          # 运行日志
├── tests/
│   ├── test_cli.py          # CLI 测试
│   ├── test_explorer_layers.py  # 分层探索测试
│   ├── test_arxiv_analyzer.py   # arXiv 分析测试
│   ├── test_llm_client.py       # LLM 客户端测试
│   ├── test_integration.py      # 集成测试
│   ├── test_auto_queue.py       # 自动入队测试
│   └── test_e2e.py              # E2E 测试
├── docs/                    # 详细文档
│   ├── 01-调研报告.md       # 元认知理论 + 7框架调研
│   ├── 02-设计文档.md       # 架构 + 算法 + 接口设计
│   ├── 03-实现指南.md       # 代码解读 + 调试技巧
│   ├── 04-OpenCode完善指南.md  # 面向开发者的增强路径
│   └── 05-版本路线图.md     # v0.1 → v1.0 里程碑
└── run_exploration.sh       # Cron 任务脚本
```

---

## 八、技术栈

- **语言**: Python 3.11+
- **Web 框架**: Flask 3.x
- **前端**: Vanilla JS + D3.js v7（零依赖，单 HTML 文件）
- **可视化**: D3.js 力导向图（Force-Directed Graph）
- **搜索**: Bocha Search API（`/v1/web-search`）
- **论文分析**: arxiv 库 + PyPDF2
- **LLM**: minimax API（`minimax-m2.7` 模型）
- **持久化**: JSON（v0.1）→ SQLite（v0.2 计划）
- **定时**: Cron

---

## 九、v0.2 新特性

### 分层探索 (Layered Exploration)

支持三种探索深度，适应不同场景需求：

| 深度 | 层级 | 耗时 | 适用场景 |
|------|------|------|---------|
| `shallow` | Layer 1: Web Search | <30秒 | 快速了解、初步调研 |
| `medium` | Layer 1 + Layer 2: arXiv 分析 | 3-5分钟 | 深入研究、论文追踪 |
| `deep` | Layer 1 + Layer 2 + Layer 3: LLM 洞察 | 10-15分钟 | 全面分析、跨论文对比 |

**CLI 使用：**
```bash
# 快速探索
python3 curious_agent.py --run --run-depth shallow

# 中等深度（默认）
python3 curious_agent.py --run --run-depth medium

# 深度探索
python3 curious_agent.py --run --run-depth deep
```

**Layer 说明：**
- **Layer 1 (Web Search)**: 调用 Bocha Search API，获取网页结果，提取 arXiv 链接
- **Layer 2 (arXiv 分析)**: 下载论文元数据，计算相关性评分，提取关键发现
- **Layer 3 (LLM 洞察)**: 使用 minimax API 生成跨论文对比分析、趋势观察、研究建议

### 主动触发系统 (Active Trigger)

支持多种触发方式，实现主动探索：

**1. API 触发**
```bash
# 触发探索（后台异步执行）
curl -X POST http://10.1.0.13:4849/api/curious/trigger \
  -H "Content-Type: application/json" \
  -d '{"topic":"knowledge graph embedding","depth":"deep"}'

# 响应
{
  "status": "accepted",
  "topic": "knowledge graph embedding",
  "depth": "deep",
  "estimated_time": "10-15分钟"
}
```

**2. 定时触发**
- 早安探索 (9:00): 每日知识更新
- 晚安探索 (21:00): 当日发现总结

### 自动入队 (Auto-Queue)

从探索发现中自动提取关键词，加入好奇心队列：

- 探索完成后自动分析 findings
- 提取学术关键词（大写短语、专业术语）
- 去重后加入待探索队列
- 仅在 medium/deep 深度启用

**示例流程：**
```
探索 "knowledge graph embedding"
  ↓
发现关键词: TransE, RotatE, Neural Networks
  ↓
自动入队: ["TransE algorithm", "RotatE method", "Neural Networks for KG"]
  ↓
下一轮自动探索这些新话题
```

---

## 十、v0.2.1 新特性

### ICM 融合评分机制

引入 **Intrinsic Curiosity Module** 启发式评分，让 Agent 能够自主评估话题的探索价值：

```
FinalScore = HumanScore × α + IntrinsicScore × (1 - α)
```

**三个内在信号（LLM 评估）**：
- **预测误差**: 当前对该话题的理解程度
- **图谱密度**: 知识网络中的位置重要性  
- **新颖性**: 与已知知识的语义重叠度

**用户控制**:
```bash
# 偏重人工意图 (70%)
python3 curious_agent.py --inject "topic" --motivation human

# 偏重自主探索 (30%)
python3 curious_agent.py --inject "topic" --motivation curious

# 纯探索模式 (0%)
python3 curious_agent.py --run --pure-curious
```

### Bug 修复与增强

| 修复项 | 改进 |
|--------|------|
| F1 队列删除 | `--delete`, `--force`, `--list-pending` 参数 |
| F2 Layer 3 触发 | 修复 depth 参数传递，触发率从 2% → 20-30% |
| F3 关键词过滤 | 停用词表 + 语义检查，噪音率 73% → <5% |
| F4 启动脚本 | `run_curious.sh` 一键干净启动 |
| F5 ArXiv 容错 | 超时重试 + fallback，成功率 20% → 60%+ |

---

## 十一、已探索的知识

当前知识图谱覆盖领域：

| 主题 | 分数 | 来源 |
|------|------|------|
| openclaw agent framework capabilities | 8.5 | 自主推理 |
| ReAct Reflexion agent frameworks | 8.1 | arXiv:2504.04650 |
| OMO multi-agent orchestration | 8.1 | arXiv:2601.04861 |
| LLM self-reflection mechanisms | 7.9 | arXiv:2401.02009 |
| working memory AI agent | 8.0 | 博客园 / CSDN |
| smolagents huggingface | 8.2 | HuggingFace 官方 |
| autonomous agent planning | 7.8 | 多篇论文 |
| curiosity-driven reinforcement learning | 7.8 | 博客园 |

---

_最后更新: 2026-03-20 | v0.2.1_

📄 **Release Notes**: [v0.2.1 Release Note](./RELEASE_NOTE_v0.2.1.md) | [v0.2.0 Release Note](./RELEASE_NOTE_v0.2.0.md)

_设计理念：好奇驱动，主动探索，以我为名_

**v0.2.1 更新日志：**
- ✅ ICM 融合评分机制（IntrinsicScorer 模块）
- ✅ LLM 主导信号评估（pred_error/graph_density/novelty）
- ✅ α 参数全接口支持（CLI/API/Web UI）
- ✅ F1-F5 Bug 修复（队列删除/Layer 3触发/关键词过滤/启动脚本/ArXiv容错）

**v0.2 更新日志：**
- ✅ 分层探索架构 (shallow/medium/deep)
- ✅ arXiv 论文分析集成
- ✅ minimax LLM 洞察生成
- ✅ API 触发端点 (`/api/curious/trigger`)
- ✅ 自动入队功能
- ✅ E2E 测试覆盖
