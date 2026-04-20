# Curious Agent × OpenClaw 集成接入手册

> 适用版本：**Curious Agent v0.3.1** | OpenClaw 2026.3+
> 测试状态：**97+ 测试模块** | 最后更新：2026-04-17

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     OpenClaw 主 Agent (R1D3)                             │
│                                                                          │
│   OpenClaw Hooks (v0.3.0+)                                               │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │  knowledge-query   → GET /api/knowledge/confidence               │  │
│   │  knowledge-learn   → POST /api/knowledge/learn                    │  │
│   │  knowledge-bootstrap → GET /api/knowledge/session/startup           │  │
│   │  knowledge-gate    → POST /api/knowledge/check                    │  │
│   │  knowledge-inject  → POST /api/knowledge/record                   │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                              │                                           │
│                              ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Curious Agent API (port 4848)                                    │   │
│   │  • /api/knowledge/* — Cognitive Framework (v0.3.0)               │   │
│   │  • /api/audit/* — Hook Audit (v0.3.1 NEW)                        │   │
│   │  • /api/explorer/* — Trace Visualization (v0.3.1 NEW)            │   │
│   │  • /api/timeline — Global Event Stream (v0.3.1 NEW)              │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  CAAgent Unified Architecture                                    │   │
│   │  ┌──────────────────┐              ┌──────────────────┐         │   │
│   │  │  ExploreAgent    │              │   DreamAgent     │         │   │
│   │  │  (ReAct loop)    │              │  (L1→L4 cycle)   │         │   │
│   │  │  • 14 Tools      │              │  • 15 Tools      │         │   │
│   │  │  • TraceWriter   │              │  • DreamTrace    │         │   │
│   │  └──────────────────┘              └──────────────────┘         │   │
│   │                                                                  │   │
│   │  Daemons: ExploreDaemon (5min) + DreamDaemon (6h) + SleepPruner │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Observability Layer (v0.3.1 NEW)                                 │   │
│   │  • hook_audit.db — Hook call records                             │   │
│   │  • traces.db — Explorer/Dream execution traces                   │   │
│   │  • WebUI (4-tab dashboard)                                        │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**v0.3.1 核心特性**：

| 特性 | 说明 |
|------|------|
| **Cognitive Framework** | 4-level 置信度评估，R1D3 知道"知道自己知道什么" |
| **Unified CAAgent** | ExploreAgent + DreamAgent 共享同一基类，只有配置不同 |
| **ReAct Loop** | LLM 自主决定何时搜索、何时分析、何时停止 |
| **21 Tools** | KG (9) + Queue (5) + Search (5) + LLM (2) |
| **Hook Audit** | 所有 OpenClaw Hook 调用自动记录到 SQLite |
| **Trace Writers** | Explorer/Dream 执行轨迹完整记录 |
| **WebUI 4-Tab** | List + Graph + Internal + External 视图 |
| **Config-driven** | 所有参数通过 `config.json` 控制，零硬编码 |

---

## 二、前置条件

### 2.1 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.11+ |
| OpenClaw | 2026.3+ |
| 端口 | 4848 未被占用 |
| API Keys | BOCHA_API_KEY, SERPER_API_KEY, VOLCENGINE_API_KEY |

### 2.2 目录结构

```
/root/dev/curious-agent/
├── curious_agent.py          # CLI 入口 + Daemon orchestration
├── curious_api.py            # Flask API (~2700 lines)
├── config.json               # 中央配置文件
├── start.sh                  # 一键启动
│
├── core/
│   ├── trace/                # v0.3.1 NEW: Trace writers
│   │   ├── explorer_trace.py
│   │   └── dream_trace.py
│   │
│   ├── agents/               # Unified Agent framework
│   │   ├── ca_agent.py       # CAAgent 基类
│   │   ├── explore_agent.py  # ExploreAgent (ReAct)
│   │   └── dream_agent.py    # DreamAgent (L1→L4)
│   │
│   ├── tools/                # 21 Tools
│   │   ├── kg_tools.py       # KG Tools (9)
│   │   ├── queue_tools.py    # Queue Tools (5)
│   │   ├── search_tools.py   # Search Tools (5)
│   │   └── llm_tools.py      # LLM Tools (2)
│   │
│   ├── frameworks/           # ReAct engine
│   │   ├── agent_runner.py   # Nanobot ReAct
│   │   ├── error_classifier.py # Hermes error handling
│   │   └── heartbeat.py      # Nanobot Heartbeat
│   │
│   ├── daemon/               # Daemons
│   │   ├── explore_daemon.py
│   │   └── dream_daemon.py
│   │
│   ├── kg/                   # KG storage layer
│   │   ├── neo4j_client.py
│   │   └── json_kg_repository.py
│   │
│   ├── knowledge_graph.py    # KG logic
│   ├── curiosity_engine.py   # ICM fusion scoring
│   └── quality_v2.py         # Quality scoring
│
├── openclaw-hooks/           # v0.3.0+: 5 Hooks
│   ├── internal/
│   │   ├── knowledge-query/
│   │   ├── knowledge-learn/
│   │   ├── knowledge-bootstrap/
│   │   ├── knowledge-gate/   # v0.3.1 NEW
│   │   └──────────────────────────────────────────────────────────────
│   │   └──────────────────────────────────────────────────────────────
│   │
│   └──────────────────────────────────────────────────────────────────────
│
├── knowledge/                # Runtime data (gitignored)
│   ├── state.json            # KG state (~750KB)
│   ├── queue.db              # Queue storage
│   ├── hook_audit.db         # v0.3.1 NEW
│   ├── traces.db             # v0.3.1 NEW
│   └──────────────────────────────────────────────────────────────────────dream_insights/
│
├── ui/                       # v0.3.1 NEW: WebUI
│   ├── index.html            # 4-tab framework
│   ├── css/base.css
│   ├── js/*.js               # 5 JS modules
│   └──────────────────────────────────────────────────────────────────────views/*.html          # 4 view templates
│
└──────────────────────────────────────────────────────────────────────────────shared_knowledge/         # R1D3 ↔ CA sync
│   ├── ca/
│   ├── r1d3/
│   └──────────────────────────────────────────────────────────────────────assertion_index/
│
├── tests/                    # 97+ test modules
└──────────────────────────────────────────────────────────────────────────────
```

---

## 三、部署步骤

### Step 1：配置环境变量

```bash
# 编辑 ~/.bashrc
export BOCHA_API_KEY="your-bocha-api-key"
export SERPER_API_KEY="your-serper-api-key"
export VOLCENGINE_API_KEY="your-volcengine-api-key"

source ~/.bashrc
```

### Step 2：启动 Curious Agent

```bash
cd /root/dev/curious-agent

# 一键启动 API 服务
bash start.sh

# 或手动启动
python3 curious_api.py --port 4848
```

**验证启动**：

```bash
curl http://localhost:4848/api/curious/state
```

**预期输出**：

```json
{
  "status": "ok",
  "version": "v0.3.1"
}
```

### Step 3：启动 Daemon 模式（可选）

```bash
# 两代理 Daemon（推荐）
python3 curious_agent.py --daemon

# Ctrl+C 停止
```

**Daemon 说明**：

| Daemon | 间隔 | 职责 |
|--------|------|------|
| ExploreDaemon | 5min | 持续探索队列中的 topics |
| DreamDaemon | 6h | 生成跨领域创意洞察 |
| SleepPruner | 自适应 | KG 维护（修剪 dormant nodes） |

### Step 4：访问 WebUI

浏览器打开：http://10.1.0.13:4848/

**4 Tab 视图**：

| Tab | 内容 |
|-----|------|
| 📋 List | 好奇心队列、注入表单、探索历史、知识预览 |
| 🔮 Graph | D3.js 知识图谱（force simulation） |
| 🧭 Internal | Explorer/Dream traces、Queue/KG/System stats |
| 🪝 External | Hook 调用板、Agent 活动、Timeline |

---

## 四、API 端点参考

### 4.1 Hook 端点（5 Hooks 使用）

| 端点 | 方法 | Hook |
|------|------|------|
| `/api/knowledge/confidence` | GET | knowledge-query |
| `/api/knowledge/learn` | POST | knowledge-learn |
| `/api/knowledge/session/startup` | GET | knowledge-bootstrap |
| `/api/knowledge/check` | POST | knowledge-gate |
| `/api/knowledge/record` | POST | knowledge-inject |

### 4.2 Cognitive Framework API (v0.3.0)

```bash
# 置信度查询
curl "http://localhost:4848/api/knowledge/confidence?topic=agent+memory"

# 检查 + guidance
curl -X POST http://localhost:4848/api/knowledge/check \
  -H "Content-Type: application/json" \
  -d '{"topic": "FlashAttention"}'

# 注入未知 topic
curl -X POST http://localhost:4848/api/knowledge/learn \
  -H "Content-Type: application/json" \
  -d '{"topic": "FlashAttention", "strategy": "llm_answer"}'

# 记录搜索结果
curl -X POST http://localhost:4848/api/knowledge/record \
  -H "Content-Type: application/json" \
  -d '{"topic": "xxx", "content": "...", "sources": ["url"]}'
```

### 4.3 Observability API (v0.3.1 NEW)

```bash
# Hook 调用记录
curl "http://localhost:4848/api/audit/hooks?limit=20"

# Hook 统计
curl "http://localhost:4848/api/audit/hooks/stats"

# Explorer traces
curl "http://localhost:4848/api/explorer/recent?limit=10"
curl "http://localhost:4848/api/explorer/trace/<trace_id>"

# Dream traces
curl "http://localhost:4848/api/dream/stats"
curl "http://localhost:4848/api/dream/trace/<trace_id>"

# KG Enhanced
curl "http://localhost:4848/api/kg/nodes"
curl "http://localhost:4848/api/kg/stats"

# 系统健康
curl "http://localhost:4848/api/system/health"

# Provider 热力图 + 配额
curl "http://localhost:4848/api/providers/heatmap"

# 全局时间线
curl "http://localhost:4848/api/timeline?limit=50"

# Agent 列表
curl "http://localhost:4848/api/agents"
```

### 4.4 Queue 管理

```bash
# 查看队列
curl "http://localhost:4848/api/queue"

# 注入话题
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic": "xxx", "score": 7.0, "depth": 6.0}'

# 触发探索
curl -X POST http://localhost:4848/api/curious/run
```

---

## 五、OpenClaw Hook 安装

### 5.1 Internal Hooks

Internal Hooks 位于 `openclaw-hooks/internal/`，需要配置到 OpenClaw：

```json
// ~/.openclaw/openclaw.json
{
  "hooks": {
    "internal": [
      {
        "name": "knowledge-query",
        "path": "/root/dev/curious-agent/openclaw-hooks/internal/knowledge-query",
        "events": ["message:received"]
      },
      {
        "name": "knowledge-learn",
        "path": "/root/dev/curious-agent/openclaw-hooks/internal/knowledge-learn",
        "events": ["message:sent"]
      },
      {
        "name": "knowledge-bootstrap",
        "path": "/root/dev/curious-agent/openclaw-hooks/internal/knowledge-bootstrap",
        "events": ["session:start"]
      },
      {
        "name": "knowledge-gate",
        "path": "/root/dev/curious-agent/openclaw-hooks/internal/knowledge-gate",
        "events": ["message"]
      }
    ]
  }
}
```

### 5.2 Plugin Hooks (SDK)

Plugin Hooks 需要编译：

```bash
# knowledge-inject
cd /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-inject
npm install
npm run build

# knowledge-gate (plugin version)
cd /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-gate
npm install
npm run build
```

配置：

```json
{
  "hooks": {
    "plugins": [
      {
        "name": "knowledge-inject",
        "path": "/root/dev/curious-agent/openclaw-hooks/plugins/knowledge-inject"
      },
      {
        "name": "knowledge-gate",
        "path": "/root/dev/curious-agent/openclaw-hooks/plugins/knowledge-gate"
      }
    ]
  }
}
```

---

## 六、配置驱动

所有参数通过 `config.json` 控制：

```json
{
  "agents": {
    "explore": {
      "model": "volcengine",
      "max_iterations": 10,
      "tools": ["search_web", "query_kg", "add_to_kg", ...]
    },
    "dream": {
      "scoring_weights": {
        "relevance": 0.25,
        "quality": 0.20,
        "frequency": 0.15,
        "recency": 0.15,
        "surprise": 0.15,
        "cross_domain": 0.10
      },
      "min_score_threshold": 0.8
    }
  },
  "daemon": {
    "explore": { "poll_interval_seconds": 300 },
    "dream": { "interval_seconds": 21600 }
  },
  "knowledge": {
    "search": {
      "primary": "bocha",
      "fallback": "serper",
      "daily_quota": { "enabled": true, "serper": 100, "bocha": 50 }
    },
    "kg": { "enabled": false, "fallback_to_json": true }
  },
  "hooks": {
    "cognitive": {
      "confidence_threshold": 0.6,
      "auto_inject_unknowns": true
    }
  }
}
```

---

## 七、验证与测试

```bash
# 运行测试
cd /root/dev/curious-agent
python3 -m pytest tests/ --tb=no -q

# 检查 API
curl http://localhost:4848/api/system/health

# 检查 Hook audit
curl http://localhost:4848/api/audit/hooks/stats

# 检查 Explorer traces
curl http://localhost:4848/api/explorer/recent
```

---

## 八、故障排查

### 问题 1：端口被占用

```bash
# 检查端口
netstat -tlnp | grep 4848

# 杀死进程
pkill -f curious_api.py
```

### 问题 2：Hook 不触发

```bash
# 检查 OpenClaw 配置
cat ~/.openclaw/openclaw.json

# 检查 Hook 调用记录
curl http://localhost:4848/api/audit/hooks

# 确认 CA API 运行
curl http://localhost:4848/api/curious/state
```

### 问题 3：API Key 未配置

```bash
# 检查环境变量
echo $BOCHA_API_KEY
echo $SERPER_API_KEY

# 重新配置
source ~/.bashrc
```

---

## 九、文件路径速查

| 文件 | 路径 |
|------|------|
| API 服务 | `/root/dev/curious-agent/curious_api.py` |
| CLI 入口 | `/root/dev/curious-agent/curious_agent.py` |
| 配置文件 | `/root/dev/curious-agent/config.json` |
| 启动脚本 | `/root/dev/curious-agent/start.sh` |
| KG state | `/root/dev/curious-agent/knowledge/state.json` |
| Hook audit DB | `/root/dev/curious-agent/knowledge/hook_audit.db` |
| Traces DB | `/root/dev/curious-agent/knowledge/traces.db` |
| WebUI | `/root/dev/curious-agent/ui/index.html` |
| OpenClaw Hooks | `/root/dev/curious-agent/openclaw-hooks/` |

---

## 十、快速命令汇总

```bash
# === 启动 ===
cd /root/dev/curious-agent && bash start.sh

# === Daemon 模式 ===
python3 curious_agent.py --daemon

# === 注入话题 ===
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic": "xxx", "score": 7.0}'

# === 触发探索 ===
curl -X POST http://localhost:4848/api/curious/run

# === 查看状态 ===
curl http://localhost:4848/api/curious/state

# === 查看健康 ===
curl http://localhost:4848/api/system/health

# === Hook 统计 ===
curl http://localhost:4848/api/audit/hooks/stats

# === WebUI ===
# 浏览器打开 http://10.1.0.13:4848/

# === 测试 ===
python3 -m pytest tests/ --tb=no -q
```

---

## 十一、版本历史

| 版本 | 主题 |
|------|------|
| v0.3.1 | Observability Layer — Hook audit, trace visualization, WebUI 4-tab |
| v0.3.0 | Cognitive Framework — 4-level confidence, auto-inject unknowns |
| v0.2.9 | Agent Refactor — CAAgent unified class, 21 Tools, Hermes errors |
| v0.2.7 | Queue Atomicity + QualityV2 fix |
| v0.2.5 | Root Tracing (Spreading activation) |
| v0.2.3 | Full Capability Landing |
| v0.2.2 | Meta-cognitive Monitor |

---

## 十二、参考链接

- [Curious Agent README](file:///root/dev/curious-agent/README.md)
- [Curious Agent Architecture](file:///root/dev/curious-agent/ARCHITECTURE.md)
- [Release Note v0.3.1](file:///root/dev/curious-agent/RELEASE_NOTE_v0.3.1.md)
- [API Reference](file:///root/dev/curious-agent/skills/curious-agent/references/api.md)