# Curious Agent MVP - Architecture

## 目标
一个具有"好奇心"的 Agent 原型：主动追踪知识缺口，持续自主探索，而非被动响应。

## 核心组件

```
curious_agent/
├── curious_agent.py          # 🚀 入口 + 调度器
├── core/
│   ├── knowledge_graph.py     # 知识图谱 - 已知/未知节点
│   ├── curiosity_engine.py   # 🧠 好奇心引擎 - 评分 & 优先级排序
│   └── explorer.py           # 🔍 探索器 - 实际执行调查
└── knowledge/
    └── state.json            # 持久化状态
```

## 工作流程

```
[调度器 触发]
    ↓
[好奇心引擎] → 从 state.json 加载知识图谱 + 好奇心队列
    ↓
[选择 Top 1 好奇心项]（基于: 相关性 × 时效性 × 深度）
    ↓
[探索器] → 生成搜索词 / 深度思考 / 知识推导
    ↓
[更新知识图谱] → 发现的新知识写入 state.json
    ↓
[评估是否通知用户] → 有意义的新发现 → 飞书通知
    ↓
[等待下一轮调度]
```

## 好奇心评分公式

```
Score(topic) = Relevance(user_interest) × Recency(news_count) × Depth(gap_level)
```

- **Relevance**: 与用户 / 项目相关性 (0-10)
- **Recency**: 多久没更新了，越久分越高 (0-10)
- **Depth**: 知识缺口深度，越深越好奇 (0-10)

## 知识图谱状态 (state.json)

```json
{
  "version": "1.0",
  "last_update": "ISO timestamp",
  "knowledge": {
    "topics": {
      "topic_name": {
        "known": true/false,
        "depth": 0-10,
        "last_updated": "ISO",
        "sources": ["url1", "url2"],
        "summary": "..."
      }
    }
  },
  "curiosity_queue": [
    {
      "topic": "metacognition in AI agents",
      "score": 8.5,
      "reason": "深度理解用户 weNix 的研究方向",
      "created_at": "ISO",
      "status": "pending|investigating|done|paused"
    }
  ],
  "exploration_log": [
    {
      "timestamp": "ISO",
      "topic": "...",
      "action": "search|infer|derive",
      "findings": "...",
      "notified_user": true/false
    }
  ]
}
```

## MVP 范围 (v0.1)

### ✅ 实现
- 好奇心引擎（评分 + 队列管理）
- 探索器（基于推理 + 有限 web search）
- 状态持久化
- 飞书通知

### ⏳ 后续迭代
- 真正的 web search 集成
- 知识图谱可视化
- 多维度好奇心策略
- 与 OpenCode/OMO 系统集成
