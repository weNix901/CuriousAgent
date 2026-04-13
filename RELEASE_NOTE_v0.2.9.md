# Release Note - v0.2.9

## 🎯 核心主题：Agent 架构重构 + 知识结构化

v0.2.9 是 Curious Agent 的**架构重构版本**，将 SpiderAgent/DreamAgent 重构为真正的 Agent（ReAct 循环 + Tool 接口），同时建立结构化的知识表示系统。

---

## 🏗️ 核心架构变更

### 统一 CAAgent 框架

ExploreAgent 和 DreamAgent 成为同一个 `CAAgent` 类的不同配置实例，代码逻辑统一，仅配置不同。

```
┌─────────────────────────────────────────────────────────────┐
│                    CAAgent（统一 Agent 类）                   │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  AgentRunner（Nanobot ReAct 执行引擎）               │  │
│  │  • 统一 ReAct Loop                                 │  │
│  │  • Hook System（前后置回调）                        │  │
│  │  • Hermes ErrorClassifier（错误分层处理）           │  │
│  └─────────────────────────────────────────────────────┘  │
│                           │                               │
│                           ▼                               │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  ToolRegistry（统一 Tool 接口）                     │  │
│  │  • KG Tools（Neo4j）• Queue Tools（SQLite）       │  │
│  │  • Search Tools（多 Provider）• LLM Tools          │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌──────────────────┐      ┌──────────────────┐
│  ExploreAgent    │      │   DreamAgent     │
│  (ReAct 循环)    │      │  (多周期循环)      │
│  • 14 Tools     │      │  • 15 Tools     │
│  • 连续 Daemon  │      │  • Heartbeat 6h │
│  • 写 KG        │      │  • 只写 Queue   │
└──────────────────┘      └──────────────────┘
```

### 外部框架借鉴

| 模块 | 来源 | 说明 |
|------|------|------|
| `error_classifier.py` | Hermes Agent (NousResearch) | 错误分层处理 |
| `retry_utils.py` | Hermes Agent (NousResearch) | 重试策略 |
| `HeartbeatService` | Nanobot (HKUDS) | 心跳服务 |
| `AgentRunner` | Nanobot (HKUDS) | ReAct 执行引擎 |
| `AgentHook` | Nanobot (HKUDS) | Hook 回调系统 |

---

## 📦 新增模块

### core/agents/ — Agent 实现

| 文件 | 说明 |
|------|------|
| `ca_agent.py` | 统一 CAAgent 基类 |
| `explore_agent.py` | ExploreAgent（ReAct 循环，14 Tools） |
| `dream_agent.py` | DreamAgent（多周期循环，15 Tools） |
| `evolution.py` | Self-Evolution 引擎 |
| `hooks/explore_hook.py` | ExploreAgent Hook |
| `hooks/dream_hook.py` | DreamAgent Hook |

### core/tools/ — Tool 系统（21 个）

| 类别 | Tool 数量 | 说明 |
|------|----------|------|
| KG Tools | 9 个 | query_kg, add_to_kg, update_kg_status 等 |
| Queue Tools | 5 个 | add_to_queue, claim_queue, mark_done 等 |
| Search Tools | 5 个 | search_web, fetch_page, process_paper 等 |
| LLM Tools | 2 个 | llm_analyze, llm_summarize |

### core/frameworks/ — 执行框架

| 文件 | 说明 |
|------|------|
| `agent_runner.py` | Nanobot ReAct 执行引擎 |
| `agent_hook.py` | Hook 回调系统 |
| `error_classifier.py` | Hermes 错误分类器 |
| `retry_utils.py` | 重试策略工具 |
| `heartbeat.py` | Nanobot Heartbeat 服务 |

### core/daemon/ — Daemon 进程

| 文件 | 说明 |
|------|------|
| `explore_daemon.py` | ExploreAgent 连续守护（5s 轮询） |
| `dream_daemon.py` | DreamAgent 心跳守护（6h 触发） |

### core/configs/ — 配置系统

| 文件 | 说明 |
|------|------|
| `agent_explore.py` | ExploreAgent 配置 |
| `agent_dream.py` | DreamAgent 配置 |
| `llm_providers.py` | 多 LLM Provider 配置 |

### core/kg/ — 知识存储层

| 文件 | 说明 |
|------|------|
| `kg_repository.py` | KG Repository 抽象 |
| `neo4j_client.py` | Neo4j 操作封装 |

---

## 🔄 ExploreAgent（ReAct 循环）

### 工作流程
```
claim_topic → ReAct Loop(max 10次) → mark_done
```

### ReAct 循环
- **Thought** → LLM 思考下一步
- **Action** → 调用 Tool（search_web, fetch_page, llm_analyze 等）
- **Observation** → 观察结果，决定是否继续

