# next_move_v0.2.4 - R1D3 记忆优先框架 + 主动分享机制

> **版本关系**：v0.2.4 是 v0.2.3 的能力增强，叠加在 v0.2.3 之上，不替换已有能力  
> **核心目标**：R1D3 回答与学习解耦——记忆优先回答，探索后主动分享  
> **设计原则**：尽量复用现有模块，不重复造轮子  
> **最后更新**：2026-03-24（问题讨论完毕，已全部确认）

---

## 0. v0.2.3 能力清单（已包含）

| Phase | 能力 | 核心模块 |
|-------|------|---------|
| Phase 1 | Agent-Behavior-Writer | `AgentBehaviorWriter` |
| Phase 1 | 行为文件写入 | `curious-agent-behaviors.md` |
| Phase 2 | CompetenceTracker | `CompetenceTracker` |
| Phase 2 | 能力感知调度 | `select_next_v2` |
| Phase 2 | Quality v2 评估 | `QualityV2Assessor` |
| Phase 2 | 边际收益计算 | `MetaCognitiveMonitor` |
| Phase 3 | CuriosityDecomposer | `CuriosityDecomposer` |
| Phase 3 | Provider 热力图 | `ProviderRegistry` |
| 集成点3 | 话题注入 API | `POST /api/curious/inject` |
| 集成点4 | 状态查询 API | `GET /api/curious/state` |

---

## 1. 核心需求分析

### 1.1 R1D3 回答的现状问题

当前 R1D3 回答问题时：
- **没有先查记忆**——直接用 LLM 知识回答，不知道自己"记过什么"
- **探索是独立事件**—— Curious Agent 定时探索，但探索结果没有反馈到 R1D3 的回答中
- **用户无法感知学习闭环**——探索完成后 R1D3 不会主动告诉用户"我学会了什么"

### 1.2 v0.2.4 要解决的核心问题

| 问题 | 解决方案 | 复用模块 |
|------|---------|---------|
| R1D3 不知道"记过什么" | 记忆优先回答流程 | `memory_search()` |
| 触发探索需要新 API 吗？ | 复用 `/api/curious/inject` | `POST /api/curious/inject` |
| 如何判断该不该先探索？ | 复用 `CompetenceTracker` | `CompetenceTracker.assess_competence()` |
| 探索完成后如何主动分享？ | 复用 EventBus + 心跳同步 | `EventBus` + `CuriousHeartbeatClient` |

---

## 2. 新增/增强特性清单

### 2.1 特性总览

| 特性 | 类型 | 位置 | 复用/新建 |
|------|------|------|----------|
| 记忆优先回答流程 | 新增强制规则 | R1D3 (AGENTS.md) | 新建 |
| R1D3 侧置信度检查 | 新增 Tool | R1D3 | 新建（封装已有模块）|
| R1D3 侧定向触发探索 | 新增 Tool | R1D3 | 复用 `/api/curious/inject` |
| 主动分享机制 | 增强 | R1D3 | 复用已有记忆系统 |
| R1D3 注入优先处理 | 增强 | Curious Agent 侧 | 新建（config 控制）|
| 置信度主动暴露 | 新增行为规范 | R1D3 (SOUL.md) | 新建 |
| 自发主动探索机制 | 新增能力 | Curious Agent + R1D3 | 新建（双模式） |

---

## 3. 特性一：记忆优先回答流程

### 3.1 AGENTS.md 规则

**位置**：R1D3 的 `AGENTS.md`

**新增规则**：

```markdown
## 回答前检查（v0.2.4）

### 回答流程
1. **先搜索记忆**：使用 `memory_search(topic)` 搜索相关答案
2. **找到 → 直接回答**：标注"从记忆中..."，置信度高
3. **没找到 →诚实回答**：标注"基于 LLM 知识，我猜测..."，novice 档
4. **必然触发探索**：无论找到与否，都触发 `curious_agent_inject(topic)` 注入话题
```

### 3.2 curious_check_confidence Tool

**封装已有模块**：调用 `GET /api/curious/state`（集成点4），解析 `competence_state`

```python
def curious_check_confidence(topic: str) -> dict:
    """
    R1D3 查询某个 topic 的置信度
    
    Returns:
        {
            "topic": str,
            "confidence": float,       # 0-1, 来自 CompetenceTracker
            "level": str,              # "novice" | "competent" | "proficient" | "expert"
            "explore_count": int,      # 探索次数
            "gaps": list               # 知识缺口（如果有）
        }
    """
    # 调用 GET /api/curious/state
    # 解析 competence_state[topic_name]
```

### 3.3 curious_agent_inject Tool

**直接复用已有 API**：`POST /api/curious/inject`（集成点3）

