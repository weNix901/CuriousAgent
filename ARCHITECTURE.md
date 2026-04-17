# Curious Agent Architecture (v0.3.1)

## 目标

一个具有"好奇心"的自主知识探索 Agent：主动追踪知识缺口，持续自主探索，并将发现内化为行为规则。

---

## 核心架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Curious Agent System                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    CAAgent (Unified Agent Class)                  │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │  AgentRunner (Nanobot ReAct engine)                      │    │   │
│  │  │  • Thought → Action → Observation loop                   │    │   │
│  │  │  • Hook System (pre/post callbacks)                      │    │   │
│  │  │  • ErrorClassifier (Hermes layered error handling)       │    │   │
│  │  │  • TraceWriter (v0.3.1 NEW - execution tracking)         │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  │                           │                                     │   │
│  │                           ▼                                     │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │  ToolRegistry (21 Tools, 4 categories)                   │    │   │
│  │  │  • KG (9)  • Queue (5)  • Search (5)  • LLM (2)          │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                    │                        │
│           ▼                                    ▼                        │
│  ┌──────────────────┐              ┌──────────────────┐                │
│  │  ExploreAgent    │              │   DreamAgent     │                │
│  │  (ReAct loop)    │              │  (L1→L4 cycle)   │                │
│  │  • 14 Tools      │              │  • 15 Tools      │                │
│  │  • Continuous    │              │  • Heartbeat 6h  │                │
│  │  • Writes KG     │              │  • Writes Queue  │                │
│  │  • TraceWriter   │              │  • DreamTrace    │                │
│  └──────────────────┘              └──────────────────┘                │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Daemons (24/7 Guardians)                       │   │
│  │  • ExploreDaemon (poll 5min)  • DreamDaemon (heartbeat 6h)        │   │
│  │  • SleepPruner (adaptive 4-24h)                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      OpenClaw Hooks (v0.3.0+)                             │
│  "Know what it knows, know what it doesn't know"                         │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Internal Hooks (知识注入到 R1D3)                                   │  │
│  │  knowledge-query   → GET /api/knowledge/confidence                │  │
│  │  knowledge-learn   → POST /api/knowledge/learn                    │  │
│  │  knowledge-bootstrap → GET /api/kg/overview                       │  │
│  │  knowledge-gate    → POST /api/knowledge/check                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Plugin Hooks (SDK integration)                                    │  │
│  │  knowledge-inject  → POST /api/knowledge/record                   │  │
│  │  knowledge-gate    → Confidence check before reply                │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  X-OpenClaw Headers (v0.3.1 NEW):                                       │
│  X-OpenClaw-Agent-Id, X-OpenClaw-Hook-Name,                             │
│  X-OpenClaw-Hook-Event, X-OpenClaw-Hook-Type                            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    Observability Layer (v0.3.1 NEW)                       │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Audit Middleware                                                 │   │
│  │  • before_request: g.start_time                                  │   │
│  │  • after_request: latency calculation → SQLite                   │   │
│  │  • Background worker thread                                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Trace Writers                                                    │   │
│  │  • TraceWriter: Explorer steps, tools, tokens, errors            │   │
│  │  • DreamTraceWriter: L1→L4 pipeline metrics                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Database Files                                                   │   │
│  │  • hook_audit.db  (~32KB)  Hook call records                     │   │
│  │  • traces.db      (~57KB)  Explorer/Dream traces                 │   │
│  │  • queue.db       (~32KB)  Queue storage                         │   │
│  │  • state.json     (~750KB) Knowledge graph state                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                       WebUI (v0.3.1 NEW)                                  │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  4-Tab Dashboard (http://10.1.0.13:4848/)                          │ │
│  │  📋 List View    → Curiosity queue, inject, history, knowledge    │ │
│  │  🔮 Graph View   → D3.js knowledge graph (force simulation)       │ │
│  │  🧭 Internal View → Explorer/Dream traces, Queue/KG/System stats  │ │
│  │  🪝 External View → Hook board, Agent activity, Timeline          │ │
│  └───────────────────────────────────────────────────────────────────┐ │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  File Structure                                                    │ │
│  │  ui/index.html        Tab framework                                │ │
│  │  ui/css/base.css      Extracted styles (193 lines)                 │ │
│  │  ui/js/base.js        Utility functions                            │ │
│  │  ui/js/list-view.js   List rendering                               │ │
│  │  ui/js/graph-view.js  D3.js graph                                  │ │
│  │  ui/js/internal-view.js  Internal panels                           │ │
│  │  ui/js/external-view.js  External panels                           │ │
│  │  ui/views/*.html      4 view templates                             │ │
│  └───────────────────────────────────────────────────────────────────┐ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 核心组件详解

### CAAgent (Unified Agent Class)

v0.2.9 重构后的统一 Agent 类。ExploreAgent 和 DreamAgent 只是 `CAAgent` 的不同配置。

**AgentRunner (Nanobot ReAct Engine)**
- Thought → Action → Observation 循环
- Hook System: `pre_tool_call`, `post_tool_call`, `pre_step`, `post_step`
- ErrorClassifier: Hermes 分层错误处理 (transient, permanent, retryable)
- TraceWriter (v0.3.1 NEW): 记录每一步执行轨迹

**ToolRegistry (21 Tools)**
- KG Tools (9): `query_kg`, `add_to_kg`, `update_kg_status`, `get_node_relations`, ...
- Queue Tools (5): `add_to_queue`, `claim_queue`, `mark_done`, `mark_failed`, `get_queue`
- Search Tools (5): `search_web`, `fetch_page`, `process_paper`, `analyze_pdf`, ...
- LLM Tools (2): `llm_analyze`, `llm_summarize`

### ExploreAgent

**ReAct Loop 探索**
- LLM 自主决定何时搜索、何时分析、何时停止
- 适应不同 topic 的复杂度
- 14 Tools: 搜索 + KG + Queue + LLM

**TraceWriter 注入** (v0.3.1)
```python
# explore_agent.py
from core.trace.explorer_trace import TraceWriter
trace_writer = TraceWriter()
trace_id = trace_writer.start_trace(topic)
# ... ReAct loop ...
trace_writer.finish_trace(trace_id, steps, quality_score)
```

### DreamAgent

**L1→L4 Insight Pipeline**
- L1 Light Sleep: ExplorationLog + KG anomalies → ≤100 candidates
- L2 Deep Sleep: 6-dimension scoring → Top 20
- L3 Filtering: Threshold gate → Filtered
- L4 REM Sleep: Generate queue topics

**6-dimension Scoring**
| Dimension | Weight |
|-----------|--------|
| Relevance | 0.25 |
| Quality | 0.20 |
| Frequency | 0.15 |
| Recency | 0.15 |
| Surprise | 0.15 |
| CrossDomain | 0.10 |

**Zero Search API** - 纯 KG + LLM 分析，不消耗 Serper/Bocha quota。

### Daemons

| Daemon | Schedule | Role |
|--------|----------|------|
| ExploreDaemon | Poll 5min | Continuous topic exploration |
| DreamDaemon | Heartbeat 6h | Creative insight generation |
| SleepPruner | Adaptive 4-24h | KG maintenance (prune dormant) |

---

## Observability Layer (v0.3.1)

### Audit Middleware

**Hook Call Tracking**
```
before_request:
  g.start_time = time.time()

after_request:
  latency_ms = (time.time() - g.start_time) * 1000
  _audit_queue.put({
    hook_name, endpoint, method, status_code,
    latency_ms, agent_id, timestamp
  })
```

**Background Worker**
- SQLite 写入 (`hook_audit.db`)
- 日志文件 (`logs/hook_access.log`)

### Trace Writers

**Explorer Trace Schema**
```sql
CREATE TABLE explorer_traces (
  trace_id, topic, started_at, finished_at,
  status, total_steps, tools_used, quality_score, error
);

CREATE TABLE trace_steps (
  step_id, trace_id, step_num, action,
  duration_ms, llm_tokens, output_summary
);
```

**Dream Trace Schema**
```sql
CREATE TABLE dream_traces (
  trace_id, started_at, finished_at,
  l1_count, l1_duration_ms,
  l2_count, l2_duration_ms,
  l3_count, l3_duration_ms,
  l4_count, l4_duration_ms,
  insights_generated
);
```

---

## API Endpoints Summary

### Core API (v0.2.x)

| Category | Endpoints |
|----------|-----------|
| State | `/api/curious/state` |
| Queue | `/api/curious/inject`, `/api/curious/run`, `/api/queue` |
| KG | `/api/kg/trace`, `/api/kg/roots`, `/api/kg/dream_insights` |

### Cognitive Framework (v0.3.0)

| Endpoint | Description |
|----------|-------------|
| `/api/knowledge/confidence` | KG confidence for topic |
| `/api/knowledge/check` | Confidence + guidance |
| `/api/knowledge/learn` | Inject unknown to queue |
| `/api/knowledge/record` | Save search results to KG |
| `/api/knowledge/analytics` | Cognitive stats |

### Observability API (v0.3.1)

| Category | Endpoints |
|----------|-----------|
| Audit | `/api/audit/hooks`, `/api/audit/hooks/stats`, `/api/audit/agent/<id>/activity` |
| Explorer | `/api/explorer/active`, `/api/explorer/recent`, `/api/explorer/trace/<id>` |
| Dream | `/api/dream/traces`, `/api/dream/trace/<id>`, `/api/dream/stats` |
| KG Enhanced | `/api/kg/nodes`, `/api/kg/edges`, `/api/kg/subgraph`, `/api/kg/stats` |
| System | `/api/system/health`, `/api/providers/heatmap` |
| Timeline | `/api/timeline`, `/api/agents`, `/api/agents/<id>` |

---

## 数据流

```
[R1D3 User Query]
    ↓
[knowledge-gate Hook]
    ↓ POST /api/knowledge/check
[CA API: KG Confidence Check]
    ↓ confidence < 0.3
[R1D3: Auto-inject unknown]
    ↓ POST /api/knowledge/learn
[CA Queue: New topic added]
    ↓
[ExploreDaemon: Poll queue]
    ↓
[ExploreAgent: ReAct loop]
    ↓ TraceWriter records steps
[KG: New knowledge written]
    ↓ quality ≥ 7.0
[Shared Knowledge: R1D3 reads discovery]
    ↓
[Next time: R1D3 knows the topic]
```

---

## 配置驱动

所有参数通过 `config.json` 控制，零硬编码：

```json
{
  "agents": {
    "explore": { "model", "max_iterations", "tools" },
    "dream": { "scoring_weights", "min_score_threshold" }
  },
  "daemon": {
    "explore": { "poll_interval_seconds", "max_retries" },
    "dream": { "interval_seconds" }
  },
  "knowledge": {
    "search": { "primary", "fallback", "daily_quota" },
    "kg": { "enabled", "uri", "fallback_to_json" }
  }
}
```

---

## 目录结构

```
curious-agent/
├── curious_agent.py              # CLI entry + daemon orchestration
├── curious_api.py                # Flask REST API (~2700 lines)
├── config.json                   # Central configuration
├── start.sh                      # One-command startup
│
├── core/
│   ├── trace/                    # v0.3.1 NEW: Trace writers
│   │   ├── __init__.py
│   │   ├── explorer_trace.py     # TraceWriter for ExploreAgent
│   │   └── dream_trace.py        # DreamTraceWriter for DreamAgent
│   │
│   ├── agents/                   # Unified Agent framework
│   │   ├── ca_agent.py           # CAAgent base class
│   │   ├── explore_agent.py      # ExploreAgent (ReAct + TraceWriter)
│   │   └── dream_agent.py        # DreamAgent (L1→L4 + DreamTrace)
│   │   └── evolution.py          # Self-Evolution engine
│   │
│   ├── tools/                    # Tool system
│   │   ├── registry.py           # ToolRegistry
│   │   ├── kg_tools.py           # KG Tools (9)
│   │   ├── queue_tools.py        # Queue Tools (5) + NEW methods
│   │   ├── search_tools.py       # Search Tools (5)
│   │   └── llm_tools.py          # LLM Tools (2)
│   │
│   ├── frameworks/               # Execution frameworks
│   │   ├── agent_runner.py       # ReAct engine
│   │   ├── agent_hook.py         # Hook callbacks
│   │   ├── error_classifier.py   # Hermes errors
│   │   ├── heartbeat.py          # Nanobot Heartbeat
│   │   └──────────────────────────────────────────────────────────────────────retry_utils.py        # Retry strategies
│   │
│   ├── daemon/                   # Daemon processes
│   │   ├── explore_daemon.py
│   │   └── dream_daemon.py
│   │
│   ├── kg/                       # Knowledge storage
│   │   ├── kg_repository.py
│   │   ├── neo4j_client.py
│   │   └──────────────────────────────────────────────────────────────────────json_kg_repository.py
│   │   └──────────────────────────────────────────────────────────────────────repository_factory.py
│   │
│   ├── knowledge_graph.py        # KG logic
│   ├── curiosity_engine.py       # ICM fusion
│   ├── quality_v2.py             # Quality scoring
│   └───────────────────────────────────────────────────────────────────────────────────────────────
│
├── openclaw-hooks/               # v0.3.0+: Hook system
│   ├── internal/                 # Internal hooks
│   │   ├── knowledge-query/
│   │   ├── knowledge-learn/
│   │   ├── knowledge-bootstrap/
│   │   ├── knowledge-gate/       # v0.3.1 NEW
│   │   └──────────────────────────────────────────────────────────────────────────────────────────────
│   │   └──────────────────────────────────────────────────────────────────────────────────────────────
│   │   └──────────────────────────────────────────────────────────────────────────────────────────────
│   │
│   ├── plugins/                  # Plugin hooks (SDK)
│   │   ├── knowledge-gate/
│   │   └──────────────────────────────────────────────────────────────────────────────────────────────
│   │
├── knowledge/                    # Runtime data (gitignored)
│   ├── state.json                # KG state (~750KB)
│   ├── queue.db                  # Queue storage
│   ├── hook_audit.db             # v0.3.1 NEW: Audit log
│   ├── traces.db                 # v0.3.1 NEW: Trace data
│   └──────────────────────────────────────────────────────────────────────────────────────────────────────dream_insights/
│   └──────────────────────────────────────────────────────────────────────────────────────────────────────
│
├── shared_knowledge/             # R1D3 ↔ CA sync layer
│   ├── ca/
│   ├── r1d3/
│   └──────────────────────────────────────────────────────────────────────────────────────────────────────
│
├── ui/                           # v0.3.1 NEW: WebUI
│   ├── index.html                # 4-tab framework
│   ├── css/
│   │   └──────────────────────────────────────────────────────────────────────────────────────────────base.css
│   ├── js/
│   │   ├── base.js
│   │   ├── list-view.js
│   │   ├── graph-view.js
│   │   ├── internal-view.js
│   │   └──────────────────────────────────────────────────────────────────────────────────────────────external-view.js
│   └──────────────────────────────────────────────────────────────────────────────────────────────────────views/
│   │   ├── list-view.html
│   │   ├── graph-view.html
│   │   ├── internal-view.html
│   │   └──────────────────────────────────────────────────────────────────────────────────────────────external-view.html
│
├── tests/                        # 97+ test modules
├── docs/                         # Design documents
└──────────────────────────────────────────────────────────────────────────────────────────────────────
```

---

## 版本演进

| Version | Theme |
|---------|-------|
| v0.3.1 | Observability Layer |
| v0.3.0 | Cognitive Framework |
| v0.2.9 | Agent Refactor (CAAgent) |
| v0.2.7 | Queue Atomicity |
| v0.2.5 | Root Tracing |
| v0.2.3 | Full Capability |
| v0.2.2 | Meta-cognitive Monitor |
| v0.2.1 | ICM Fusion |
| v0.1.0 | MVP (好奇心引擎) |

---

_设计理念：**好奇驱动，主动探索，元认知调控，自我进化**_