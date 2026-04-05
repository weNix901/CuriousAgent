# v0.2.8 — 可视化：数据流 + 队列管道 + R1D3 消费

## 目标

在现有 `ui/index.html` 中新增第三个 Tab：「数据流」，实时可视化：
1. R1D3（数字生命体）与 Curious Agent（好奇探索系统）两大顶级模块
2. 每个顶级模块内部所有子模块及其数据流
3. 两模块之间的双向数据通道
4. 每个处理阶段的速度和流量
5. LOOP 历史滚动时间线
6. TRACE 专题追踪
7. R1D3 消费 CA 发现的全链路

**增量开发原则**：不改现有 UI 结构和 API，只新增 Tab + 新增 API endpoint。

---

## 零、整体架构：两大顶级模块数据流图

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                               🧠 R1D3（数字生命体）                              ┃
┃                                    主机：researcher session                              ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                                      ┃
┃  ┌─────────────────────────────────────────────────────────────────────────────┐   ┃
┃  │                          R1D3 子模块与数据流                                      │   ┃
┃  │                                                                              │   ┃
┃  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                   │   ┃
┃  │  │   HEARTBEAT   │   │  AGENTS.md   │   │   MEMORY.md   │                   │   ┃
┃  │  │   每心跳执行  │   │  工作流定义   │   │  长期记忆    │                   │   ┃
┃  │  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘                   │   ┃
┃  │          │                  │                  │                              │   ┃
┃  │          ▼                  │                  │                              │   ┃
┃  │  ┌──────────────────────────────────────────────────────────┐              │   ┃
┃  │  │                   R1D3 Skill 执行层                              │              │   ┃
┃  │  │                                                                  │              │   ┃
┃  │  │  ┌──────────────────┐     ┌──────────────────┐                │              │   ┃
┃  │  │  │ sync_discoveries │     │share_new_        │                │              │   ┃
┃  │  │  │ .py              │     │discoveries.py    │                │              │   ┃
┃  │  │  │                  │     │                  │                │              │   ┃
┃  │  │  │ 输入:            │     │ 输入:              │                │              │   ┃
┃  │  │  │  state.json      │     │ curious-          │                │              │   ┃
┃  │  │  │  ←─────────────  │     │ discoveries.md    │                │              │   ┃
┃  │  │  │  (CA生产数据)     │     │ ←────────────────  │                │              │   ┃
┃  │  │  │                  │     │                  │                │              │   ┃
┃  │  │  │ 输出:            │     │ 输出:              │                │              │   ┃
┃  │  │  │  memory/curious/│     │ undiscovered[]    │                │              │   ┃
┃  │  │  │   discoveries.md│     │ (高分待分享列表)    │                │              │   ┃
┃  │  │  │  →─────────────  │     │ →───────────────  │                │              │   ┃
┃  │  │  │  R1D3 记忆层     │     │ R1D3→用户推送     │                │              │   ┃
┃  │  │  └────────┬─────────┘     └────────┬─────────┘                │              │   ┃
┃  │  │           │                          │                             │              │   ┃
┃  │  └───────────┼──────────────────────────┼─────────────────────────────┘              │   ┃
┃  │              │                          │                                        │   ┃
┃  │              ▼                          ▼                                        │   ┃
┃  │  ┌──────────────────────────────────────────────────────────┐              │   ┃
┃  │  │               R1D3 主动分享层                               │              │   ┃
┃  │  │                                                                  │              │   ┃
┃  │  │  飞书推送: "我最近好奇了 TRACE，有几个有意思的发现..."              │              │   ┃
┃  │  │  对话引用: R1D3 在对话中自然引用 CA 探索结论                     │              │   ┃
┃  │  └──────────────────────────────────────────────────────────┘              │   ┃
┃  │                                                                              │   ┃
┃  │  ┌──────────────────────────────────────────────────────────┐              │   ┃
┃  │  │               R1D3 决策层（使用 CA 知识）                       │              │   ┃
┃  │  │                                                                  │              │   ┃
┃  │  │  · memory_search() 检索 CA 知识                              │              │   ┃
┃  │  │  · 置信度感知：先判断知不知道，再决定怎么回答                     │              │   ┃
┃  │  │  · 好奇探索触发：低置信度时主动注入 topic 到 CA 队列             │              │   ┃
┃  │  └──────────────────────────────────────────────────────────┘              │   ┃
┃  └─────────────────────────────────────────────────────────────────────────────┘   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
          │                                                                  │
          │ CA 发现写入                                                      │ R1D3 注入 topic
          │ memory/curious/*.md                                              │ curiosity_queue
          ▼                                                                  ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                              🔬 Curious Agent（好奇探索系统）                    ┃
┃                                  主机：daemon process                              ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                                      ┃
┃  ┌─────────────────────────────────────────────────────────────────────────────┐   ┃
┃  │                          CA 子模块与数据流                                         │   ┃
┃  │                                                                              │   ┃
┃  │  ┌──────────────────────────────────────────────────────────────────────┐  │   ┃
┃  │  │                         持久化存储层（knowledge/）                            │  │   ┃
┃  │  │                                                                      │  │   ┃
┃  │  │   state.json          dream_topic_inbox.json    exploration_log.json   │  │   ┃
┃  │  │   ├── KG (topics)     └── DreamAgent 洞察       └── 探索历史             │  │   ┃
┃  │  │   ├── curiosity_queue                         (每条记录含:           │  │   ┃
┃  │  │   ├── exploration_log                          topic, status,         │  │   ┃
┃  │  │   └── meta_cognitive                          findings, sources,      │  │   ┃
┃  │  │                                              quality, subtopics)     │  │   ┃
┃  │  └──────────────────────────────────────────────────────────────────────┘  │   ┃
┃  │                                      ▲                                      │   ┃
┃  │                                      │ read/write                              │   ┃
┃  │  ┌───────────────────────────────────┼───────────────────────────────────┐  │   ┃
┃  │  │                           主循环（监控线程）                              │  │   ┃
┃  │  │   every 10s: 打印状态 | every 60s: claim 主队列 | revive stuck       │  │   ┃
┃  │  └───────────────────────────────────┼───────────────────────────────────┘  │   ┃
┃  │                                      │                                      │   ┃
┃  │         ┌────────────────────────────┼────────────────────────────┐         │   ┃
┃  │         │                            │                            │         │   ┃
┃  │         ▼                            ▼                            ▼         │   ┃
┃  │  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐     │   ┃
┃  │  │ SpiderAgent │          │  DreamAgent │          │SleepPruner │     │   ┃
┃  │  │   🕷️       │          │    💤       │          │    ✂️      │     │   ┃
┃  │  │            │          │            │          │            │     │   ┃
┃  │  │ 子线程1    │          │ 子线程2     │          │ 子线程3    │     │   ┃
┃  │  │            │          │            │          │            │     │   ┃
┃  │  └─────┬──────┘          └─────┬──────┘          └─────┬──────┘     │   ┃
┃  │        │                        │                        │            │     │   ┃
┃  │        ▼                        ▼                        │            │     │   ┃
┃  │  ┌─────────────────────────────────────────┐          │            │     │   ┃
┃  │  │              CA 核心处理流程                  │          │            │     │   ┃
┃  │  │                                                │          │            │     │   ┃
┃  │  │  ┌──────────┐    ┌──────────┐   ┌──────────┐ │          │            │     │   ┃
┃  │  │  │ DreamInbox│ → │  探索    │ → │  分解    │→│ KG写入   │            │     │   ┃
┃  │  │  │ 优先读取  │    │ Serper   │   │ Decomposer│ │ partial   │            │     │   ┃
┃  │  │  │          │    │ +LLM合成 │   │ 子话题提取│ │           │            │     │   ┃
┃  │  │  └──────────┘    └──────────┘   └──────────┘ └──────────┘            │     │   ┃
┃  │  │         ▲               │               │               │              │     │   ┃
┃  │  │         │               ▼               ▼               ▼              │     │   ┃
┃  │  │         │         ┌─────────────────────────────────────────┐        │     │   ┃
┃  │  │         │         │          Quality 评估 (QualityV2)        │        │     │   ┃
┃  │  │         │         │   score = f(新颖性, 深度, 实用性, 一致性) │        │     │   ┃
┃  │  │         │         └─────────────────────────────────────────┘        │     │   ┃
┃  │  │         │                                                         │     │   ┃
┃  │  │         └────────────────────┐                                    │     │   ┃
┃  │  │                              │                                    │     │   ┃
┃  │  │                              ▼                                    │     │   ┃
┃  │  │                    ┌──────────────────┐                        │     │   ┃
┃  │  │                    │curiosity_queue   │                        │     │   ┃
┃  │  │                    │  新子话题写入     │                        │     │   ┃
┃  │  │                    │  (pending)       │                        │     │   ┃
┃  │  │                    └──────────────────┘                        │     │   ┃
┃  │  │                              ▲                                  │     │   ┃
┃  │  │                              │                                  │     │   ┃
┃  │  │                    ┌─────────┴──────────┐                      │     │   ┃
┃  │  │                    │   Monitor 循环      │                      │     │   ┃
┃  │  │                    │  claim_pending_item│                      │     │   ┃
┃  │  │                    │  → add_to_dream_inbox                    │     │     │   ┃
┃  │  │                    └───────────────────┘                        │     │   ┃
┃  │  └─────────────────────────────────────────────────────────────────┘     │   ┃
┃  │                                                                              │   ┃
┃  │  ┌──────────────────────────────────────────────────────────────────┐    │   ┃
┃  │  │                        DreamAgent 创意生成                            │    │   ┃
┃  │  │                                                                    │    │   ┃
┃  │  │  every 2s:                                                       │    │   ┃
┃  │  │    · 从 high_priority_queue 取 5 个 topic（5s 超时）               │    │   ┃
┃  │  │    · 从 low_priority_queue 随机选 topic                            │    │   ┃
┃  │  │    · LLM 生成创意洞察（insight）                                   │    │   ┃
┃  │  │    · insight → add_to_dream_inbox()                               │    │   ┃
┃  │  │                                                                    │    │   ┃
┃  │  │  insights 存储位置: knowledge/dream_topic_inbox.json                │    │   ┃
┃  │  └──────────────────────────────────────────────────────────────────┘    │   ┃
┃  │                                                                              │   ┃
┃  │  ┌──────────────────────────────────────────────────────────────────┐    │   ┃
┃  │  │                      SleepPruner 修剪                              │    │   ┃
┃  │  │                                                                    │    │   ┃
┃  │  │  every 8-24h (动态间隔):                                           │    │   ┃
┃  │  │    · 扫描 dream_topic_inbox                                        │    │   ┃
┃  │  │    · 删除 7 天前 且 quality < 5.0 的 insights                      │    │   ┃
┃  │  │    · consolidation: 合并 14 天内相似 insights                      │    │   ┃
┃  │  └──────────────────────────────────────────────────────────────────┘    │   ┃
┃  └─────────────────────────────────────────────────────────────────────────────┘   ┃
┃                                                                                      ┃
┃  ┌─────────────────────────────────────────────────────────────────────────────┐   ┃
┃  │                         CA → R1D3 数据通道                                      │   ┃
┃  │                                                                              │   ┃
┃  │   KG (partial/complete)  ──exploration_log──  sync_discoveries.py ──→       │   ┃
┃  │   memory/curious/*.md  ──索引──→  curious-discoveries.md (shared:false)      │   ┃
┃  │                                                                              │   ┃
┃  │   R1D3 注入:  curiosity_queue ──claim──→ DreamInbox ──explore──→ KG         │   ┃
┃  └─────────────────────────────────────────────────────────────────────────────┘   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### 零.1 R1D3 内部数据流详解

| 子模块 | 职责 | 输入 | 输出 | 可视化显示 |
|--------|------|------|------|-----------|
| HEARTBEAT | 每 ~30 分钟触发一次 | — | 执行所有 skill | 最后执行时间、耗时 |
| `sync_discoveries.py` | 同步 CA 发现到记忆 | `state.json` + `exploration_log` | `memory/curious/*.md` + `curious-discoveries.md` | 同步文件数、延迟 |
| `share_new_discoveries.py` | 推送高分发现给用户 | `curious-discoveries.md` | 飞书消息 | 待分享数、已分享数 |
| `memory_search()` | 检索 CA 知识 | 关键词 | 相关发现 | R1D3 引用次数 |
| 置信度感知 | 判断回答详细程度 | LLM 知识 vs CA 知识 | expert/competent/novice | — |
| 好奇触发 | 低置信度时注入 topic | 用户问题 | `curiosity_queue` | 注入 topic 数 |

### 零.2 CA 内部数据流详解

| 子模块 | 职责 | 输入 | 输出 | 可视化显示 |
|--------|------|------|------|-----------|
| curiosity_queue | 待探索话题池 | Monitor claim / R1D3 注入 / Spider 子话题 | 被 claim | pending 数、priority 分布 |
| DreamInbox | 洞察优先队列 | DreamAgent insights / Monitor claim | SpiderAgent 读取 | inbox size、流速 |
| SpiderAgent | 探索 + 分解 | DreamInbox topic | KG partial + 新子话题 → queue | 正在探索的 topic、已探索数 |
| DreamAgent | 创意洞察生成 | high/low priority queue | insight → DreamInbox | insights 数量、生产速度 |
| SleepPruner | 过期清理 | dream_topic_inbox | 清理过期 insights | 下次修剪时间、已清理数 |
| Monitor | 协调 + 保活 | — | claim 主队列 + revive stuck | cycle count、claim 速度 |
| KG | 知识库 | SpiderAgent 探索结果 | 持久化 state.json | complete/partial 数、流速 |
| QualityV2 | 质量评估 | 探索结果（新颖性+深度+实用性+一致性） | quality score | — |

---

---

## 现有代码参考

### 已有文件
- `curious_api.py` — Flask API server，端口 4848，`app` 是 Flask 实例
- `ui/index.html` — 现有 UI（1049 行），已有 tabs：`列表视图` + `图谱视图`
- `ui/` 目录 — 所有静态文件

### 已有 API endpoints
- `GET /api/curious/state` — 返回 `{knowledge, curiosity_queue, exploration_log, last_update}`
- `GET /api/curious/run` — POST 触发探索
- `GET /api/r1d3/unshared_discoveries` — R1D3 未分享发现
- `GET /api/r1d3/mark_shared` — POST 标记已分享

### 关键约束
- **Flask API 和 Daemon 是两个进程**：Flask 通过读 `state.json` 和 `dream_topic_inbox.json` 获取数据
- **Daemon 写，Flask 读**：Flask 不能访问 Daemon 的内存变量
- **数据文件路径**：
  - `knowledge/state.json` — KG + curiosity_queue
  - `knowledge/dream_topic_inbox.json` — DreamInbox（独立文件）
  - `knowledge/exploration_log` — 探索历史
- **Python 路径**：`cd /root/dev/curious-agent && python3 curious_api.py --port 4848`

---

## 一、API 层改动

### 1.1 新增 endpoint：`GET /api/curious/pipeline`

在 `curious_api.py` 中新增，读取所有状态文件，返回管道全景数据：

```python
@app.route("/api/curious/pipeline")
def api_pipeline():
    """返回管道全景数据：队列统计、流量速率、三代理状态"""
    import time
    from core import knowledge_graph as kg
    from pathlib import Path

    state = kg.get_state()
    topics = state.get("knowledge", {}).get("topics", {})
    queue = state.get("curiosity_queue", [])

    # DreamInbox（独立 JSON 文件）
    inbox_path = Path(__file__).parent / "knowledge" / "dream_topic_inbox.json"
    try:
        with open(inbox_path) as f:
            inbox_data = json.load(f)
        inbox = inbox_data.get("inbox", [])
    except Exception:
        inbox = []

    # === 流量速率计算（基于文件 mtime 变化率）===
    # 记录上次调用时的 KG count 和 timestamp，计算速度
    # 使用 module-level 变量缓存上次状态
    now = time.time()
    cache = _pipeline_cache  # module-level dict
    last_time = cache.get("last_time", now)
    last_kg = cache.get("last_kg", len(topics))
    last_queue = cache.get("last_queue", len(queue))
    last_inbox = cache.get("last_inbox", len(inbox))

    dt = now - last_time
    kg_rate = (len(topics) - last_kg) / dt if dt > 0 else 0
    queue_rate = (len(queue) - last_queue) / dt if dt > 0 else 0
    inbox_rate = (len(inbox) - last_inbox) / dt if dt > 0 else 0

    cache.update({
        "last_time": now, "last_kg": len(topics),
        "last_queue": len(queue), "last_inbox": len(inbox)
    })

    # === 队列按 status 分组 ===
    queue_by_status = {}
    for item in queue:
        s = item.get("status", "unknown")
        if s not in queue_by_status:
            queue_by_status[s] = []
        queue_by_status[s].append({
            "topic": item.get("topic", ""),
            "priority": item.get("priority", 5),
            "score": item.get("score", 0),
            "claimed_at": item.get("claimed_at"),
        })

    # === KG 按 status 分组 ===
    kg_by_status = {}
    for name, v in topics.items():
        s = v.get("status", "partial")
        if s not in kg_by_status:
            kg_by_status[s] = []
        kg_by_status[s].append(name)

    # === TRACE 专题追踪 ===
    trace_keywords = ["TRACE", "Hierarchical Trajectory", "AgentDiet",
                     "Agent trajectory", "Agentic skill", "OpenClaw agent"]
    def is_trace(topic):
        return any(k.lower() in topic.lower() for k in trace_keywords)

    trace_in_queue = [q for q in queue if is_trace(q.get("topic", ""))]
    trace_in_kg = [n for n in topics.keys() if is_trace(n)]
    trace_in_inbox = [i for i in inbox if is_trace(i.get("topic", ""))]

    # === 代理状态（从 exploration_log 最近条目推断）===
    log = state.get("exploration_log", [])
    last_explore = log[-1] if log else {}
    agent_status = {
        "spider": {
            "status": "running",
            "explored_total": len([n for n in topics.keys() if topics[n].get("status") == "complete"]),
            "last_topic": last_explore.get("topic", "N/A"),
        },
        "dream": {
            "status": "running",
            "insights_total": len(inbox),
            "inbox_size": len(inbox),
        },
        "pruner": {
            "status": "running",
            "last_prune": state.get("meta_cognitive", {}).get("last_prune_time", "N/A"),
        }
    }

    return jsonify({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline": {
            "queue": {
                "total": len(queue),
                "by_status": {s: len(v) for s, v in queue_by_status.items()},
                "rate_per_sec": round(queue_rate, 2),
            },
            "inbox": {
                "total": len(inbox),
                "rate_per_sec": round(inbox_rate, 2),
            },
            "kg": {
                "total": len(topics),
                "complete": len(kg_by_status.get("complete", [])),
                "partial": len(kg_by_status.get("partial", [])),
                "rate_per_sec": round(kg_rate, 2),
            },
        },
        "trace": {
            "queue": len(trace_in_queue),
            "kg": len(trace_in_kg),
            "inbox": len(trace_in_inbox),
            "queue_items": trace_in_queue[:5],
            "kg_items": trace_in_kg[:5],
        },
        "agents": agent_status,
        "queue_sample": queue_by_status.get("pending", [])[:10],
        "inbox_sample": inbox[-10:] if len(inbox) > 10 else inbox,
    })
```

在 `curious_api.py` 文件顶部（imports 后）添加缓存变量：
```python
_pipeline_cache = {
    "last_time": time.time(),
    "last_kg": 0,
    "last_queue": 0,
    "last_inbox": 0,
}
```

### 1.2 新增 endpoint：`GET /api/curious/loops`

返回最近 N 个处理事件（用于 LOOP 历史时间线）：

```python
@app.route("/api/curious/loops")
def api_loops():
    """返回最近 50 个 loop 事件"""
    from core import knowledge_graph as kg
    state = kg.get_state()
    log = state.get("exploration_log", [])
    # exploration_log 每条格式: {topic, status, timestamp, subtopics, quality, ...}
    # 最多返回最近 50 条
    recent = []
    for entry in reversed(log[-50:]):
        recent.append({
            "topic": entry.get("topic", ""),
            "status": entry.get("status", ""),
            "time": entry.get("timestamp", entry.get("completed_at", "")),
            "quality": entry.get("quality"),
            "subtopics_count": len(entry.get("subtopics", [])),
            "sources_count": len(entry.get("sources", [])),
        })
    return jsonify({"loops": list(reversed(recent))})
```

### 1.3 新增 endpoint：`GET /api/r1d3/consumption`

R1D3 消费端数据（被 R1D3 的 heartbeat 调用读取）：

```python
@app.route("/api/r1d3/consumption")
def api_r1d3_consumption():
    """返回 R1D3 消费端数据"""
    import os
    # 读取 curious-discoveries.md 索引
    idx_path = Path("/root/.openclaw/workspace-researcher/memory/curious-discoveries.md")
    shared = 0
    total_d = 0
    unshared_list = []
    if idx_path.exists():
        content = idx_path.read_text()
        # 格式: ## [score] Topic Name #tag1 #tag2 (shared: false)
        import re
        entries = re.findall(r'- \[\d+\.\d+\] (.+?) \(shared:\s*(true|false)\)', content)
        total_d = len(entries)
        shared = sum(1 for _, s in entries if s == "true")
        unshared_list = [name for name, s in entries if s == "false"][:10]

    # 读取 shared_knowledge 中发现的 md 文件
    shared_dir = Path("/root/.openclaw/workspace-researcher/memory/curious/")
    discovery_count = len(list(shared_dir.glob("*.md"))) if shared_dir.exists() else 0

    return jsonify({
        "total_discoveries": discovery_count,
        "indexed": total_d,
        "shared": shared,
        "unshared": total_d - shared,
        "unshared_list": unshared_list,
        "last_sync": datetime.now(timezone.utc).isoformat(),
    })
```

---

## 二、前端 UI 改动（增量）

### 2.1 新增 Tab 按钮

在 `ui/index.html` 的 `view-tabs` div 中（第 285-287 行附近）新增：

```html
<button class="view-tab" id="tab-pipeline" onclick="switchView('pipeline')">🔄 数据流</button>
```

### 2.2 switchView 函数扩展

在 `switchView()` 函数中（约第 601 行）添加：

```javascript
function switchView(view) {
    document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + view)?.classList.add('active');
    document.getElementById('view-list')?.style && (document.getElementById('view-list').style.display = view === 'list' ? '' : 'none');
    document.getElementById('view-graph')?.style && (document.getElementById('view-graph').style.display = view === 'graph' ? '' : 'none');
    // 新增：
    var pipelineEl = document.getElementById('view-pipeline');
    if (pipelineEl) pipelineEl.style.display = view === 'pipeline' ? '' : 'none';
    if (view === 'pipeline') loadPipeline();
}
```

### 2.3 新增 Pipeline 视图 HTML

在 `ui/index.html` 的 `view-graph` div 后面添加（大约第 750 行附近）：

```html
<div id="view-pipeline" style="display:none">
  <!-- 系统指标条 -->
  <div class="pipeline-stats" id="pipeline-stats"></div>

  <!-- 数据流可视化 -->
  <div class="pipeline-flow" id="pipeline-flow"></div>

  <!-- 底部两栏：LOOP历史 + TRACE追踪 -->
  <div class="pipeline-bottom">
    <div class="panel" style="flex:1">
      <div class="panel-header">
        <div class="panel-title">🔄 LOOP 历史</div>
        <button class="btn" onclick="loadLoops()">🔄</button>
      </div>
      <div class="panel-body" id="loops-list" style="max-height:400px;overflow-y:auto"></div>
    </div>
    <div class="panel" style="flex:1">
      <div class="panel-header">
        <div class="panel-title">🎯 TRACE 专题追踪</div>
      </div>
      <div class="panel-body" id="trace-tracker"></div>
    </div>
  </div>

  <!-- R1D3 消费链路 -->
  <div class="panel" style="margin-top:16px">
    <div class="panel-header">
      <div class="panel-title">🧠 R1D3 消费链路</div>
      <span class="stat-sub" id="r1d3-sync-time"></span>
    </div>
    <div class="panel-body" id="r1d3-consumption"></div>
  </div>
</div>
```

### 2.4 Pipeline CSS 样式

在 `<style>` 标签中（约第 250 行附近 `.panel` 样式后）添加：

```css
/* Pipeline 数据流视图 */
.pipeline-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.pipeline-stats .stat-card {
  min-width: 120px;
}
.pipeline-flow {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  overflow-x: auto;
}
.flow-row {
  display: flex;
  align-items: center;
  gap: 0;
  justify-content: center;
  margin-bottom: 16px;
}
.flow-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 140px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
  position: relative;
}
.flow-box.queue-box { border-color: #3fb950; }
.flow-box.inbox-box { border-color: #d29922; }
.flow-box.agent-box { border-color: #58a6ff; }
.flow-box.kg-box { border-color: #bc8cff; }
.flow-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.flow-count {
  font-size: 28px;
  font-weight: 700;
  color: var(--text);
}
.flow-rate {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
.flow-rate.positive { color: var(--green); }
.flow-rate.negative { color: var(--red); }
.flow-arrow {
  font-size: 24px;
  color: var(--text-muted);
  padding: 0 12px;
  position: relative;
}
.flow-arrow::after {
  content: attr(data-rate);
  position: absolute;
  top: -8px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 10px;
  color: var(--green);
  white-space: nowrap;
}
/* LOOP 历史 */
.loop-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(48,54,61,0.5);
  animation: fadeIn 0.3s ease;
}
.loop-item:last-child { border-bottom: none; }
.loop-icon { font-size: 16px; flex-shrink: 0; width: 24px; text-align: center; }
.loop-time { font-size: 11px; color: var(--text-muted); width: 65px; flex-shrink: 0; }
.loop-content { flex: 1; font-size: 12px; }
.loop-topic { color: var(--text); font-weight: 600; }
.loop-action { color: var(--text-muted); margin-left: 6px; }
.loop-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
/* TRACE 追踪 */
.trace-bar-container {
  margin-bottom: 12px;
  padding: 10px;
  background: var(--bg);
  border-radius: 6px;
  border: 1px solid var(--border);
}
.trace-name { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.trace-stages {
  display: flex;
  gap: 4px;
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
}
.trace-stage { padding: 2px 6px; border-radius: 4px; background: var(--surface); }
.trace-stage.active { background: var(--accent); color: #fff; }
.trace-stage.done { background: var(--green); color: #fff; }
/* 进度条 */
.prog { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; margin: 4px 0; }
.prog-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }
/* R1D3 消费 */
.consumption-flow {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.cons-box {
  padding: 10px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  text-align: center;
  min-width: 100px;
}
.cons-box.highlight { border-color: var(--accent); background: rgba(88,166,255,0.05); }
.cons-label { font-size: 11px; color: var(--text-muted); }
.cons-value { font-size: 20px; font-weight: 700; color: var(--accent); }
.cons-arrow { color: var(--text-muted); font-size: 18px; }
.health-status { display: flex; gap: 8px; flex-wrap: wrap; }
.health-item { padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.health-item.ok { background: rgba(63,185,80,0.15); color: var(--green); }
.health-item.slow { background: rgba(210,153,34,0.15); color: var(--yellow); }
.health-item.error { background: rgba(248,81,73,0.15); color: var(--red); }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
.pipeline-bottom { display: flex; gap: 16px; }
```

### 2.5 Pipeline JavaScript 函数

在 `<script>` 标签末尾添加（约第 900 行）：

```javascript
var pipelineData = null;
var loopsData = null;
var r1d3Data = null;

async function loadPipeline() {
    var [pipeRes, loopsRes, r1d3Res] = await Promise.all([
        fetch('/api/curious/pipeline'),
        fetch('/api/curious/loops'),
        fetch('/api/r1d3/consumption'),
    ]);
    pipelineData = await pipeRes.json();
    loopsData = await loopsRes.json();
    r1d3Data = await r1d3Res.json();
    renderPipelineStats(pipelineData);
    renderPipelineFlow(pipelineData);
    renderLoops(loopsData);
    renderTrace(pipelineData);
    renderR1D3Consumption(r1d3Data);
}

function renderPipelineStats(d) {
    var p = d.pipeline;
    var el = document.getElementById('pipeline-stats');
    if (!el) return;
    el.innerHTML = `
        <div class="stat-card">
            <div class="stat-label">KG</div>
            <div class="stat-value">${p.kg.total}</div>
            <div class="stat-sub">+${p.kg.rate_per_sec}/s</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Queue</div>
            <div class="stat-value">${p.queue.total}</div>
            <div class="stat-sub">${p.queue.by_status.pending || 0} pending</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">DreamInbox</div>
            <div class="stat-value">${p.inbox.total}</div>
            <div class="stat-sub">+${p.inbox.rate_per_sec}/s</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">TRACE 追踪</div>
            <div class="stat-value">${d.trace.queue + d.trace.kg}</div>
            <div class="stat-sub">Q:${d.trace.queue} KG:${d.trace.kg}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Spider 已探索</div>
            <div class="stat-value">${d.agents.spider.explored_total}</div>
            <div class="stat-sub">${d.agents.spider.last_topic ? '← ' + d.agents.spider.last_topic.slice(0,20) : ''}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Insights</div>
            <div class="stat-value">${d.agents.dream.insights_total}</div>
            <div class="stat-sub">DreamInbox</div>
        </div>
    `;
}

function renderPipelineFlow(d) {
    var p = d.pipeline;
    var el = document.getElementById('pipeline-flow');
    if (!el) return;
    el.innerHTML = `
        <div class="flow-row">
            <div class="flow-box queue-box">
                <div class="flow-label">curiosity_queue</div>
                <div class="flow-count">${p.queue.total}</div>
                <div class="flow-rate ${p.queue.rate_per_sec >= 0 ? 'positive' : 'negative'}">
                    ${p.queue.rate_per_sec >= 0 ? '+' : ''}${p.queue.rate_per_sec}/s
                </div>
            </div>
            <div class="flow-arrow" data-rate="+0.5/s">→</div>
            <div class="flow-box inbox-box">
                <div class="flow-label">DreamInbox</div>
                <div class="flow-count">${p.inbox.total}</div>
                <div class="flow-rate positive">+${p.inbox.rate_per_sec}/s</div>
            </div>
            <div class="flow-arrow" data-rate="+2/s">→</div>
            <div class="flow-box agent-box">
                <div class="flow-label">SpiderAgent</div>
                <div class="flow-count">1</div>
                <div class="flow-rate">exploring</div>
            </div>
            <div class="flow-arrow" data-rate="+0.8/s">→</div>
            <div class="flow-box kg-box">
                <div class="flow-label">KG</div>
                <div class="flow-count">${p.kg.total}</div>
                <div class="flow-rate positive">+${p.kg.rate_per_sec}/s</div>
            </div>
        </div>
        <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
            <div class="flow-box" style="border-color:#f472b6">
                <div class="flow-label">DreamAgent</div>
                <div class="flow-count">${p.inbox.total}</div>
                <div class="flow-rate positive">+${p.inbox.rate_per_sec}/s insights</div>
            </div>
            <div class="flow-arrow" style="color:#f472b6">↩</div>
            <div class="flow-box" style="border-color:#22d3ee">
                <div class="flow-label">Spider → Queue</div>
                <div class="flow-count">+${p.queue.rate_per_sec > 0 ? (p.queue.rate_per_sec * 5).toFixed(1) : '?'}/s</div>
                <div class="flow-rate positive">subtopics</div>
            </div>
            <div class="flow-arrow" style="color:#94a3b8">⏱</div>
            <div class="flow-box" style="border-color:#94a3b8">
                <div class="flow-label">Monitor claim</div>
                <div class="flow-count">60s</div>
                <div class="flow-rate">1 item/cycle</div>
            </div>
        </div>
    `;
}

function renderLoops(d) {
    var el = document.getElementById('loops-list');
    if (!el || !d.loops) return;
    el.innerHTML = d.loops.slice(-20).map(function(l) {
        var icon = l.status === 'complete' ? '🕷️' : l.status === 'exploring' ? '🔍' : '💤';
        var quality = l.quality ? `⭐${l.quality.toFixed(1)}` : '';
        var subtopics = l.subtopics_count ? `+${l.subtopics_count} subtopics` : '';
        return `
            <div class="loop-item">
                <div class="loop-icon">${icon}</div>
                <div class="loop-time">${l.time ? l.time.slice(11, 19) : ''}</div>
                <div class="loop-content">
                    <span class="loop-topic">${l.topic.slice(0, 40)}</span>
                    <span class="loop-action">${l.status} ${quality} ${subtopics}</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderTrace(d) {
    var el = document.getElementById('trace-tracker');
    if (!el) return;
    var items = (d.trace.queue_items || []).slice(0, 5);
    var kgItems = d.trace.kg_items || [];
    el.innerHTML = items.map(function(q) {
        var inKg = kgItems.some(function(n) { return n.includes(q.topic.split(' ')[0]); });
        var stages = ['pending', 'exploring', 'partial', 'complete'];
        var current = q.status || 'pending';
        var currentIdx = stages.indexOf(current);
        var pct = ((currentIdx + 1) / stages.length * 100).toFixed(0);
        return `
            <div class="trace-bar-container">
                <div class="trace-name">${q.topic.slice(0, 50)}</div>
                <div class="prog"><div class="prog-fill" style="width:${pct}%;background:var(--accent)"></div></div>
                <div class="trace-stages">
                    ${stages.map(function(s, i) {
                        var cls = i < currentIdx ? 'done' : i === currentIdx ? 'active' : '';
                        return '<span class="trace-stage ' + cls + '">' + s + '</span>';
                    }).join(' → ')}
                </div>
            </div>
        `;
    }).join('');
}

function renderR1D3Consumption(d) {
    var el = document.getElementById('r1d3-consumption');
    if (!el) return;
    document.getElementById('r1d3-sync-time').textContent = '最后同步: ' +
        (d.last_sync ? d.last_sync.slice(11, 19) : 'N/A');
    el.innerHTML = `
        <div class="consumption-flow">
            <div class="cons-box">
                <div class="cons-label">CA 发现</div>
                <div class="cons-value">${d.total_discoveries}</div>
            </div>
            <div class="cons-arrow">→</div>
            <div class="cons-box">
                <div class="cons-label">已索引</div>
                <div class="cons-value">${d.indexed}</div>
            </div>
            <div class="cons-arrow">→</div>
            <div class="cons-box highlight">
                <div class="cons-label">待分享</div>
                <div class="cons-value" style="color:#d29922">${d.unshared}</div>
            </div>
            <div class="cons-arrow">→</div>
            <div class="cons-box">
                <div class="cons-label">已分享 R1D3</div>
                <div class="cons-value" style="color:#3fb950">${d.shared}</div>
            </div>
            <div class="cons-arrow">→</div>
            <div class="cons-box">
                <div class="cons-label">用户会话</div>
                <div class="cons-value">💬</div>
            </div>
        </div>
        <div class="health-status">
            <span class="health-item ok">✅ CA→KG</span>
            <span class="health-item ok">✅ CA→shared</span>
            <span class="health-item ok">✅ shared→index</span>
            <span class="health-item slow">⚠️ index→R1D3 (心跳延迟)</span>
            <span class="health-item ok">✅ R1D3→用户</span>
        </div>
        ${d.unshared_list && d.unshared_list.length ? '<div style="margin-top:12px;font-size:12px;color:var(--text-muted)">待分享: ' + d.unshared_list.slice(0,3).join(', ') + '</div>' : ''}
    `;
}

async function loadLoops() {
    var res = await fetch('/api/curious/loops');
    var d = await res.json();
    renderLoops(d);
}

// 自动刷新：Tab 激活时每 5s 刷新
var pipelineInterval = null;
var originalSwitchView = switchView;
switchView = function(view) {
    originalSwitchView(view);
    if (view === 'pipeline') {
        loadPipeline();
        if (!pipelineInterval) pipelineInterval = setInterval(loadPipeline, 5000);
    } else {
        if (pipelineInterval) { clearInterval(pipelineInterval); pipelineInterval = null; }
    }
};
```

---

## 三、文件变更清单

| 文件 | 改动类型 | 描述 |
|------|---------|------|
| `curious_api.py` | 修改 | 新增 3 个 API endpoint + `_pipeline_cache` 缓存变量 |
| `ui/index.html` | 修改 | 新增 Tab 按钮 + Pipeline 视图 HTML + CSS + JS |

---

## 四、验收标准

### 功能验收
- [ ] 刷新 `ui/index.html`，点击「数据流」Tab 能正常显示
- [ ] Pipeline 数据每 5s 自动刷新
- [ ] 显示 KG / Queue / DreamInbox 三个数字和流速
- [ ] LOOP 历史显示最近 20 条探索记录
- [ ] TRACE 追踪显示队列中 TRACE topics 的阶段进度条
- [ ] R1D3 消费链路显示 5 个环节的健康状态

### 技术验收
- [ ] `curl http://localhost:4848/api/curious/pipeline` 返回正确 JSON
- [ ] `curl http://localhost:4848/api/curious/loops` 返回 JSON
- [ ] `curl http://localhost:4848/api/r1d3/consumption` 返回 JSON
- [ ] Tab 切换不破坏「列表视图」和「图谱视图」
- [ ] Pipeline 刷新不影响其他 Tab 的状态

---

## 五、R1D3 CA Skill 可视化（补充）

> 本节补充：R1D3 如何执行 CA skill（sync_discoveries.py / share_new_discoveries.py）的可视化

### 5.1 背景：R1D3 执行 CA skill 的流程

```
R1D3 Heartbeat（每 ~30 分钟）
  │
  ├─→ python3 sync_discoveries.py
  │       │
  │       ├─ 读取: /root/dev/curious-agent/knowledge/state.json
  │       ├─ 读取: .curious_last_sync（上次同步时间戳）
  │       ├─ 写入: memory/curious/*.md（每个发现一个文件）
  │       ├─ 更新: curious-discoveries.md（索引，shared:false）
  │       └─ 更新: .curious_last_sync
  │
  └─→ python3 share_new_discoveries.py --list
          │
          ├─ 读取: curious-discoveries.md
          ├─ 筛选: shared:false 的条目
          ├─ 输出: 高分未分享发现列表
          │
          └─ R1D3 主动分享给用户（飞书消息）
```

### 5.2 新增 API：`GET /api/r1d3/skill_status`

在 `curious_api.py` 中新增（R1D3 主动拉取 skill 执行状态）：

```python
@app.route("/api/r1d3/skill_status")
def api_r1d3_skill_status():
    """
    返回 R1D3 CA skill 的执行状态。
    R1D3 的 heartbeat 脚本会定期调用此接口，将结果写入记忆文件。
    """
    from pathlib import Path
    from datetime import datetime, timezone

    curious_dir = Path("/root/.openclaw/workspace-researcher/memory/curious")
    index_file = Path("/root/.openclaw/workspace-researcher/memory/curious-discoveries.md")
    last_sync_file = Path("/root/.openclaw/workspace-researcher/memory/.curious_last_sync")
    skill_log_file = Path("/root/.openclaw/workspace-researcher/memory/.ca_skill_execution_log")

    # 1. 最后同步时间
    last_sync = None
    if last_sync_file.exists():
        last_sync = last_sync_file.read_text().strip() or None

    # 2. 同步文件数量（memory/curious/*.md）
    md_files = list(curious_dir.glob("*.md")) if curious_dir.exists() else []

    # 3. 解析索引：统计 shared / unshared
    total_indexed = 0
    shared_count = 0
    unshared_items = []
    if index_file.exists():
        content = index_file.read_text()
        import re
        # 匹配: - [score] Title (#tag1 #tag2) (shared: true/false)
        entries = re.findall(
            r'- \[(\d+\.\d+)\] (.+?)(?:#[a-z0-9\-]+)* \(shared:\s*(true|false)\)',
            content
        )
        total_indexed = len(entries)
        shared_count = sum(1 for _, _, s in entries if s == "true")
        unshared_items = [
            {"score": float(sc), "title": t}
            for sc, t, s in entries if s == "false"
        ][:10]  # 最多 10 条

    unshared_count = total_indexed - shared_count

    # 4. 最近的 skill 执行日志（由 R1D3 heartbeat 写入）
    recent_runs = []
    if skill_log_file.exists():
        import json as json_mod
        try:
            with open(skill_log_file) as f:
                recent_runs = json_mod.load(f).get("runs", [])[-5:]
        except Exception:
            pass

    # 5. CA 发现总数（来自 state.json）
    from core import knowledge_graph as kg
    state = kg.get_state()
    kg_complete = len([n for n, v in state.get("knowledge", {}).get("topics", {}).items()
                       if v.get("status") == "complete"])
    kg_partial = len([n for n, v in state.get("knowledge", {}).get("topics", {}).items()
                      if v.get("status") == "partial"])

    # 6. 计算同步延迟（CA 发现到 R1D3 可见的延迟）
    sync_delay_minutes = None
    if last_sync:
        try:
            from datetime import datetime as dt_module
            last_dt = dt_module.fromisoformat(last_sync.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            sync_delay_minutes = round((now_dt - last_dt).total_seconds() / 60, 1)
        except Exception:
            pass

    return jsonify({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill": {
            "name": "ca_discovery_pipeline",
            "description": "R1D3 执行 CA sync + share skill",
            "last_sync": last_sync,
            "sync_delay_minutes": sync_delay_minutes,
            "sync_files_count": len(md_files),
        },
        "consumption": {
            "total_indexed": total_indexed,
            "shared": shared_count,
            "unshared": unshared_count,
            "unshared_items": unshared_items,
        },
        "ca_production": {
            "kg_complete": kg_complete,
            "kg_partial": kg_partial,
        },
        "pipeline_health": {
            "ca_to_shared": "ok" if md_files else "empty",
            "shared_to_index": "ok" if total_indexed > 0 else "empty",
            "index_to_r1d3": "slow" if sync_delay_minutes and sync_delay_minutes > 60 else "ok" if sync_delay_minutes else "unknown",
            "r1d3_to_user": "ok",
        },
        "recent_runs": recent_runs,
    })
```

### 5.3 R1D3 Skill 执行日志写入

R1D3 的 heartbeat 在每次执行 CA skill 后，将执行结果追加到记忆文件：

文件：`/root/.openclaw/workspace-researcher/memory/.ca_skill_execution_log`

```json
{
  "runs": [
    {
      "run_id": "2026-04-05T15:30:00Z",
      "sync_count": 3,
      "unshared_count": 12,
      "shared_to_user": 2,
      "duration_seconds": 4.2,
      "errors": [],
      "top_discovery": "TRACE evaluation framework (score: 9.2)"
    },
    ...
  ]
}
```

R1D3 heartbeat 脚本在 `sync_discoveries.py` 和 `share_new_discoveries.py` 执行后追加此日志。

### 5.4 前端 R1D3 Skill 可视化面板

在「数据流」Tab 的 R1D3 消费链路面板下方，新增「🧠 R1D3 CA Skill 执行」子面板：

```html
<!-- 插入到 r1d3-consumption div 之后 -->
<div class="panel" style="margin-top:16px">
  <div class="panel-header">
    <div class="panel-title">🧠 R1D3 CA Skill 执行</div>
    <span class="stat-sub" id="ca-skill-last-sync"></span>
  </div>
  <div class="panel-body">
    <div id="ca-skill-status"></div>
    <div id="ca-skill-runs" style="margin-top:12px"></div>
  </div>
</div>
```

新增 CSS（追加到 style 标签）：

```css
/* CA Skill 执行状态 */
.skill-run-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(48,54,61,0.5);
  font-size: 12px;
}
.skill-run-item:last-child { border-bottom: none; }
.skill-run-time { color: var(--text-muted); width: 70px; flex-shrink: 0; }
.skill-run-badge { padding: 2px 8px; border-radius: 10px; font-size: 11px; }
.skill-run-badge.ok { background: rgba(63,185,80,0.15); color: var(--green); }
.skill-run-badge.warn { background: rgba(210,153,34,0.15); color: var(--yellow); }
.skill-run-badge.error { background: rgba(248,81,73,0.15); color: var(--red); }
.skill-run-detail { color: var(--text-muted); }
.skill-exec-flow {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.skill-step {
  padding: 8px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  text-align: center;
  min-width: 90px;
}
.skill-step-icon { font-size: 16px; }
.skill-step-label { font-size: 10px; color: var(--text-muted); margin-top: 2px; }
.skill-step-value { font-size: 16px; font-weight: 700; }
```

新增 JavaScript 函数（追加到 script 标签）：

```javascript
async function loadSkillStatus() {
    var res = await fetch('/api/r1d3/skill_status');
    var d = await res.json();
    renderSkillStatus(d);
}

function renderSkillStatus(d) {
    var el = document.getElementById('ca-skill-status');
    if (!el) return;

    var syncTime = d.skill.last_sync
        ? d.skill.last_sync.replace('T', ' ').slice(0, 16)
        : '从未同步';
    var delayClass = !d.skill.sync_delay_minutes ? 'warn' :
                     d.skill.sync_delay_minutes > 60 ? 'warn' : 'ok';
    var delayText = !d.skill.sync_delay_minutes ? '未知' :
                    d.skill.sync_delay_minutes > 60 ? d.skill.sync_delay_minutes + 'min延迟' :
                    d.skill.sync_delay_minutes + 'min前';

    document.getElementById('ca-skill-last-sync').textContent =
        '最后同步: ' + syncTime + ' | 延迟: ' + delayText;

    el.innerHTML = `
        <div class="skill-exec-flow">
            <div class="skill-step">
                <div class="skill-step-icon">🔍</div>
                <div class="skill-step-value">${d.ca_production.kg_complete + d.ca_production.kg_partial}</div>
                <div class="skill-step-label">CA KG</div>
            </div>
            <div class="flow-arrow">→</div>
            <div class="skill-step">
                <div class="skill-step-icon">📁</div>
                <div class="skill-step-value">${d.skill.sync_files_count}</div>
                <div class="skill-step-label">memory/curious/</div>
            </div>
            <div class="flow-arrow">→</div>
            <div class="skill-step">
                <div class="skill-step-icon">📋</div>
                <div class="skill-step-value">${d.consumption.total_indexed}</div>
                <div class="skill-step-label">已索引</div>
            </div>
            <div class="flow-arrow">→</div>
            <div class="skill-step">
                <div class="skill-step-icon" style="color:#d29922">🔔</div>
                <div class="skill-step-value" style="color:#d29922">${d.consumption.unshared}</div>
                <div class="skill-step-label">待分享</div>
            </div>
            <div class="flow-arrow">→</div>
            <div class="skill-step">
                <div class="skill-step-icon" style="color:#3fb950">✅</div>
                <div class="skill-step-value" style="color:#3fb950">${d.consumption.shared}</div>
                <div class="skill-step-label">已分享</div>
            </div>
        </div>
        ${d.consumption.unshared_items.length ?
            '<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">待分享: ' +
            d.consumption.unshared_items.slice(0,3).map(function(i) {
                return '⭐' + i.score.toFixed(1) + ' ' + i.title.slice(0,30);
            }).join(' | ') + '</div>' : ''}
    `;

    // 最近 5 次执行
    var runsEl = document.getElementById('ca-skill-runs');
    if (runsEl && d.recent_runs.length) {
        runsEl.innerHTML = '<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">最近执行</div>' +
            d.recent_runs.map(function(r) {
                var badge = r.errors && r.errors.length
                    ? '<span class="skill-run-badge error">❌ ' + r.errors.length + ' errors</span>'
                    : '<span class="skill-run-badge ok">✅ ok</span>';
                return `
                    <div class="skill-run-item">
                        <div class="skill-run-time">${r.run_id ? r.run_id.slice(11,16) : ''}</div>
                        ${badge}
                        <div class="skill-run-detail">
                            sync+${r.sync_count} | 未分享+${r.unshared_count} | 已推送${r.shared_to_user} | ${r.duration_seconds}s
                        </div>
                    </div>`;
            }).join('');
    }
}

// 加载时一并拉取 skill_status
var originalRenderPipeline = renderR1D3Consumption;
renderR1D3Consumption = function(d) {
    originalRenderPipeline(d);
    loadSkillStatus();
};
```

### 5.5 R1D3 Skill 执行日志写入（heartbeat 改动）

在 R1D3 的 `HEARTBEAT.md` 的 sync 步骤中，更新为写入执行日志：

```bash
# 替换原来的纯 stdout，改为写日志文件
LOG_FILE="/root/.openclaw/workspace-researcher/memory/.ca_skill_execution_log"

# 执行 sync + share
SYNC_OUT=$(python3 skills/curious-agent/scripts/sync_discoveries.py 2>&1)
SHARE_OUT=$(python3 skills/curious-agent/scripts/share_new_discoveries.py --list 2>&1)

# 解析输出，提取 sync count
SYNC_COUNT=$(echo "$SYNC_OUT" | grep -oP 'SYNC: \K\d+' || echo 0)
UNSHARED=$(echo "$SHARE_OUT" | grep -oP '"undiscovered":\s*\K\d+' || echo 0)

# 追加到执行日志（保留最近 10 条）
python3 - << 'PYEOF'
import json, os
from datetime import datetime, timezone

log_file = os.environ.get('LOG_FILE', '/root/.openclaw/workspace-researcher/memory/.ca_skill_execution_log')
log_data = {"runs": []}
if os.path.exists(log_file):
    try:
        with open(log_file) as f:
            log_data = json.load(f)
    except: pass

log_data["runs"].append({
    "run_id": datetime.now(timezone.utc).isoformat(),
    "sync_count": int(os.environ.get('SYNC_COUNT', 0)),
    "unshared_count": int(os.environ.get('UNSHARED', 0)),
    "shared_to_user": 0,  # 由 share 步骤填充
    "duration_seconds": 0,
    "errors": [],
    "top_discovery": ""
})

# 只保留最近 10 条
log_data["runs"] = log_data["runs"][-10:]
with open(log_file, 'w') as f:
    json.dump(log_data, f, indent=2)
PYEOF
```

### 5.6 更新验收标准

在功能验收中补充：

| 验收项 | 验证方式 |
|--------|---------|
| CA Skill 执行面板显示 | 点击「数据流」Tab，滚动到底部看到 Skill 执行面板 |
| 最后同步时间正确 | 对比 `.curious_last_sync` 文件内容与页面显示 |
| 同步文件数正确 | 对比 `memory/curious/*.md` 文件数与页面显示 |
| 未分享列表正确 | 对比 `curious-discoveries.md` 中 shared:false 条目数 |
| 最近 5 次执行记录 | 页面底部显示历史执行记录 |
| 延迟标签正确 | 超过 60min 显示⚠️，否则显示✅ |

---

## 六、部署方式

```bash
# 重启 API server（Flask）
cd /root/dev/curious-agent
kill $(ps aux | grep "curious_api.py" | grep -v grep | awk '{print $1}')
python3 -u curious_api.py --port 4848 --no-browser >> logs/api.log 2>&1 &

# 访问
http://10.1.0.13:4848/
# 点击第三个 Tab「数据流」
```