### 搜索调用变化
| 对比项 | v0.2.8 (旧) | v0.2.9 (新) |
|--------|------------|------------|
| 搜索策略 | query_variants=2 多路搜索 | LLM ReAct 自主决策 |
| 每 topic 搜索 | 2+ 次（固定） | 1-2 次（自适应）|
| early_stop | 5 结果即停 | LLM 判断何时够 |
| **每日 Serper** | ~570 次 | **~200-1000 次** |
| **每日 Bocha** | ~120 次 | **~50-300 次** |

---

## 🌙 DreamAgent（多周期架构）

### 四层工序

| 层级 | 名称 | 职责 | 输入→输出 |
|------|------|------|----------|
| L1 | Light Sleep | 候选筛选 | ExplorationLog + KG 异常 → ≤100 候选 |
| L2 | Deep Sleep | 6 维评分 | 候选列表 → Top 20 ScoredCandidate |
| L3 | Filtering | 阈值门控 | ScoredCandidate → FilteredCandidate |
| L4 | REM Sleep | Queue 写入 | FilteredCandidate → Queue topic |

### 6 维评分信号

| 维度 | 权重 | 说明 |
|------|------|------|
| Relevance | 0.25 | 检索命中次数 |
| Frequency | 0.15 | 探索日志出现次数 |
| Recency | 0.15 | 时间衰减（半衰期 14 天）|
| Quality | 0.20 | KG 质量分数 |
| Surprise | 0.15 | 意外程度 |
| CrossDomain | 0.10 | 跨领域程度 |

### 关键变更
- **无搜索 API 调用**（纯 KG + LLM 分析）
- **只写 Queue，不写 KG**（探索工作交给 ExploreAgent）

---

## 📊 搜索 API 使用量变化

### 月度估算

| API | 每日 | **每月** | 推荐套餐 |
|-----|------|---------|---------|
| **Serper** | 200-1,000 次 | **6,000-30,000 次** | $49/月（3万次）|
| **Bocha** | 50-300 次 | **1,500-9,000 次** | Starter 5000 次 |

### vs v0.2.8

| 对比项 | v0.2.8 (旧) | v0.2.9 (新) |
|--------|------------|------------|
| DreamAgent 搜索 | 有（额外消耗）| **无** |
| 每 topic 搜索 | 固定 2+ 次 | 1-2 次（自适应）|
| Serper 月消耗 | ~17,100 次 | **6,000-30,000 次** |

---

## 📝 目录结构变更

```
core/
├── agents/              # 新增：Agent 实现
│   ├── ca_agent.py
│   ├── explore_agent.py
│   ├── dream_agent.py
│   ├── evolution.py
│   └── hooks/
├── tools/              # 新增：Tool 系统
│   ├── registry.py
│   ├── base.py
│   ├── kg_tools.py     (9)
│   ├── queue_tools.py  (5)
│   ├── search_tools.py (5)
│   └── llm_tools.py    (2)
├── frameworks/         # 新增：执行框架
│   ├── agent_runner.py
│   ├── agent_hook.py
│   ├── error_classifier.py
│   ├── retry_utils.py
│   └── heartbeat.py
├── daemon/             # 新增：Daemon 进程
│   ├── explore_daemon.py
│   └── dream_daemon.py
├── configs/            # 新增：配置系统
│   ├── agent_explore.py
│   ├── agent_dream.py
│   └── llm_providers.py
└── kg/                 # 新增：存储层
    ├── kg_repository.py
    └── neo4j_client.py
migrations/             # 新增：数据迁移
    └── migrate_json_to_neo4j.py
```

---

## 🧪 测试覆盖

| 测试类别 | 文件数 | 说明 |
|---------|-------|------|
| agents 测试 | 4 | ca_agent, explore_agent, dream_agent, hooks |
| frameworks 测试 | 4 | agent_runner, agent_hook, heartbeat, retry |
| tools 测试 | 6 | base, kg_tools, queue_tools, search_tools, llm_tools, registry |
| daemon 测试 | 2 | explore_daemon, dream_daemon |
| kg 测试 | 2 | kg_repository, neo4j_client |
| configs 测试 | 2 | configs, llm_providers |
| API 测试 | 1 | test_agent_api.py |
| E2E 测试 | 1 | test_real_exploration.py |
| 迁移测试 | 1 | test_migrate.py |

---

## 🔮 后续计划

- v0.3.0: Neo4j 存储正式启用，JSON 状态文件退役
- v0.3.1: Self-Evolution 引擎完善，贝叶斯权重更新
- v0.3.2: R1D3 Skill 接口集成

---

## 📈 变更统计

| 指标 | 值 |
|------|-----|
| 提交 | bef42f8 |
| 变更文件 | 104 个 |
| 新增行 | +16,270 |
| 删除行 | -47,135 |
| 新增模块 | ~25 个 |

---

_发布时间: 2026-04-13_  
_版本: v0.2.9_  
_重构者: weNix + R1D3 (OpenClaw Researcher)_
