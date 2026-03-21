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

### 4.1 ICM 融合评分机制（v0.2.1）

Curious Agent v0.2.1 引入 ICM（Intrinsic Curiosity Module）融合评分，平衡人工意图和自主探索：

```
FinalScore = HumanScore × α + IntrinsicScore × (1 - α)
```

**α 参数控制**（用户可配置）：
- `α = 0.7`（--motivation human）：偏重人工意图
- `α = 0.3`（--motivation curious）：偏重自主探索
- `α = 0.0`（--pure-curious）：纯探索模式
- `α = 0.5`（默认）：平衡模式

**人工评分（HumanScore）**：
```
HumanScore = Relevance × 0.35 + Recency × 0.25 + Depth × 0.25 + Surprise × 0.15
```

| 维度 | 含义 | 计算方式 |
|------|------|---------|
| **Relevance** | 与用户兴趣的相关性 | 匹配关键词 +1.5/命中 |
| **Recency** | 遗忘效应 | 每24小时 +1 分，上限 10 |
| **Depth** | 知识缺口深度 | 直接使用，越深越想探索 |
| **Surprise** | 意外程度 | 图谱中越少相关节点越惊喜 |

**内在评分（IntrinsicScore）- LLM 评估**：
| 信号 | 权重 | 含义 | 评估方式 |
|------|------|------|---------|
| **pred_error** | 0.4 | 预测误差（理解不确定性） | LLM 评估历史探索质量 |
| **graph_density** | 0.3 | 图谱密度（知识网络位置） | 连接越少分越高 |
| **novelty** | 0.3 | 新颖性（语义重叠度） | LLM 对比已知知识 |

内在评分使用 LLM 进行语义理解和综合推理，图谱统计作为辅助输入。LLM 失败时自动降级到统计方案。

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

Curious Agent 已**内化为 OpenClaw 主 Agent 的能力模块**，形成完整的"感知-记忆-行动"闭环：

### 6.1 集成架构

```
┌─────────────────────────────────────────────────────────────┐
│                      OpenClaw 主 Agent                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   感知层    │  │   记忆层    │  │      行动层         │ │
│  │sync_discover│◀─┤curious-disc │◀─┤  主动分享 + 引用    │ │
│  │ ies.py     │  │overies.md   │  │                     │ │
│  └──────┬──────┘  └─────────────┘  └─────────────────────┘ │
│         │                                                   │
│         │ 心跳同步 (30s)                                    │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Curious Agent (独立进程)                │   │
│  │  ┌──────────┐   ┌─────────────┐   ┌────────────┐   │   │
│  │  │好奇心队列 │   │  知识图谱    │   │  探索器    │   │   │
│  │  │          │   │             │   │            │   │   │
│  │  └──────────┘   └─────────────┘   └────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 外部 Agent 注入好奇心

OpenClaw 或其他外部 Agent 可通过 **API** 向 Curious Agent 注入好奇心：

**方式 1：实时注入（推荐）**
```bash
# 基础注入
curl -X POST http://10.1.0.13:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "self-reflection in LLM agents",
    "reason": "用户在对话中提到对Agent自我反思感兴趣",
    "relevance": 8.5,
    "depth": 7.0
  }'

# 使用 ICM 融合评分（v0.2.1+）
curl -X POST http://10.1.0.13:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "transformer attention mechanism",
    "reason": "对话上下文推断",
    "alpha": 0.7,
    "mode": "fusion"
  }'

# 纯内在信号模式（完全自主）
curl -X POST http://10.1.0.13:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "knowledge graph embedding",
    "reason": "系统自动发现",
    "mode": "intrinsic"
  }'
```

**方式 2：触发探索（异步执行）**
```bash
# 立即触发探索（后台执行，无需等待）
curl -X POST http://10.1.0.13:4848/api/curious/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "multi-agent orchestration",
    "depth": "deep"
  }'

