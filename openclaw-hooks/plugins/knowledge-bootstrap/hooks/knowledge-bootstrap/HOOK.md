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
依赖 `/api/knowledge/session/startup` 端点（2026-10-07 从已删除的 `/api/kg/overview` 切换）。

## What It Does

When a new session starts:
1. Queries CA `GET /api/knowledge/session/startup`
2. Injects the assembled injection content (KG summary + cognitive framework + skill rules + topic extraction)
3. **Always** injects 置信度感知回答行为规范（confidence-aware answering rules）
4. Agent starts with context of previous explorations + correct answering posture

## Requirements

- Node.js (for fetch API)
- CA service running on localhost:4848

## Configuration

Uses `CA_API_URL` environment variable (default: http://localhost:4848).

Can be configured via CA Web UI "Bootstrap Hook 配置" panel.

## Disabling

openclaw hooks disable knowledge-bootstrap