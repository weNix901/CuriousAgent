# CA API 端点参考

> 按需加载。完整端点列表，含请求/响应格式。

## Hook 调用端点（5 个 Hook 实际使用）

| # | 端点 | 方法 | 调用方 Hook |
|---|------|------|-------------|
| 1 | `/api/r1d3/confidence?topic=xxx` | GET | knowledge-query |
| 2 | `/api/knowledge/learn` | POST | knowledge-learn |
| 3 | `/api/kg/overview` | GET | knowledge-bootstrap |
| 4 | `/api/knowledge/check` | POST | knowledge-gate |
| 5 | `/api/kg/confidence/<topic>` | GET | knowledge-gate |
| 6 | `/api/knowledge/record` | POST | knowledge-inject |

### 1. GET /api/r1d3/confidence

置信度查询。Hook knowledge-query 调用。

**请求**:
```
GET /api/r1d3/confidence?topic=<url_encoded_topic>
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