# 返回：{"status": "accepted", "estimated_time": "10-15分钟"}
```

**参数说明**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `topic` | string | **必填**，研究话题 |
| `reason` | string | 注入原因，用于溯源 |
| `relevance` | float | 相关性分数 (0-10)，默认 7.0 |
| `depth` | float | 深度分数 (0-10)，默认 6.0 |
| `alpha` | float | 人工信号权重 (0.0-1.0)，默认 0.5 |
| `mode` | string | `fusion` 或 `intrinsic` |

### 6.3 发现通知机制

当 Curious Agent 完成探索后，根据**评分阈值**决定是否通知用户：

**通知判断逻辑**：
```python
# 在 explorer.py 中
score = curiosity_item["score"]                    # 好奇心评分
threshold = 7.0                                     # 通知阈值（可配置）
should_notify = score >= threshold                  # 是否通知

# 记录到 exploration_log
kg.log_exploration(topic, action, findings, should_notify)
```

**通知流程**：
1. **探索完成** → 计算最终评分
2. **评分 ≥ 7.0** → 标记 `notified_user: true`
3. **同步到 OpenClaw** → `sync_discoveries.py` 每 30 秒读取 exploration_log
4. **写入发现库** → 追加到 `memory/curious-discoveries.md`
5. **主 Agent 感知** → 读取发现库，筛选高价值发现
6. **主动分享** → 在合适时机以"我"的口吻告诉用户

**通知格式示例**：
```markdown
<!-- memory/curious-discoveries.md -->
## 2026-03-20 的发现

### 🔍 transformer attention mechanism
**评分**: 8.2 | **深度**: Layer 3 (LLM 洞察)

**发现摘要**：
Transformer 的注意力机制本质上是...

**来源**：
- arXiv:2401.02009
- https://blog.example.com/attention

**我的思考**：
这个发现让我想到，在我们的系统中可以...
```

### 6.4 完整集成流程

**场景：用户在对话中提到对某个话题感兴趣**

```
[用户] "最近看到有人说 Agent 的自我反思很有意思"
    │
    ▼
[OpenClaw 主 Agent] 
    ├─ 理解用户意图：对 "self-reflection in agents" 感兴趣
    ├─ 决策：注入到 Curious Agent 进行深入研究
    │
    ▼ API 调用
[Curious Agent] 收到注入请求
    ├─ 使用 ICM 评分：人工 7.5 + 内在 8.2 = 最终 7.75
    ├─ 加入好奇心队列（pending）
    └─ 返回：已注入，排名 #3
    │
    ▼ 30 分钟后（Cron 触发）
[Curious Agent] 自动探索
    ├─ Layer 1: Web Search (发现 3 篇 arXiv)
    ├─ Layer 2: arXiv 分析 (提取关键发现)
    ├─ Layer 3: LLM 洞察 (生成深度分析)
    ├─ 评分 8.2 ≥ 7.0 → notified_user = true
    └─ 写入 exploration_log
    │
    ▼ 30 秒同步周期
[OpenClaw sync_discoveries.py]
    ├─ 读取 exploration_log
    ├─ 筛选 notified_user = true 的条目
    ├─ 追加到 memory/curious-discoveries.md
    └─ 更新最后同步时间戳
    │
    ▼ 下次对话
[OpenClaw 主 Agent]
    ├─ 读取 curious-discoveries.md
    ├─ 发现新发现（self-reflection）
    └─ 主动分享：
       
       "你之前提到的 Agent 自我反思，
        我最近好奇了一下，有几个有意思的发现...
        
        首先，现在的主流方法分为两类..."
```

### 6.5 层次化集成设计

| 层次 | 组件 | 职责 | 技术实现 |
|------|------|------|---------|
| **感知层** | `sync_discoveries.py` | 定期同步新发现 | 每 30s 读取 exploration_log，过滤 `notified_user=true` |
| **记忆层** | `memory/curious-discoveries.md` | 持久化发现库 | Markdown 格式，按日期分组，包含评分和来源 |
| **意识层** | `SOUL.md` | 定义好奇特质 | "我是一个有好奇心的 Agent，会主动探索..." |
| **行动层** | 主动分享逻辑 | 择机告知用户 | 读取发现库，以"我"的口吻自然融入对话 |

### 6.6 主 Agent 的主动行为规范

**何时分享**：
- ✅ 对话中自然提到相关话题时
- ✅ 用户主动询问"最近有什么新发现"时
- ✅ 早安/晚安问候时顺带分享（1-2 条）
- ❌ 不做机械推送（如每小时发送列表）

**如何分享**：
```
❌ 错误示范：
"系统检测到您有一个新发现：self-reflection in agents..."

