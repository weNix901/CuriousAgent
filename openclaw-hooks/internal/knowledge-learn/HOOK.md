---
name: knowledge-learn
description: "After agent replies → detect low confidence → inject to CA exploration queue"
metadata:
  {
    "openclaw": {
      "emoji": "🔍",
      "events": ["message:sent"],
      "requires": { "bins": ["node"] }
    }
  }
---

# Knowledge Learn Hook

检测低置信度回答并自动注入 CA 探索队列。
依赖 v0.3.0 的 `/api/knowledge/learn` 端点。

## What It Does

After agent sends a reply:
1. Detects low confidence markers in response
2. Extracts uncertain topic
3. Injects topic to CA queue for exploration

## Requirements

- Node.js (for fetch API)
- CA service running on localhost:4848

## Configuration

Uses `CA_API_URL` environment variable (default: http://localhost:4848).

## Disabling

openclaw hooks disable knowledge-learn