```python
def curious_agent_inject(topic: str, context: str = "", depth: str = "medium") -> dict:
    """
    R1D3 主动触发定向探索
    
    Args:
        topic: 话题名称
        context: 用户问的原问题（用于评分）
        depth: 探索深度 ("shallow" | "medium" | "deep")
    
    Returns:
        {
            "status": "success" | "error",
            "topic_id": str,
            "estimated_position": int,
            "queue_length": int
        }
    """
    # 复用 POST /api/curious/inject
    # payload = { "topic": topic, "reason": context, "source": "r1d3" }
    # 如果 config.injection_priority.enabled=True 且 source 在 priority_sources 里
    # → 优先处理
    # 如果 config.injection_priority.trigger_immediate=True
    # → 立即触发探索，R1D3 不等待（异步）
```

---

## 4. 特性二：置信度主动暴露 + 回答详细程度分级

### 4.1 置信度 level 与回答策略

| Level | Confidence | 回答策略 | 详细程度 |
|-------|-----------|---------|---------|
| **novice** | < 0.3 | 基于 LLM 知识，我猜测... | 简洁，不展开 |
| **competent** | 0.3-0.6 | 我有一些了解但不深入... | 给大概方向 |
| **proficient** | 0.6-0.85 | 详细展开，主动给例子和细节 | 较详细 |
| **expert** | > 0.85 | 可以深入到实现细节、源码、论文 | 最详细 |

### 4.2 novice 回答示例

```
用户: Attention 机制是怎么工作的？

R1D3: 基于 LLM 的知识，我猜测你想问的是 Transformer 中的 Attention 机制...
（不展开细节，简短回答，不假装很懂）
```

### 4.3 expert 回答示例

```
用户: Attention 机制是怎么工作的？

R1D3: Attention 机制的核心是 Query-Key-Value 计算...

从记忆中（这个方向我研究过多次）：
1. Scaled Dot-Product Attention: QK^T / √d_k
2. Multi-Head Attention: 多组 QKV 并行...
3. 具体实现可以参考 transformer_modules.py...

深入一点，FlashAttention 的实现原理是...
（主动展开细节、例子、源码）
```

### 4.4 诚实是第一性原则

**无论哪个 level，都要诚实**：
- expert 不隐藏知识
- novice 不假装不懂也不假装很懂
- 置信度只是决定**详细程度**，不是决定**说不说**

---

## 5. 特性三：主动分享机制

### 5.1 分享粒度

**结论**：先全部分享，根据实际打扰程度再迭代。

### 5.2 复用现有机制

| 已有机制 | 复用方式 |
|---------|---------|
| `sync_discoveries.py` | 每次心跳同步最新发现到 `curious-discoveries.md` |
| `memory/curious-discoveries.md` | 新发现自动追加，格式含时间戳 |
| 新会话读取 | R1D3 启动时读取，与上一轮时间戳对比 |

### 5.3 追踪"已分享"

在 `curious-discoveries.md` 中加字段：

```markdown
- **[8.2]** Agent Memory Systems
  - 分享时间: 2026-03-24T16:50:00Z
  - shared: true
```

分享逻辑：
1. R1D3 启动时读取 `curious-discoveries.md`
2. 找出 `shared: false` 的发现
3. 主动说："你之前问的 XXX，我现在有答案了..."
4. 更新 `shared: true`

---

## 6. 特性四：R1D3 注入优先处理（Curious Agent 侧）

### 6.1 config 新增配置

```json
// curious-agent config.json
{
  "injection_priority": {
    "enabled": true,
    "priority_sources": ["r1d3"],
    "boost_score": 2.0,
    "trigger_immediate": true
  }
}
```

| 配置项 | 说明 |
|-------|------|
| `enabled` | 是否启用优先处理 |
| `priority_sources` | 优先名单，名单内的 source 注入的话题优先处理 |
| `boost_score` | 优先话题的分数加成 |
| `trigger_immediate` | True = 立即触发探索，R1D3 不等待（异步） |

### 6.2 处理逻辑

```python
# curious_agent.py inject 端点
def inject_topic(topic, source, score=None, ...):
    if config.injection_priority.enabled and source in config.injection_priority.priority_sources:
        # 优先处理
        effective_score = (score or 5.0) + config.injection_priority.boost_score
        
        if config.injection_priority.trigger_immediate:
            # 立即触发探索，异步，不阻塞
            async_trigger_exploration(topic)
        else:
            # 入队，等 cron 定时处理
            queue.add(topic, score=effective_score)
    else:
        # 普通处理
        queue.add(topic, score=score)
```

---

## 7. 架构接口图（v0.2.4 新增部分）

