---
name: knowledge-gate
description: "Before agent replies → query CA KG → inject context based on confidence"
metadata:
  {
    "openclaw": {
      "emoji": "🚦",
      "events": ["before_agent_reply"],
      "requires": { "bins": ["node"] }
    }
  }
---

# Knowledge Gate Hook

Agent 回复前查询 CA 知识图谱，根据置信度注入知识上下文。

## What It Does

Before agent replies:
1. Extracts topic from user message
2. Queries CA KG confidence (`/api/knowledge/check`)
3. Injects context based on confidence level:
   - ≥85%: "KG 有完整知识"
   - 60-85%: "KG 有部分知识，建议搜索补充"
   - <60%: "KG 知识有限"
4. Non-blocking, silent failure

## Requirements

- Node.js (for fetch API)
- CA service running on localhost:4848

## Configuration

Uses `CA_API_URL` environment variable (default: http://localhost:4848).

## X-OpenClaw Headers

```
X-OpenClaw-Agent-Id: r1d3
X-OpenClaw-Hook-Name: knowledge-gate
X-OpenClaw-Hook-Event: message
X-OpenClaw-Hook-Type: plugin_sdk
```