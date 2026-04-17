---
name: knowledge-query
description: "Intercept user messages → query CA KG confidence → inject knowledge context"
metadata:
  {
    "openclaw": {
      "emoji": "🧠",
      "events": ["message:received"],
      "requires": { "bins": ["node"] }
    }
  }
---

# Knowledge Query Hook

在 Agent 回答前查询 CA 知识图谱置信度，将相关知识注入上下文。
依赖 v0.3.0 的 `/api/knowledge/confidence` 端点。

## What It Does

When a user sends a message:
1. Extracts the topic from the message
2. Queries CA API for KG confidence
3. Injects knowledge context into agent conversation

## Requirements

- Node.js (for fetch API)
- CA service running on localhost:4848

## Configuration

Uses `CA_API_URL` environment variable (default: http://localhost:4848).

## Disabling

openclaw hooks disable knowledge-query