```
R1D3 (OpenClaw Agent)
│
├── AGENTS.md 规则（新建）
│   └── 记忆优先回答流程
│
├── curious_check_confidence(topic) [Tool, 新建]
│   └── 封装: GET /api/curious/state
│
├── curious_agent_inject(topic, context, depth) [Tool, 新建]
│   └── 复用: POST /api/curious/inject
│   └── priority_sources 名单内 → 优先处理 + 立即探索
│
├── SOUL.md 行为规范（增强）
│   └── 置信度主动暴露 + 回答详细程度分级
│
└── 主动分享 [增强]
    └── 复用: memory/curious-discoveries.md + sync_discoveries.py
    └── shared 字段追踪已分享


Curious Agent (改动: config.json + inject 端点)
│
├── config.json 新增 injection_priority 配置
├── POST /api/curious/inject [增强]
│   └── priority_sources 名单内 → boost_score + trigger_immediate
├── GET /api/curious/state [已有, 复用]
├── CompetenceTracker [已有, 复用]
├── AgentBehaviorWriter [已有, 复用]
└── EventBus [已有, 复用]
```

---

## 8. 实现任务清单

### 8.1 R1D3 侧（新增）

| 优先级 | 任务 | 说明 |
|-------|------|------|
| P0 | AGENTS.md 记忆优先规则 | 回答前先查 memory_search() |
| P0 | curious_check_confidence Tool | 封装 /api/curious/state |
| P0 | curious_agent_inject Tool | 封装 /api/curious/inject |
| P0 | SOUL.md 置信度暴露规范 | novice~expert 四档回答策略 |
| P1 | 主动分享逻辑 | 新会话时对比 shared 字段 |
| P2 | shared 追踪写入 | 更新 curious-discoveries.md |

### 8.2 Curious Agent 侧（新增）

| 优先级 | 任务 | 说明 |
|-------|------|------|
| P0 | config.json injection_priority | 新增配置项 |
| P0 | inject 端点优先逻辑 | priority_sources + boost_score + trigger_immediate |
| P1 | config.json exploration mode | hybrid/daemon/api_only 三模式 |
| P1 | daemon 与 inject 联动 | trigger_immediate=true 时 inject 后立即异步探索 |

---

## 9. 不纳入 v0.2.4 的内容

- mission 验证机制（移至 v0.2.5+）
- OpenClaw Hook 实时注入（依赖验证）
- 置信度精确计算（当前 level 映射够用）
- 分享粒度迭代（先全部分享，看打扰程度再调）

---

## 10. 与 v0.2.3 的接口关系

```
v0.2.3 基础层（完全不变）
├── /api/curious/inject ←── R1D3 inject Tool 复用
│   └── 新增：priority_sources 名单判断
├── /api/curious/state ←── R1D3 confidence Tool 复用
├── CompetenceTracker ←── R1D3 confidence Tool 复用
├── AgentBehaviorWriter ←── 被动复用（写入行为规则）
└── EventBus ←── 被动复用（通知机制）

v0.2.4 新增
├── R1D3 侧
│   ├── AGENTS.md 记忆优先规则
│   ├── curious_check_confidence Tool
│   ├── curious_agent_inject Tool
│   ├── SOUL.md 置信度暴露规范
│   └── 主动分享逻辑
└── Curious Agent 侧
    ├── config.json injection_priority + exploration mode
├── curious_agent.py --daemon [已有, 复用]
├── POST /api/curious/inject [增强]
    └── inject 端点优先逻辑
```

---

## 12. 特性五：自发主动探索机制

### 12.1 两种探索触发模式

Curious Agent 的探索触发分为**外部触发**和**自发主动**两类：

| 模式 | 触发方式 | 适用场景 |
|------|---------|---------|
| **外部触发** | R1D3 调用 `trigger_explore.sh` → `POST /api/curious/inject` | 用户提问时注入话题 |
| **定时自发** | `curious_agent.py --daemon --interval N` 守护进程 | 无人介入时持续探索 |
| **混合模式** | 外部触发优先 + 定时兜底 | 平衡实时性和持续性 |

### 12.2 定时自发探索（守护进程模式）

**已有实现**：`curious_agent.py --daemon --interval N`

```bash
# 每 30 分钟探索一次
python3 curious_agent.py --daemon --interval 30

# 每 2 小时探索一次
python3 curious_agent.py --daemon --interval 120
```

**daemon 模式逻辑**：

```python
def daemon_mode(interval_minutes: int = 30):
    while True:
        # 1. 从队列取 top curiosity
        topic = select_next_v2()
        # 2. 执行探索（generate_insights）
        result = explorer.explore(topic)
        # 3. 质量评估 + 写入 KG
        quality = quality_assessor(result)
        write_to_kg(topic, result, quality)
        # 4. 计算边际收益，决定是否继续
        if marginal_return_too_low():
            break
        # 5. 等待下一个 interval
        time.sleep(interval_minutes * 60)
```

