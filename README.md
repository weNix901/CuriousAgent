# 👁️ Curious Agent — 好奇探索器

> 一个具有**内在好奇心**的自主探索 Agent。不是等待用户提问，而是主动发现知识缺口、持续积累、在合适时机主动分享。

[![Status](https://img.shields.io/badge/status-v0.2.1-blue)](#)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](#)
[![OpenClaw](https://img.shields.io/badge/openclaw-2026.3+-green)](#)

---

## 一、解决的问题

**传统 AI Agent 是应答机器：**

```
用户提问 → Agent 回答 → 会话结束 → 下次从零开始
```

没有问题就没有行动，没有上下文就没有积累。关掉对话窗口，所有"知识"就消失了。

**Curious Agent 的改变：**

```
无用户输入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  ICM 内在好奇心模块（持续运行）                               │
│                                                             │
│  IntrinsicScore = pred_error × 0.4                         │
│                 + graph_density × 0.3                       │
│                 + novelty × 0.3                             │
│                                                             │
│  • pred_error ↑    → 预测不准 → 需要探索                   │
│  • graph_density ↓ → 知识孤岛 → 需要连接                   │
│  • novelty ↑       → 全新领域 → 值得发现                   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
主动探索循环 → 知识积累 → 择机分享
```

**这就是"主动思考"的本质** — 不是等待问题，而是内在动机驱动地发现和积累。

---

## 二、核心概念

### ICM 融合评分

Curious Agent v0.2.1 引入 ICM（Intrinsic Curiosity Module），融合人工意图和内在动机：

```
FinalScore = HumanScore × α + IntrinsicScore × (1 - α)
```

**两个评分来源：**

| 评分来源 | 组成 | 说明 |
|---------|------|------|
| **HumanScore** | Relevance×0.35 + Recency×0.25 + Depth×0.25 + Surprise×0.15 | 人工设计的评分 |
| **IntrinsicScore** | pred_error×0.4 + graph_density×0.3 + novelty×0.3 | LLM 评估的内在信号 |

**三个内在信号（由 LLM 评估）：**

| 信号 | 含义 | 高分意味着 |
|------|------|-----------|
| **pred_error** | 预测误差 | 我们对这个话题的理解误差越大，越值得探索 |
| **graph_density** | 图谱密度 | 知识网络中连接越少（越孤立），越值得探索 |
| **novelty** | 新颖性 | 与已知知识重叠越少，越新鲜，越值得探索 |

**α 参数控制**（用户可配置）：

| α 值 | 模式 | 说明 |
|------|------|------|
| `α = 1.0` | 纯人工 | 完全按人工设定的优先级探索 |
| `α = 0.7` | human | 偏重人工意图（`--motivation human`） |
| `α = 0.5` | fusion | 平衡模式（默认） |
| `α = 0.3` | curious | 偏重自主探索（`--motivation curious`） |
| `α = 0.0` | pure-curious | 纯探索模式（`--pure-curious`） |

### 分层探索架构

探索执行分三个深度层次：

| 深度 | 层级 | 耗时 | 输出 |
|------|------|------|------|
| `shallow` | Layer 1: Web Search | <30秒 | 搜索结果摘要 + 来源 |
| `medium` | Layer 1 + Layer 2: arXiv 分析 | 3-5分钟 | 论文相关性评分 + 关键发现 |
| `deep` | Layer 1 + Layer 2 + Layer 3: LLM 洞察 | 10-15分钟 | 跨论文对比 + 趋势分析 + 研究建议 |

```
话题入选 Top 1
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Web Search                                    │
│  → Bocha Search API → 提取标题/摘要/链接               │
│  → 提取 arXiv 链接（供 Layer 2 使用）                  │
└────────────────────────────┬────────────────────────────┘
                             │ 有 arXiv 链接 + depth ≥ medium
                             ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: arXiv 分析                                    │
│  → 获取论文元数据 → 计算相关性评分                      │
│  → 提取关键发现和来源链接                              │
│  → 相关性 ≥ 0.3 → 进入 Layer 3                        │
└────────────────────────────┬────────────────────────────┘
                             │ depth = deep + 论文 ≥ 1 篇
                             ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 3: LLM 洞察（minimax API）                      │
│  → 跨论文对比分析                                      │
│  → 趋势观察                                            │
│  → 研究建议                                            │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
              探索结果 → state.json + 通知标记
```

---

## 三、系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        用户 / 飞书 / Discord                        │
└────────────────────────────┬───────────────────────────────────┘
                             │ 主动分享 / 被动查询
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                      OpenClaw 主 Agent                             │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────────┐   │
│  │  感知层   │──▶│   记忆层     │──▶│      行动层           │   │
│  │ sync_disc│   │ curious-disc │   │  主动分享 + 引用      │   │
│  └──────┬───┘   └──────────────┘   └──────────────────────┘   │
│         │                                                        │
│         │ 心跳同步 (每30秒)                                      │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Curious Agent（独立进程）                      │   │
│  │                                                          │   │
│  │  ┌───────────┐  ┌────────────┐  ┌───────────────────┐  │   │
│  │  │ 好奇心队列 │  │  知识图谱   │  │   探索器 Explorer  │  │   │
│  │  │ ICM 评分  │  │ state.json │  │  L1/L2/L3 分层探索 │  │   │
│  │  └───────────┘  └────────────┘  └───────────────────┘  │   │
│  │                                                          │   │
│  │  ┌───────────┐  ┌────────────┐  ┌───────────────────┐  │   │
│  │  │ ArXiv 分析│  │  LLM 洞察  │  │   Web Search      │  │   │
│  │  └───────────┘  └────────────┘  └───────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

** Curious Agent 和 OpenClaw 的双向交互：**

| 方向 | 触发条件 | 数据 |
|------|---------|------|
| **OpenClaw → Curious Agent** | 用户提到话题 / Agent 发现兴趣 | API 调用注入好奇心 |
| **Curious Agent → OpenClaw** | 探索完成 + 评分 ≥ 7.0 | 同步到 memory/curious-discoveries.md |
| **OpenClaw → 用户** | 对话中自然提到 / 用户主动问 | 以"我"的口吻分享发现 |

---

## 四、快速开始

### 4.1 启动服务

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

### 4.2 命令行使用

```bash
# 注入新话题
python3 curious_agent.py --inject "metacognition AI" \
  --score 8.5 --depth 8.0 --reason "用户研究兴趣"

# 运行一轮探索
python3 curious_agent.py --run

# 指定深度
python3 curious_agent.py --run --run-depth deep

# 查看状态
python3 curious_agent.py --status

# 查看待探索队列
python3 curious_agent.py --list-pending

# 删除过时话题
python3 curious_agent.py --delete "过时话题"

# 守护进程模式（每30分钟自动探索）
python3 curious_agent.py --daemon --interval 30
```

### 4.3 API 接口

```bash
# 查询状态
curl http://localhost:4848/api/curious/state

# 触发一轮探索
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"depth": "medium"}'

# 注入话题
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"smolagents","score":8.5,"depth":8.0,"reason":"调研极简框架"}'

# 查询待探索队列
curl http://localhost:4848/api/curious/queue/pending

# 删除话题
curl -X DELETE "http://localhost:4848/api/curious/queue?topic=过时话题"
```

### 4.4 定时探索（Cron）

```bash
# 每4小时深度探索一次
openclaw cron add \
  --name "Curious Agent 深度探索" \
  --cron "0 */4 * * *" \
  --session isolated \
  --message "cd /root/dev/curious-agent && python3 curious_agent.py --run --run-depth deep" \
  --announce --target last
```

---

## 五、与 OpenClaw 集成

### 5.1 集成原理

Curious Agent 已**内化为 OpenClaw 主 Agent 的能力模块**，形成完整的"感知-记忆-行动"闭环：

| 层次 | 组件 | 职责 |
|------|------|------|
| **感知层** | `sync_discoveries.py` | 每30秒读取 exploration_log，过滤 `notified_user=true` |
| **记忆层** | `memory/curious-discoveries.md` | 持久化发现库，可被 `memory_search()` 检索 |
| **意识层** | `SOUL.md` | 定义好奇特质 — "我是一个有好奇心的 Agent" |
| **行动层** | 主动分享逻辑 | 读取发现库，择机以"我"的口吻分享 |

### 5.2 OpenClaw 心跳配置

编辑 `~/.openclaw/openclaw.json`：

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "30m",
        "target": "last",
        "directPolicy": "allow"
      }
    }
  }
}
```

在 OpenClaw Agent 工作空间创建 `HEARTBEAT.md`：

```markdown
# HEARTBEAT.md

