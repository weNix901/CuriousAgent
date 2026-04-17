# Release Note v0.3.1

**Release Date:** 2026-04-17

**Theme:** Hook 调用观测 + CA 内部工作全景可视化 + 外部 Agent 交互可追溯 + WebUI 多文件拆分

---

## Overview

v0.3.1 在 v0.3.0 Cognitive Framework 基础上，增加了完整的可观测性层（Observability Layer）：

1. **Hook Audit Middleware** - 捕获所有 OpenClaw Hook 调用，记录到 SQLite + 日志
2. **Internal Trace Writers** - Explorer/Dream Agent 执行轨迹写入数据库
3. **External Agent Tracking** - Agent 注册、活动轨迹、全局时间线
4. **WebUI Multi-file Architecture** - 4 Tab 框架 + 模块化 JS/CSS

---

## New Features

### Phase 0: Hook Audit Infrastructure

**Audit Middleware** (`curious_api.py` lines 27-214)

- `before_request` 记录请求开始时间 (`g.start_time`)
- `after_request` 计算 latency，写入 `_audit_queue`
- Background worker thread 写入 SQLite (`hook_audit.db`)
- 所有 Hook endpoint 自动审计

**Audit API Endpoints** (6 endpoints)

| Endpoint | Description |
|----------|-------------|
| `/api/audit/hooks` | Query Hook call records (paginated, filtered) |
| `/api/audit/hooks/<hook_id>` | Single Hook call detail |
| `/api/audit/hooks/stats` | Hook call statistics (counts, latency, success rate) |
| `/api/audit/webhooks` | Webhook call records |
| `/api/audit/agent/<agent_id>/activity` | Agent activity timeline |
| `/api/audit/sessions/<session_id>` | Session context retrieval |

**X-OpenClaw Headers** (all 5 hooks)

```
X-OpenClaw-Agent-Id: r1d3
X-OpenClaw-Hook-Name: knowledge-query
X-OpenClaw-Hook-Event: message:received
X-OpenClaw-Hook-Type: internal
```

### Phase 1: Internal Visualization

**Trace Writers** (`core/trace/`)

- `TraceWriter` - Explorer Agent 执行轨迹 (steps, tools, tokens, errors)
- `DreamTraceWriter` - Dream Agent L1→L4 pipeline metrics

**QueueStorage Methods** (`core/tools/queue_tools.py`)

- `get_item(item_id)` - Single queue item
- `get_items_by_topic(topic)` - Items by topic
- `get_all_stats()` - Complete queue statistics

**KG Enhanced API** (6 endpoints)

| Endpoint | Description |
|----------|-------------|
| `/api/kg/nodes` | List all KG nodes |
| `/api/kg/nodes/<node_id>` | Single node detail |
| `/api/kg/edges` | List all edges |
| `/api/kg/subgraph/<root>` | Get subgraph from root |
| `/api/kg/stats` | KG statistics |
| `/api/kg/quality-distribution` | Quality score distribution |

**Explorer/Dream Trace API** (8 endpoints)

| Endpoint | Description |
|----------|-------------|
| `/api/explorer/active` | Active Explorer traces |
| `/api/explorer/recent` | Recent Explorer traces |
| `/api/explorer/trace/<id>` | Single Explorer trace detail |
| `/api/dream/active` | Active Dream trace |
| `/api/dream/traces` | Dream trace list |
| `/api/dream/trace/<id>` | Single Dream trace detail |
| `/api/dream/stats` | Dream statistics |
| `/api/decomposition/tree/<topic>` | Decomposition tree |
| `/api/decomposition/stats` | Decomposition statistics |

**System Health API**

| Endpoint | Description |
|----------|-------------|
| `/api/system/health` | System health (CPU, memory, queue, KG stats) |
| `/api/providers/heatmap` | Provider heatmap + quota status |
| `/api/providers/record` | Record provider verification result |

**Timeline API**

| Endpoint | Description |
|----------|-------------|
| `/api/timeline` | Global event timeline (hook calls, explorations, insights) |
| `/api/agents` | Registered agents list |
| `/api/agents/<agent_id>` | Agent detail + activity |

