---
name: knowledge-gate
description: "Before agent replies → dual-check CA KG → inject context"
metadata:
  {
    "openclaw": {
      "emoji": "🚦",
      "events": ["message"],
      "requires": { "bins": ["node"] }
    }
  }
---

# Knowledge Gate Hook

Reply 前查询 CA 知识图谱，注入知识上下文。