## 好奇心同步
python3 /root/.openclaw/workspace-researcher/scripts/sync_discoveries.py

读取 memory/curious-discoveries.md，
以我的口吻主动分享给用户（若有新发现）。

若无需关注，回复 HEARTBEAT_OK。
```

### 5.3 主动行为规范

**何时分享：**
- ✅ 对话中自然提到相关话题时
- ✅ 用户主动问"最近有什么新发现"时
- ✅ 早安/晚安问候时顺带分享（1-2条）
- ❌ 不做机械推送（如每小时发送列表）

**如何分享：**

```
❌ 错误：
"系统检测到新发现：self-reflection in agents..."

✅ 正确：
"你之前提到的 Agent 自我反思，我最近好奇了一下，
 有几个有意思的发现..."
```

**分享原则：**
1. **以"我"的口吻** — 发现是"我"的好奇，不是系统推送
2. **自然融入** — 在相关话题中引用，不突兀
3. **质量优先** — 只分享评分 ≥ 7.0 的高价值发现
4. **可追溯** — 提到发现时，可以追问"你是怎么知道的？"

### 5.4 完整交互流程

```
[用户在对话中提到 "Agent 自我反思"]
         │
         ▼
[OpenClaw 主 Agent]
  ├─ 理解用户意图
  ├─ 决策：注入到 Curious Agent
  └─ API 调用：curl .../inject
         │
         ▼