### Phase 3: WebUI Multi-file Architecture

**4-Tab Framework**

| Tab | Content |
|-----|---------|
| 📋 List View | Curiosity queue, inject form, history, knowledge, metacognitive state |
| 🔮 Graph View | D3.js knowledge graph with force simulation |
| 🧭 Internal View | Explorer traces, Dream stats, Queue status, KG stats, System health |
| 🪝 External View | Hook board, Agent activity, Timeline |

**File Structure**

```
ui/
├── index.html           # Tab framework + shared components
├── css/
│   └── base.css         # Extracted styles (193 lines)
├── js/
│   ├── base.js          # Utility functions + state management
│   ├── list-view.js     # List rendering logic
│   ├── graph-view.js    # D3.js graph rendering
│   ├── internal-view.js # Internal visualization panels
│   └── external-view.js # External interaction panels
└── views/
    ├── list-view.html   # List view template
    ├── graph-view.html  # Graph view template
    ├── internal-view.html # Internal view template
    └── external-view.html # External view template
```

---

## Bug Fixes

### Critical

| Issue | File | Fix |
|-------|------|-----|
| Endpoint mismatch | `knowledge-query/handler.ts` | `/api/r1d3/confidence` → `/api/knowledge/confidence` |
| Flask Request attribute | `curious_api.py:191` | `request._start_time` → `g.start_time` |
| Missing holder_id | `curious_api.py:2021` | Add `holder_id` to `mark_done` |
| Missing holder_id | `curious_api.py:2049` | Add `holder_id` to `mark_failed` |

### Gitignore Fixes

- `knowledge/queue.db` removed from tracking
- `knowledge/hook_audit.db` added to gitignore
- `knowledge/traces.db` added to gitignore
- `node_modules/` added to gitignore

---

## Database Files

| File | Purpose | Size |
|------|---------|------|
| `knowledge/hook_audit.db` | Hook call records | ~32KB |
| `knowledge/traces.db` | Explorer/Dream traces | ~57KB |
| `knowledge/queue.db` | Queue storage | ~32KB |

---

## API Summary

**Total new endpoints:** ~30

**Hook endpoints verified:**

| Hook | Endpoint | Status |
|------|----------|--------|
| knowledge-query | `/api/knowledge/confidence` | ✅ |
| knowledge-learn | `/api/knowledge/learn` | ✅ |
| knowledge-bootstrap | `/api/kg/overview` | ✅ |
| knowledge-gate | `/api/knowledge/check` + `/api/kg/confidence/<topic>` | ✅ |
| knowledge-inject | `/api/knowledge/record` | ✅ |

---

## Testing

- 5 integration tests passing (`test_api_knowledge_integration.py`)
- Python syntax verified
- CA API startup verified (port 4848)

---

## Migration Guide

### From v0.3.0

1. **No breaking changes** - All v0.3.0 endpoints still work
2. **New databases** created automatically at startup:
   - `hook_audit.db` - created by `_ensure_audit_db()`
   - `traces.db` - created by `TraceWriter.__init__()`
3. **WebUI** - Open http://10.1.0.13:4848/ for 4-tab dashboard

### Configuration

No new config required. All audit/trace parameters are internal defaults.

---

## Files Changed

```
35 files changed, 3077 insertions(+), 1144 deletions(-)
```

**New files:**
- `core/trace/__init__.py`
- `core/trace/explorer_trace.py`
- `core/trace/dream_trace.py`
- `openclaw-hooks/internal/knowledge-gate/HOOK.md`
- `openclaw-hooks/internal/knowledge-gate/handler.ts`
- `ui/css/base.css`
- `ui/js/*.js` (5 files)
- `ui/views/*.html` (4 files)

**Modified files:**
- `curious_api.py` (+1142 lines)
- `core/tools/queue_tools.py` (+70 lines)
- `core/agents/explore_agent.py` (+47 lines)
- `core/agents/dream_agent.py` (+37 lines)
- `ui/index.html` (rewrite)
- 5 hook handlers (headers added)

**Removed:**
- `tests/test_api_r1d3_integration.py` (renamed to `test_api_knowledge_integration.py`)