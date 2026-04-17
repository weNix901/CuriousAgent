# CA API 端点参考

> 按需加载。完整端点列表，含请求/响应格式。

## Hook 调用端点（5 个 Hook 实际使用）

| # | 端点 | 方法 | 调用方 Hook |
|---|------|------|-------------|
| 1 | `/api/knowledge/confidence?topic=xxx` | GET | knowledge-query |
| 2 | `/api/knowledge/learn` | POST | knowledge-learn |
| 3 | `/api/kg/overview` | GET | knowledge-bootstrap |
| 4 | `/api/knowledge/check` | POST | knowledge-gate |
| 5 | `/api/kg/confidence/<topic>` | GET | knowledge-gate |
| 6 | `/api/knowledge/record` | POST | knowledge-inject |

### 1. GET /api/knowledge/confidence

置信度查询。Hook knowledge-query 调用。

**请求**:
```
GET /api/knowledge/confidence?topic=<url_encoded_topic>
```

**响应** (200):
```json
{
  "status": "ok",
  "result": {
    "topic": "xxx",
    "confidence": 0.85,
    "level": "expert",
    "found": true
  }
}
```

### 2. POST /api/knowledge/learn

低置信度话题注入探索队列。Hook knowledge-learn 调用。

**请求**:
```json
{
  "topic": "xxx",
  "context": "Agent 回复内容摘要",
  "strategy": "llm_answer"
}
```

**响应** (200):
```json
{
  "success": true,
  "result": { "topic_id": "xxx", "status": "queued" }
}
```

### 3. GET /api/kg/overview

KG 概览。Hook knowledge-bootstrap 调用。

**响应** (200):
```json
{
  "nodes": [...],
  "edges": [...]
}
```

### 4. POST /api/knowledge/check

KG 知识存在性检查。Hook knowledge-gate 调用。

**请求**:
```json
{
  "topic": "xxx"
}
```

**响应** (200):
```json
{
  "success": true,
  "result": {
    "found": true,
    "confidence": 0.75,
    "status": "done"
  }
}
```

### 5. GET /api/kg/confidence/<topic>

话题置信度详情。Hook knowledge-gate 调用。

**响应** (200):
```json
{
  "confidence_low": [...],
  "confidence_high": [...]
}
```

### 6. POST /api/knowledge/record

知识记录到 KG。Hook knowledge-inject 调用。

**请求**:
```json
{
  "topic": "xxx",
  "content": "搜索结果摘要",
  "sources": ["https://..."]
}
```

**响应** (200):
```json
{
  "success": true,
  "result": { "node_created": "xxx" }
}
```

---

## Queue 管理

### GET /api/queue

查看队列。

**查询参数**: `?status=pending|done|failed`

**响应** (200):
```json
{
  "items": [
    {
      "id": "xxx",
      "topic": "xxx",
      "status": "pending",
      "score": 7.5,
      "depth": 5.0,
      "created_at": "2026-04-16T10:00:00Z"
    }
  ],
  "total": 10
}
```

### POST /api/queue/add

添加到队列。

**请求**:
```json
{
  "topic": "xxx",
  "score": 7.0,
  "reason": "manual inject"
}
```

### POST /api/queue/claim

认领队列项。

**请求**:
```json
{
  "item_id": "xxx",
  "holder_id": "explorer-1"
}
```

### POST /api/queue/done

标记完成。

**请求**:
```json
{
  "item_id": "xxx",
  "result": { "summary": "..." }
}
```

### POST /api/queue/failed

标记失败。

**请求**:
```json
{
  "item_id": "xxx",
  "error": "timeout"
}
```

### GET /api/curious/queue/pending

获取待处理项列表。

---

## KG 查询

### GET /api/kg/trace/<topic>

话题探索轨迹。

### GET /api/kg/roots

获取根节点列表。

### POST /api/kg/promote

提升节点。

### GET /api/kg/dream_insights

获取 Dream 洞察列表。

### GET /api/kg/dream_insights/<topic>

