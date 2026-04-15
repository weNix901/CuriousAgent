---
name: knowledge-bootstrap
description: "Session startup → inject CA KG knowledge summary"
metadata:
  {
    "openclaw": {
      "emoji": "📚",
      "events": ["agent:bootstrap"],
      "requires": { "bins": ["node"] }
    }
  }
---

# Knowledge Bootstrap Hook

Session 启动时注入 CA 最近探索的高价值知识摘要。
依赖 v0.3.0 的 `/api/kg/overview` 端点。

## What It Does

When a new session starts:
1. Queries CA KG overview
2. Injects recent high-value knowledge summary
3. Agent starts with context of previous explorations

## Requirements

- Node.js (for fetch API)
- CA service running on localhost:4848

## Configuration

Uses `CA_API_URL` environment variable (default: http://localhost:4848).

## Disabling

openclaw hooks disable knowledge-bootstrap