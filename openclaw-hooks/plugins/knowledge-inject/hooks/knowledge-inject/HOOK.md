---
name: knowledge-inject
description: "After web_search tool calls → extract results → record to CA KG"
metadata:
  {
    "openclaw": {
      "emoji": "💉",
      "events": ["after_tool_call"],
      "requires": { "bins": ["node"] }
    }
  }
---

# Knowledge Inject Hook

当 agent 调用 web_search 后，自动提取搜索结果并记录到 CA 知识图谱。
依赖 v0.3.0 的 `/api/knowledge/record` 端点。

## What It Does

After agent uses web_search:
1. Extracts search result summary and URLs
2. Records topic + content + sources to CA KG
3. Fire-and-forget, doesn't block agent

## Requirements

- Node.js (for fetch API)
- CA service running on localhost:4848

## Configuration

Uses `CA_API_URL` environment variable (default: http://localhost:4848).