### 12.3 外部触发（外部注入）

**已有实现**：`POST /api/curious/inject`

```bash
bash trigger_explore.sh "MCP协议工作原理" "用户问了我MCP协议"
```

**inject 端点行为**：

```python
# POST /api/curious/inject
payload = {
    "topic": "MCP协议工作原理",
    "context": "用户问了我MCP协议",
    "source": "r1d3",          # 来源标识
    "priority": True           # 可选：优先处理
}

# 如果 priority=True + trigger_immediate=True
# → 立即触发探索（异步），不等待 daemon
# 否则 → 入队，等 daemon 下一次轮询
```

### 12.4 混合模式架构

```
                    ┌─────────────────────────────────────┐
                    │       R1D3 (OpenClaw Agent)          │
                    │                                      │
  用户提问 ──→ memory_search ──→ 回答 ──→ inject(topic)      │
                    │                        │              │
                    │                   POST /api/curious/inject
                    │                        │
                    └────────────────────────┼──────────────┘
                                             │
                              ┌──────────────┴──────────────┐
                              │   Curious Agent API Server     │
                              │   (curious_api.py)            │
                              │                               │
                              │  ┌─────────────────────────┐ │
                              │  │ injection_priority 配置  │ │
                              │  │ priority_sources: [r1d3] │ │
                              │  └──────────┬──────────────┘ │
                              │             │                 │
                              │      是否优先注入?            │
                              │             │                 │
                              │    ┌────────┴────────┐      │
                              │    │                 │        │
                              │   YES               NO       │
                              │    │                 │        │
                              │    ▼                 ▼        │
                              │ 立即异步探索      入队等待     │
                              │ (不阻塞R1D3)    daemon轮询    │
                              │                               │
                              │  ┌─────────────────────────┐ │
                              │  │   Daemon 守护进程        │ │
                              │  │   curious_agent.py       │ │
                              │  │   --daemon --interval N  │ │
                              │  └──────────┬──────────────┘ │
                              │             │                 │
                              │    每 N 分钟轮询队列          │
                              │    执行 select_next_v2()      │
                              │    → 探索 → 写 KG            │
                              └─────────────────────────────────┘
                                             │
                              ┌──────────────┴──────────────┐
                              │   探索结果同步到 R1D3         │
                              │   sync_discoveries.py        │
                              │   → curious-discoveries.md   │
                              └──────────────────────────────┘
```

### 12.5 配置项

```json
// Curious Agent config.json
{
  "exploration": {
    "mode": "daemon",           // "daemon" | "api_only" | "hybrid"
    "daemon": {
      "interval_minutes": 30,   // 守护进程探索间隔
      "explore_per_round": 1    // 每次探索几个 topic
    },
    "injection_priority": {
      "enabled": true,
      "priority_sources": ["r1d3"],
      "trigger_immediate": true,  // true=外部注入立即触发 false=入队等daemon
      "boost_score": 2.0
    }
  }
}
```

| 配置组合 | 行为 |
|---------|------|
| `mode: "api_only"` | 完全依赖外部触发，无定时探索 |
| `mode: "daemon"` | 纯定时探索，忽略外部注入立即触发 |
| `mode: "hybrid"` | 外部注入优先 + daemon 兜底（推荐） |

### 12.6 推荐配置

**v0.2.4 默认配置**：

```json
{
  "exploration": {
    "mode": "hybrid",
    "daemon": {
      "interval_minutes": 60,
      "explore_per_round": 1
    },
    "injection_priority": {
      "enabled": true,
      "priority_sources": ["r1d3"],
      "trigger_immediate": true,
      "boost_score": 2.0
    }
  }
}
```

- R1D3 提问 → 立即触发探索（异步）
- daemon 每 60 分钟做一次兜底探索
- 外部注入的 priority 话题 boost 2.0 分

---

## 13. 关键结论

1. **inject_and_explore 不需要新 API**——`POST /api/curious/inject` + 已有定时探索机制完全够用
2. **check_confidence 不需要新 API**——`GET /api/curious/state` 的 `competence_state` 完全够用
3. **v0.2.4 的开发量分在 R1D3 侧和 Curious Agent 侧**
4. **主动分享复用现有 sync_discoveries 机制**——只需要加"已分享"追踪逻辑
5. **R1D3 注入优先处理**——config 配置 priority_sources + boost_score + trigger_immediate
6. **置信度主动暴露**——novice 说"基于 LLM 知识我猜测"，expert 详细展开
7. **自发探索 = hybrid 模式**——外部触发优先（trigger_immediate）+ daemon 定时兜底，推荐 interval=60min