✅ 正确示范：
"你之前提到的 Agent 自我反思，我最近好奇了一下，
 有几个有意思的发现。现在主流的方法其实分为两类..."
```

**分享原则**：
1. **以"我"的口吻** — 发现是"我"的好奇，不是系统推送
2. **自然融入** — 在相关话题中引用，不突兀
3. **质量优先** — 只分享评分 ≥ 7.0 的高价值发现
4. **可追溯** — 提到发现时，可以追问"你是怎么知道的这个？"

### 6.7 核心原理：为什么 Curious Agent 让 OpenClaw 变成"主动思考"的 Agent

**传统 AI Agent 的问题**：
```
用户提问 → Agent 回答 → 会话结束 → 下次从零开始
```
Agent 是**被动响应**的——没有问题就没有行动，没有上下文就没有积累。

**Curious Agent 带来的改变**：
```
无用户输入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  ICM 内在好奇心模块                                        │
│                                                             │
│  IntrinsicScore = pred_error × 0.4                        │
│                 + graph_density × 0.3                      │
│                 + novelty × 0.3                            │
│                                                             │
│  • pred_error ↑    → 预测不准 → 需要探索                   │
│  • graph_density ↓ → 知识孤岛 → 需要连接                   │
│  • novelty ↑       → 全新领域 → 值得发现                   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼ 内在驱动力
┌─────────────────────────────────────────────────────────────┐
│  主动探索循环                                               │
│                                                             │
│  1. 知识图谱中发现空白（某个话题没有/深度不足）             │
│  2. ICM 计算该话题的 IntrinsicScore 高                     │
│  3. 好奇心引擎将话题加入队列                                │
│  4. Cron/心跳触发探索 → Layer 1+2+3 分层执行              │
│  5. 探索结果写入 state.json + 通知标记                      │
│  6. sync_discoveries.py 同步到 OpenClaw 记忆系统           │
│  7. OpenClaw Agent 在合适时机主动分享给用户                 │
└─────────────────────────────────────────────────────────────┘
```

**关键区别**：

| 对比维度 | 传统 Agent | Curious Agent 加持 |
|---------|------------|------------------|
| **触发方式** | 用户提问 | 用户提问 + 内在好奇 |
| **知识积累** | 会话结束即消散 | 持久化到知识图谱 |
| **主动性** | 被动响应 | 主动发现缺口 |
| **分享时机** | 用户问了才答 | 择机主动分享 |
| **上下文** | 每次从零 | 跨会话记忆 |

**双向交互闭环**：

```
┌──────────────────────────────────────────────────────────────┐
│                      完整闭环                                │
│                                                              │
│  ┌─────────────┐     用户输入      ┌─────────────┐       │
│  │   OpenClaw   │◀─────────────────▶│    用户      │       │
│  │   主 Agent   │     被动响应       │              │       │
│  └──────┬──────┘                    └─────────────┘       │
│         │                                                   │
│         │ 主动分享（发现/洞察）                              │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   Curious Agent                        │  │
│  │                                                       │  │
│  │   感知 ──→ 记忆 ──→ 决策 ──→ 探索 ──→ 反馈          │  │
│  │     │                          │                      │  │
│  │     │                          ▼                      │  │
│  │     │                    知识图谱更新                   │  │
│  │     │                          │                      │  │
│  │     │◀─────────────────────────┘                      │  │
│  │     │                                                   │  │
│  │     │ ICM 内在评分驱动                                  │  │
│  │     │ (无用户输入时依然运行)                            │  │
│  └─────┼───────────────────────────────────────────────────┘  │
│        │                                                     │
│        │ 定时同步 (30s)                                       │
│        ▼                                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              OpenClaw 记忆系统                         │  │
│  │   memory/curious-discoveries.md                       │  │
│  │   memory_search() 可检索                              │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**总结**：Curious Agent 给 OpenClaw 带来了**内在动机驱动**。在没有用户输入时，ICM 模块持续监控知识图谱的空白，高 IntrinsicScore 的话题会自动触发探索，探索结果通过记忆系统反馈给 OpenClaw，OpenClaw 在合适时机以"我"的口吻主动分享——这就是**主动思考**的本质。

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