获取某话题的 Dream 洞察。

### GET /api/kg/dormant

获取休眠节点。

### POST /api/kg/reactivate

重新激活节点。

**请求**:
```json
{
  "topic": "xxx"
}
```

### GET /api/kg/frontier

获取前沿话题。

### GET /api/kg/calibration

校准数据。

---

## Explorer / Dream Agent

### POST /api/agents/explore

手动触发探索。

**请求**:
```json
{
  "topic": "xxx",
  "depth": "deep"
}
```

### POST /api/agents/dream

手动触发 Dream。

### POST /api/agents/daemon/explore

守护模式探索。

### POST /api/agents/daemon/dream

守护模式 Dream。

### GET /api/agents/status

获取 Agent 状态。

**响应** (200):
```json
{
  "explore_agent": { "status": "idle", "last_run": "..." },
  "dream_agent": { "status": "running", "last_run": "..." }
}
```

---

## 元认知

### GET /api/metacognitive/state

元认知状态。

### GET /api/metacognitive/check?topic=xxx

检查某话题的元认知状态。

### GET /api/metacognitive/history/<topic>

某话题的元认知历史。

### GET /api/metacognitive/topics/completed

已完成探索的话题列表。

---

## 其他

### GET /api/curious/state

CA 整体状态。

### POST /api/curious/run

手动运行探索。

### POST /api/curious/inject

探索注入（结构化）。

**请求**:
```json
{
  "topic": "xxx",
  "findings": {
    "summary": "...",
    "urls": ["https://..."]
  },
  "source": "r1d3",
  "depth": "deep"
}
```

### POST /api/curious/trigger

触发探索（简化版）。

### DELETE /api/curious/queue

清空队列。

### GET /api/quota/status

搜索配额状态。

### POST /api/quota/reset

重置配额。

### GET /api/discoveries

发现列表。

### POST /api/discoveries/<id>/share

标记发现为已分享。

### POST /api/curious/quality/assertion

质量断言。

### POST /api/auth/register

注册。

---

## Audit API (v0.3.1 NEW)

### GET /api/audit/hooks

Hook 调用记录查询。

**查询参数**: `?limit=50&offset=0&hook=knowledge-query`

**响应** (200):
```json
{
  "records": [
    {
      "id": 1,
      "hook_name": "knowledge-query",
      "endpoint": "/api/knowledge/confidence",
      "method": "GET",
      "status_code": 200,
      "status": "success",
      "latency_ms": 45,
      "agent_id": "r1d3",
      "timestamp": "2026-04-17T10:00:00Z"
    }
  ],
  "total": 100
}
```

### GET /api/audit/hooks/<hook_id>

单个 Hook 调用详情。

### GET /api/audit/hooks/stats

Hook 调用统计。

**响应** (200):
```json
{
  "hooks": {
    "knowledge-query": { "count": 50, "avg_latency_ms": 45, "success_rate": 0.95 },
    "knowledge-learn": { "count": 10, "avg_latency_ms": 120, "success_rate": 1.0 }
  },
  "total_calls": 60,
  "overall_success_rate": 0.97
}
```

### GET /api/audit/webhooks

Webhook 调用记录。

### GET /api/audit/agent/<agent_id>/activity

Agent 活动轨迹。

**响应** (200):
```json
{
  "agent_id": "r1d3",
  "activity": [
    { "hook_name": "knowledge-query", "timestamp": "...", "latency_ms": 45 }
  ]
}
```

---

## Explorer Trace API (v0.3.1 NEW)

### GET /api/explorer/active

活跃 Explorer 执行。

### GET /api/explorer/recent

最近 Explorer 执行。

**查询参数**: `?limit=20`

**响应** (200):
```json
{
  "traces": [
    {
      "trace_id": "xxx",
      "topic": "agent memory",
      "status": "done",
      "total_steps": 8,
      "quality_score": 7.5,
      "duration_ms": 4500
    }
  ]
}
```

### GET /api/explorer/trace/<trace_id>

单个 Explorer trace 详情。