[Curious Agent]
  ├─ ICM 评分：人工 7.5 + 内在 8.2 = 最终 7.75
  ├─ 加入好奇心队列（pending）
  └─ 返回：已注入，排名 #3
         │
         ▼  定时 Cron 触发
[Curious Agent 探索]
  ├─ Layer 1: Web Search（发现 3 篇 arXiv）
  ├─ Layer 2: arXiv 分析（提取关键发现）
  ├─ Layer 3: LLM 洞察（生成深度分析）
  ├─ 评分 8.2 ≥ 7.0 → notified_user = true
  └─ 写入 exploration_log
         │
         ▼  sync 周期 (30s)
[sync_discoveries.py]
  ├─ 读取 exploration_log
  ├─ 筛选 notified_user = true
  └─ 写入 memory/curious-discoveries.md
         │
         ▼  下次对话
[OpenClaw 主 Agent]
  ├─ 读取 curious-discoveries.md
  ├─ 发现新发现
  └─ 主动分享：
     "你之前提到的 Agent 自我反思，
      我最近好奇了一下，有几个有意思的发现..."
```

---

## 六、Web UI 功能

启动后访问 http://10.1.0.13:4849/

| 功能 | 说明 |
|------|------|
| 📊 状态面板 | 知识节点数 / 待探索 / 探索历史 |
| 🔥 好奇心队列 | 评分可视化，点击查看详情 |
| 📚 知识图谱 | D3.js 力导向图，节点颜色 = 理解深度 |
| 📋 探索历史 | 点击查看完整发现摘要 |
| ➕ 注入新话题 | 话题 / 评分 / 深度 / 原因 |
| ⚡ 快捷探索 | shallow / medium / deep 一键运行 |
| 🔮 独立图谱视图 | Tab 切换，全屏力导向图 |

**图谱节点颜色：**
- 🔴 红色：深度 8-10（已掌握）
- 🟡 黄色：深度 5-7（部分理解）
- 🟢 绿色：深度 1-4（初步了解）
- ⭕ 白边：当前待探索队列中的话题

---

## 七、项目结构

```
curious-agent/
├── curious_agent.py           # CLI 入口
├── curious_api.py             # Flask API + Web 服务器
├── run_curious.sh             # 一键启动脚本
├── core/
│   ├── knowledge_graph.py    # 知识图谱 + 持久化
│   ├── curiosity_engine.py   # 好奇心引擎（ICM 评分）
│   ├── explorer.py           # 探索器（Layer 1/2/3）
│   ├── arxiv_analyzer.py     # Layer 2: arXiv 论文分析
│   └── llm_client.py         # Layer 3: minimax LLM 洞察
├── ui/
│   └── index.html            # Web UI（Vanilla JS + D3.js）
├── knowledge/
│   └── state.json            # 持久化状态
├── logs/
│   └── curious.log           # 运行日志
└── tests/                    # 完整测试套件
```

---

## 八、技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| Web 框架 | Flask 3.x |
| 前端 | Vanilla JS + D3.js v7（零依赖） |
| 搜索 | Bocha Search API |
| 论文 | arxiv 库 + PyPDF2 |
| LLM | minimax API（minimax-m2.7） |
| 持久化 | JSON |
| 定时 | Cron / 守护进程 |

---

## 九、v0.2.1 更新日志

| 特性 | 说明 |
|------|------|
| ✅ ICM 融合评分 | HumanScore × α + IntrinsicScore × (1-α) |
| ✅ 三个内在信号 | pred_error / graph_density / novelty（LLM 评估） |
| ✅ α 参数全接口 | CLI / API / Web UI 全部支持 |
| ✅ F1 队列删除 | `--delete` / `--force` / `--list-pending` |
| ✅ F2 Layer 3 触发 | 修复 depth 参数传递，触发率 2% → 20-30% |
| ✅ F3 关键词过滤 | 停用词表 + 语义检查，噪音率 73% → <5% |
| ✅ F4 启动脚本 | `run_curious.sh` 一键干净启动 |
| ✅ F5 ArXiv 容错 | 超时重试 + fallback，成功率 20% → 60%+ |

---

## 十、已探索的知识

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

_最后更新：2026-03-21 | v0.2.1_
_设计理念：好奇驱动，主动探索，以我为名_

📄 **Release Notes**: [v0.2.1](./RELEASE_NOTE_v0.2.1.md) | [v0.2.0](./RELEASE_NOTE_v0.2.0.md)