**响应** (200):
```json
{
  "trace": { "trace_id": "xxx", "topic": "...", "status": "done" },
  "steps": [
    { "step_num": 1, "action": "search_web", "duration_ms": 500, "output_summary": "..." },
    { "step_num": 2, "action": "query_kg", "duration_ms": 100 }
  ]
}
```

---

## Dream Trace API (v0.3.1 NEW)

### GET /api/dream/active

活跃 Dream 执行。

### GET /api/dream/traces

Dream trace 列表。

**查询参数**: `?limit=20`

### GET /api/dream/trace/<trace_id>

单个 Dream trace 详情。

**响应** (200):
```json
{
  "trace_id": "xxx",
  "l1_count": 100,
  "l1_duration_ms": 500,
  "l2_count": 20,
  "l2_duration_ms": 300,
  "l3_count": 5,
  "l4_count": 3,
  "insights_generated": ["topic1", "topic2"]
}
```

### GET /api/dream/stats

Dream 统计。

**响应** (200):
```json
{
  "total_dreams": 50,
  "total_insights": 120,
  "avg_l1_candidates": 80,
  "avg_l2_scored": 15,
  "insight_by_type": { "cross_domain": 30, "surprise": 20 }
}
```

---

## KG Enhanced API (v0.3.1 NEW)

### GET /api/kg/nodes

KG 节点列表。

**查询参数**: `?limit=50&status=known`

**响应** (200):
```json
{
  "nodes": [
    { "id": "agent memory", "quality": 7.5, "status": "known", "exploration_count": 3 }
  ],
  "total": 100
}
```

### GET /api/kg/nodes/<node_id>

单个节点详情。

### GET /api/kg/edges

边列表。

### GET /api/kg/subgraph/<root_topic>

从 root 获取子图。

### GET /api/kg/stats

KG 统计。

**响应** (200):
```json
{
  "total_nodes": 100,
  "total_edges": 150,
  "avg_quality": 6.5,
  "status_distribution": { "known": 80, "unexplored": 20 }
}
```

### GET /api/kg/quality-distribution

质量分布。

---

## System Health API (v0.3.1 NEW)

### GET /api/system/health

系统健康状态。

**响应** (200):
```json
{
  "ca_api": { "status": "up", "uptime_seconds": 3600, "port": 4848 },
  "system": { "cpu_percent": 15.0, "memory_percent": 45.0 },
  "queue": { "pending": 5, "completed": 50 },
  "kg": { "total_nodes": 100 }
}
```

### GET /api/providers/heatmap

Provider 热力图 + 配额状态。

### POST /api/providers/record

记录 Provider 验证结果。

---

## Timeline API (v0.3.1 NEW)

### GET /api/timeline

全局事件时间线。

**查询参数**: `?limit=100`

**响应** (200):
```json
{
  "events": [
    { "timestamp": "...", "type": "hook_call", "emoji": "🔗", "summary": "knowledge-query → /api/knowledge/confidence → success" },
    { "timestamp": "...", "type": "exploration_done", "emoji": "✅", "summary": "探索完成: agent memory" },
    { "timestamp": "...", "type": "insight", "emoji": "💡", "summary": "洞察: cross_domain from topic1, topic2" }
  ],
  "total": 200
}
```

### GET /api/agents

已接入 Agent 列表。

**响应** (200):
```json
{
  "agents": [
    { "agent_id": "r1d3", "agent_name": "R1D3 Researcher", "total_calls": 50, "success_rate": 0.95 }
  ]
}
```

### GET /api/agents/<agent_id>

Agent 详情 + 活动轨迹。

---

## Decomposition API (v0.3.1 NEW)

### GET /api/decomposition/tree/<topic>

分解树。

**响应** (200):
```json
{
  "root": "agent memory",
  "tree": {
    "id": "agent memory",
    "children": [
      { "id": "short-term memory", "children": [] },
      { "id": "long-term memory", "children": [] }
    ]
  }
}
```

### GET /api/decomposition/stats

分解统计。
