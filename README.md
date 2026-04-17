# 👁️ Curious Agent

[![Status](https://img.shields.io/badge/status-v0.3.1-blue)](#)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](#)
[![OpenClaw](https://img.shields.io/badge/openclaw-2026.3+-green)](#)
[![Tests](https://img.shields.io/badge/tests-97%20modules-brightgreen)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](#)

**Autonomous knowledge explorer that builds, traces, and evolves a living knowledge graph — without being asked.**

> 不是等待提问的搜索引擎，而是**主动构建知识图谱**、**持续追踪知识缺口**、**把发现内化为行为**的自主 Agent。

---

## What Is Curious Agent?

Curious Agent is a **self-evolving knowledge explorer** that runs as an OpenClaw plugin. It doesn't wait for questions — it generates its own curiosity, explores gaps in its knowledge graph, scores every discovery for quality, and promotes high-value findings into behavioral rules that permanently change how the host Agent thinks and acts.

**The analogy:** If a search engine is a shovel (dig once, forget everything), Curious Agent is a spider — every discovery becomes a node in a growing web, and the web itself tells it where to explore next.

```
You inject a topic: "agent memory systems"
    ↓
Curious Agent asks itself:
  "What do I already know about this?
   Where are my blind spots?
   What's the highest-value sub-topic to explore first?"
    ↓
Decomposes into a tree:
  agent memory
  ├── short-term memory → working memory capacity
  ├── long-term memory  → metacognitive monitoring
  └── retrieval         → episodic buffer
    ↓
ExploreAgent (ReAct loop) explores each branch autonomously
    ↓
Every finding is scored, filtered, and written to KG (Neo4j)
    ↓
High-quality findings (≥ 7.0) become behavioral rules:
  "When answering complex questions, I must first
   evaluate my confidence (1-10) and state it clearly."
    ↓
Spreading activation traces root technologies:
  metacognitive monitoring → transformer attention
  "This surface-level concept traces back to
   the fundamental Attention mechanism."
```

### Unified Agent Architecture (v0.3.0)

ExploreAgent and DreamAgent are **two configurations of the same `CAAgent` class** — only the config differs. This is a clean, maintainable architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    CAAgent (unified class)                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  AgentRunner (Nanobot ReAct engine)                 │   │
│  │  • Thought → Action → Observation loop             │   │
│  │  • Hook System (pre/post callbacks)                 │   │
│  │  • ErrorClassifier (Hermes, layered error handling) │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                │
│                           ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ToolRegistry (21 tools, 4 categories)              │   │
│  │  • KG (9)  • Queue (5)  • Search (5)  • LLM (2)    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌──────────────────┐              ┌──────────────────┐
│  ExploreAgent    │              │   DreamAgent     │
│  (ReAct loop)    │              │  (L1→L4 cycle)   │
│  • 14 Tools      │              │  • 15 Tools      │
│  • Continuous    │              │  • Heartbeat 6h  │
│  • Writes KG     │              │  • Writes Queue  │
└──────────────────┘              └──────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              CognitiveHook (v0.3.0 NEW)                      │
│  "Know what it knows, know what it doesn't know"            │
│                                                             │
│  POST /api/knowledge/check  → KG confidence + guidance      │
│  POST /api/knowledge/learn  → Inject unknown to CA queue    │
│  GET  /api/knowledge/analytics → Interaction stats          │
│  POST /api/knowledge/record → Save search results to KG     │
│                                                             │
│  4-level confidence: Expert → Intermediate → Beginner → Novice │
│  Auto-inject unknowns for CA exploration                    │
└─────────────────────────────────────────────────────────────┘
```

Both agents run under daemons:

| Daemon | Agent | Schedule | Role |
|--------|-------|----------|------|
| **ExploreDaemon** | ExploreAgent | Poll every 5 min | Continuous topic exploration |
| **DreamDaemon** | DreamAgent | Heartbeat every 6h | Creative insight generation |
| **SleepPruner** | — | Adaptive 4–24h | KG maintenance (prune dormant nodes) |

All parameters — models, intervals, thresholds, scoring weights, tool lists — come from `config.json`. Zero hard-coded configuration.

---

## Curious Agent Is Right for You If

- ✅ You want an AI that **explores topics on its own**, not just when prompted
- ✅ You care about **knowledge structure** — connections, roots, hierarchies — not just lists of summaries
- ✅ You want your AI to **get smarter over time** by converting discoveries into behavioral rules
- ✅ You need **confidence-aware answers** — your AI knows what it knows and says so
- ✅ You want **quality-filtered knowledge** — only high-signal findings enter the graph
- ✅ You're building a **digital life form** (数字生命体) with intrinsic curiosity, not a tool
- ✅ You want agents running **autonomously 24/7** with full observability and config-driven control
- ✅ You need R1D3 to **auto-inject unknowns** — when it doesn't know, CA will explore and learn

---

## Features

### 🕸️ Knowledge Graph Weaving

Every discovery becomes a node in Neo4j. Nodes connect via parent-child relationships, citations, and dream-generated cross-links. The more you explore, the denser the web — and the web itself guides future exploration.

### 🎯 Curiosity-Driven Decomposition

Four-stage cascade: LLM reasoning → multi-provider verification → KG inference → user clarification. Hallucinated sub-topics are filtered before they enter the queue.

### 🤖 ReAct Loop Exploration

ExploreAgent uses a ReAct loop (Thought → Action → Observation) with 14 tools. Instead of fixed search strategies, the LLM autonomously decides when to search, when to analyze, and when to stop — adapting to each topic's complexity.

### 📊 Metacognitive Quality Scoring

Each exploration is scored on information gain, confidence delta, and graph structural change. Low-value explorations are silently discarded. The Agent knows when to stop drilling and switch topics.

### 🌙 DreamAgent Insight Pipeline

L1→L4 multi-cycle pipeline — **zero search API calls** (pure KG + LLM analysis):

| Level | Name | Input → Output |
|-------|------|---------------|
| L1 | Light Sleep | ExplorationLog + KG anomalies → ≤100 candidates |
| L2 | Deep Sleep | Candidates → Top 20 (6-dimension scored) |
| L3 | Filtering | Scored → Filtered (threshold gate) |
| L4 | REM Sleep | Filtered → Queue topics for ExploreAgent |

**6-dimension scoring:** Relevance (0.25), Quality (0.20), Frequency (0.15), Recency (0.15), Surprise (0.15), CrossDomain (0.10).

### 🌳 Root Technology Tracing

Spreading activation algorithm (Collins & Loftus, 1975) traces any knowledge node back to its root technology. metacognitive monitoring and planning look unrelated on the surface — but both trace back to `transformer attention`.

### 🔄 Behavior Rule Internalization

High-quality discoveries (≥ 7.0) don't just sit in a database. They become behavioral rules — skills, reflection templates, decision frameworks — that permanently change how the host Agent operates.

### ⚙️ Fully Config-Driven

All agents, daemons, models, intervals, thresholds, tool lists, and scoring weights are loaded from `config.json`. Zero hard-coded configuration in source code.

### 🔗 OpenClaw Integration

Bidirectional sync via `shared_knowledge/`. R1D3 (host Agent) queries confidence, injects topics, reads discoveries. Curious Agent writes findings back. The two Agents evolve together.

### 🧠 Cognitive Framework (v0.3.0 NEW)

**"Know what it knows, know what it doesn't know"** — R1D3 can now assess its KG confidence before answering:

| Confidence | Level | Action |
|------------|-------|--------|
| ≥ 0.85 | Expert 🟢 | Answer from KG, cite sources |
| 0.6-0.85 | Intermediate 🟡 | KG + web search supplement |
| 0.3-0.6 | Beginner 🟠 | Search first, inject to CA |
| < 0.3 | Novice 🔴 | LLM fallback + **ALWAYS** inject to CA |

**When R1D3 doesn't know → automatically triggers CA exploration → next time, topic is in KG.**

**API endpoints:**
- `POST /api/knowledge/check` — Query KG confidence + get guidance
- `POST /api/knowledge/learn` — Inject unknown topic to CA queue
- `GET /api/knowledge/analytics` — KG hit/search/fallback stats
- `POST /api/knowledge/record` — Save web search results to KG

---

## Problems Curious Agent Solves

| Without Curious Agent | With Curious Agent |
|----------------------|-------------------|
| ❌ Every search starts from zero. No memory of past explorations. | ✅ Knowledge graph persists and grows. Past explorations inform future ones. |
| ❌ AI gives confident answers about topics it barely understands. | ✅ Confidence-aware: states certainty level, explores more when unsure. |
| ❌ Same topic explored 10 times with declining quality. | ✅ Metacognitive tracking detects diminishing returns and switches topics. |
| ❌ Discoveries live in chat history, never become capabilities. | ✅ High-quality findings → behavioral rules → permanent capability upgrades. |
| ❌ No understanding of how concepts connect at a deep level. | ✅ Spreading activation traces any node to its root technology. |
| ❌ Agent configuration scattered across code, hardcoded values everywhere. | ✅ Single `config.json` source. All agents and daemons dynamically configured. |
| ❌ You have to manually kick off each exploration. | ✅ Daemons run 24/7 on configurable schedules. Heartbeat-driven autonomy. |
| ❌ When R1D3 doesn't know something, it just guesses. | ✅ Auto-inject unknowns to CA. Next time, topic is in KG — no more guessing. |

---

## Why Curious Agent Is Special

| | |
|---|---|
| **Unified CAAgent.** | ExploreAgent and DreamAgent share one class. Only config differs. Clean, maintainable, no duplication. |
| **ReAct loop, not fixed scripts.** | LLM autonomously decides when to search, analyze, or stop. Adapts to topic complexity. |
| **21 Tools, 4 categories.** | KG (9), Queue (5), Search (5), LLM (2). Unified ToolRegistry with typed interfaces. |
| **DreamAgent uses zero search API.** | Pure KG + LLM analysis. L1→L4 pipeline generates insights without consuming Serper/Bocha quota. |
| **Hermes error classification.** | Layered error handling from NousResearch's Hermes Agent — transient vs permanent vs retryable. |
| **Quality-gated knowledge.** | Only findings passing the quality gate enter the graph and shared knowledge layer. |
| **Root technology tracing.** | Cross-subgraph activation convergence automatically surfaces fundamental mechanisms. |
| **Config-driven architecture.** | Every parameter in `config.json`. Change intervals, models, thresholds without touching code. |
| **Cognitive Framework (v0.3.0).** | 4-level confidence assessment. Auto-inject unknowns. R1D3 learns what it doesn't know. |

---

## What Curious Agent Is Not

| | |
|---|---|
| **Not a search engine.** | It builds a knowledge graph, not a list of links. |
| **Not a chatbot.** | Agents have jobs to do, not chat windows. |
| **Not an agent framework.** | It runs inside OpenClaw as a plugin, not as a standalone framework. |
| **Not a prompt manager.** | Agents bring their own prompts. Curious Agent manages knowledge, not text. |
| **Not a single-agent tool.** | Designed for multi-agent collaboration: ExploreAgent + DreamAgent + SleepPruner. |

---

## Quickstart

### Prerequisites

- Python 3.11+
- Neo4j (running locally, or JSON fallback)
- API keys: Bocha, Serper, Volcengine, SiliconFlow (in `.env`)

### Install & Run

```bash
cd /root/dev/curious-agent

# Install dependencies
pip install -r requirements.txt

# Configure (edit config.json as needed)
cp config.example.json config.json

# One-command start
bash start.sh
```

**Services started:**

| Service | Port | Role |
|---------|------|------|
| curious_api | 4848 | REST API + Web UI |
| curious_agent | — | Two-agent daemon (ExploreAgent + DreamAgent) + SleepPruner |

**Access:**
- 🌐 Web UI: http://10.1.0.13:4849/
- 📡 API: http://localhost:4848/

### Inject a Topic

```bash
python3 curious_agent.py --inject "agent memory systems" \
  --score 8.5 --depth 8.0 --reason "research interest"
```

### Run Daemon Mode

```bash
# Two-agent daemon (recommended)
python3 curious_agent.py --daemon

# Config-driven: intervals, models, thresholds all from config.json
# Ctrl+C stops all agents gracefully
```

### API Quick Reference

```bash
# State
curl http://localhost:4848/api/curious/state

# Inject topic
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"metacognition","score":8.5,"depth":8.0}'

# Confidence check (R1D3 integration)
curl "http://localhost:4848/api/knowledge/confidence?topic=agent+memory"

# Root technology tracing
curl "http://localhost:4848/api/kg/trace/metacognitive%20monitoring"

# Root pool
curl http://localhost:4848/api/kg/roots

# === v0.3.0 Cognitive Framework ===

# Check KG confidence + get guidance
curl -X POST http://localhost:4848/api/knowledge/check \
  -H "Content-Type: application/json" \
  -d '{"topic":"FlashAttention"}'

# Inject unknown topic for CA exploration
curl -X POST http://localhost:4848/api/knowledge/learn \
  -H "Content-Type: application/json" \
  -d '{"topic":"FlashAttention","strategy":"llm_answer"}'

# Get cognitive stats
curl http://localhost:4848/api/knowledge/analytics
```

---

## Project Structure

```
curious-agent/
├── curious_agent.py              # CLI entry + daemon orchestration
├── curious_api.py                # Flask REST API + Web UI (+ /api/knowledge/* endpoints)
├── config.json                   # Central configuration (all agents, daemons, models)
├── start.sh                      # One-command startup
├── core/
│   ├── hooks/                   # v0.3.0: Cognitive hook system
│   │   └── cognitive_hook.py    # CognitiveHook — confidence + guidance
│   ├── agents/                  # v0.2.9: Unified Agent framework
│   │   ├── ca_agent.py          # CAAgent — unified Agent class
│   │   ├── explore_agent.py     # ExploreAgent (ReAct loop, 14 Tools)
│   │   ├── dream_agent.py       # DreamAgent (L1→L4 pipeline, 15 Tools)
│   │   └── evolution.py         # Self-Evolution engine
│   ├── tools/                   # v0.2.9: Tool system (21 Tools)
│   │   ├── registry.py           # ToolRegistry (unified registration)
│   │   ├── base.py               # Tool base class
│   │   ├── kg_tools.py           # KG Tools (9): query_kg, add_to_kg, ...
│   │   ├── queue_tools.py        # Queue Tools (5): add_to_queue, claim, ...
│   │   ├── search_tools.py       # Search Tools (5): search_web, fetch_page, ...
│   │   └── llm_tools.py          # LLM Tools (2): llm_analyze, llm_summarize
│   ├── frameworks/               # v0.2.9: Execution frameworks
│   │   ├── agent_runner.py       # Nanobot ReAct execution engine
│   │   ├── agent_hook.py         # Hook callback system
│   │   ├── error_classifier.py   # Hermes error classifier (NousResearch)
│   │   ├── heartbeat.py          # Nanobot Heartbeat service (HKUDS)
│   │   └── retry_utils.py        # Retry strategy utilities
│   ├── daemon/                   # v0.2.9: Daemon processes
│   │   ├── explore_daemon.py     # ExploreAgent continuous guardian
│   │   └── dream_daemon.py       # DreamAgent heartbeat guardian
│   ├── kg/                       # v0.2.9: Knowledge storage layer
│   │   ├── kg_repository.py      # KG Repository abstraction
│   │   ├── neo4j_client.py       # Neo4j operations wrapper
│   │   ├── json_kg_repository.py # JSON fallback repository
│   │   └── repository_factory.py # Repository factory
│   ├── configs/                  # v0.2.9: Python config dataclasses
│   │   ├── agent_explore.py      # ExploreAgent config
│   │   ├── agent_dream.py        # DreamAgent config
│   │   └── llm_providers.py      # Multi-LLM provider config
│   ├── config.py                 # Central config loader (config.json → dataclasses)
│   ├── knowledge_graph.py        # Knowledge graph (parent-child, root tracing)
│   ├── curiosity_decomposer.py   # 4-stage topic decomposition
│   ├── quality_v2.py             # Information gain quality scoring
│   ├── competence_tracker.py     # Competence gap tracking
│   ├── curiosity_engine.py       # ICM fusion scoring
│   ├── explorer.py               # Layered explorer (L1 Web + L2 ArXiv)
│   ├── insight_synthesizer.py    # Cross-topic insight synthesis
│   ├── discovery_writer.py       # Quality-gated discovery persistence
│   ├── event_bus.py              # Event bus (pub/sub)
│   ├── embedding_service.py      # Embedding service (SiliconFlow)
│   ├── providers/                # Search providers
│   │   ├── bocha_provider.py
│   │   └── serper_provider.py
│   ├── spider/                   # Spider engine internals (legacy)
│   │   ├── state.py
│   │   └── checkpoint.py
│   └── repository/               # Storage layer (legacy)
│       ├── base.py
│       └── json_repository.py
├── migrations/
│   └── migrate_json_to_neo4j.py  # JSON → Neo4j migration script
├── shared_knowledge/             # Shared knowledge layer (R1D3 ↔ Curious Agent)
├── tests/                        # 97 test modules
│   ├── hooks/                    # CognitiveHook tests (v0.3.0)
│   ├── agents/                   # CAAgent, ExploreAgent, DreamAgent, hooks
│   ├── frameworks/               # agent_runner, agent_hook, heartbeat, retry
│   ├── tools/                    # base, kg_tools, queue_tools, search_tools, llm_tools
│   ├── daemon/                   # explore_daemon, dream_daemon
│   ├── kg/                       # kg_repository, neo4j_client, repository_factory
│   ├── configs/                  # config, llm_providers, hooks_config
│   └── e2e/                      # Real exploration E2E tests
├── docs/                         # Design documents
│   └── integration-guide.md      # v0.3.0 R1D3 integration guide
└── ui/                           # Web UI (D3.js knowledge graph visualization)
```

---

## Configuration

All agent and daemon parameters are controlled via `config.json`. No hard-coded values in source code.

```json
{
  "hooks": {
    "cognitive": {
      "confidence_threshold": 0.6,
      "auto_inject_unknowns": true,
      "search_before_llm": true
    }
  },
  "agents": {
    "explore": {
      "model": "volcengine",
      "max_iterations": 10,
      "tools": [
        "search_web", "query_kg", "add_to_kg", "claim_queue",
        "mark_done", "get_queue", "llm_analyze", "llm_summarize",
        "fetch_page", "process_paper", "update_kg_status",
        "update_kg_metadata", "get_node_relations", "add_to_queue"
      ]
    },
    "dream": {
      "scoring_weights": {
        "relevance": 0.25, "frequency": 0.15, "recency": 0.15,
        "quality": 0.20, "surprise": 0.15, "cross_domain": 0.10
      },
      "min_score_threshold": 0.8,
      "min_recall_count": 3,
      "max_candidates": 100,
      "max_scored": 20
    }
  },
  "daemon": {
    "explore": {
      "poll_interval_seconds": 300,
      "max_retries": 3,
      "retry_delay_seconds": 15
    },
    "dream": {
      "interval_seconds": 21600
    }
  },
  "knowledge": {
    "root_seeds": [
      "transformer attention", "gradient descent",
      "backpropagation", "softmax", "RL reward signal",
      "uncertainty quantification"
    ],
    "search": {
      "primary": "bocha",
      "fallback": "serper",
      "daily_quota": { "enabled": true, "serper": 100, "bocha": 50 }
    },
    "kg": {
      "enabled": true,
      "uri": "bolt://localhost:7687",
      "fallback_to_json": false
    }
  },
  "behavior": {
    "curiosity": {
      "max_explore_count": 3,
      "min_marginal_return": 0.3,
      "high_quality_threshold": 7.0
    },
    "notification": { "enabled": true, "min_quality": 7.0 }
  },
  "llm": {
    "default_provider": "volcengine",
    "selection_strategy": "capability",
    "providers": {
      "volcengine": {
        "api_url": "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions",
        "models": [{ "model": "ark-code-latest", "weight": 3 }]
      }
    }
  }
}
```

---

## Release History

| Version | Theme | Date |
|---------|-------|------|
| **v0.3.1** | Observability Layer — Hook audit, trace visualization, WebUI multi-file, external agent tracking | 2026-04-17 |
| **v0.3.0** | Cognitive Framework — Know what it knows, know what it doesn't know. 4-level confidence, auto-inject unknowns, `/api/knowledge/*` endpoints | 2026-04-15 |
| **v0.2.9** | Agent architecture refactor — CAAgent unified class, ReAct loop, 21 Tools, Neo4j storage, Hermes error handling | 2026-04-13 |
| **v0.2.8** | Deadlock fixes — SpiderAgent queue stuck, KG quality issues | 2026-04-xx |
| **v0.2.7** | Queue atomicity + QualityV2 fix + Parent link | 2026-03-31 |
| **v0.2.6** | Three-agent concurrent architecture (Spider/Dream/Pruner) | 2026-03-29 |
| **v0.2.5** | KG root technology tracing (Spreading activation) | 2026-03-28 |
| **v0.2.4** | R1D3 integration + InsightSynthesizer + Spider Engine | 2026-03-26 |
| **v0.2.3** | Full capability landing (decomposition, quality, behavior) | 2026-03-23 |
| **v0.2.2** | Meta-cognitive monitor (MGV loop) | 2026-03-21 |
| **v0.2.1** | ICM fusion scoring | 2026-03-15 |

---

## Roadmap

| Status | Feature |
|--------|---------|
| ✅ | Unified CAAgent framework (ExploreAgent + DreamAgent) |
| ✅ | ReAct loop exploration (LLM-autonomous search strategy) |
| ✅ | 21 Tools across 4 categories (KG, Queue, Search, LLM) |
| ✅ | DreamAgent L1→L4 insight pipeline (zero search API) |
| ✅ | Neo4j knowledge graph storage |
| ✅ | Hermes error classification + retry utilities |
| ✅ | Fully config-driven (zero hard-coded values) |
| ✅ | OpenClaw bidirectional sync |
| ✅ | **CognitiveHook — 4-level confidence framework** |
| ✅ | **/api/knowledge/* endpoints for R1D3 integration** |
| ✅ | **Auto-inject unknown topics to CA queue** |
| ✅ | **Hook audit middleware + trace writers (v0.3.1)** |
| ✅ | **WebUI 4-tab dashboard (v0.3.1)** |
| ✅ | **External agent tracking + timeline (v0.3.1)** |
| ⚪ | OpenClaw external hook integration (before_turn/after_turn) |
| ⚪ | Neo4j as primary store (JSON fallback retirement) |
| ⚪ | Self-Evolution engine (Bayesian weight updates) |
| ⚪ | Adaptive interval scheduling (based on queue depth) |
| ⚪ | Dexterous Agent integration (experience-driven execution) |
| ⚪ | R1D3 Skill interface integration |
| ⚪ | Web UI dashboard for real-time monitoring |

---

## FAQ

**How is Curious Agent different from a regular AI search?**
Regular search gives you links. Curious Agent builds a structured knowledge graph, traces connections between concepts, and converts high-value findings into permanent behavioral capabilities.

**Does it run continuously?**
Yes. ExploreAgent polls the queue every 5 minutes. DreamAgent generates insights every 6 hours. Both are configurable via `config.json`.

**What happens to low-quality explorations?**
They're silently discarded. Only findings that pass the quality gate (≥ 7.0) enter the knowledge graph and shared knowledge layer.

**Can I use it with my own AI agent?**
Yes. It's designed as an OpenClaw plugin. The `shared_knowledge/` directory provides bidirectional sync between Curious Agent and the host Agent.

**How does it know what to explore next?**
Four signals: (1) curiosity queue (manually injected or dream-generated), (2) competence gaps (topics you've never explored), (3) metacognitive quality scoring (diminishing returns detection), (4) root technology tracing (surface-to-fundamental connections).
**What changed in v0.3.1?**

Observability Layer — Full visibility into CA's internal work and external interactions:
- Hook audit middleware: All OpenClaw hook calls logged to SQLite
- Trace writers: Explorer/Dream Agent execution steps captured
- External Agent tracking: Agent registry, activity timeline, global event stream
- WebUI 4-tab dashboard: List view, Graph view, Internal view, External view
- 30+ new API endpoints: `/api/audit/*`, `/api/explorer/*`, `/api/dream/*`, `/api/timeline`, `/api/agents`
- Bug fixes: Endpoint mismatch (`/api/knowledge/confidence`), Flask `g.start_time`, `holder_id` parameters

**What changed in v0.3.0?**

Cognitive Framework — R1D3 can now "know what it knows and know what it doesn't know":
- 4-level confidence assessment (Expert → Intermediate → Beginner → Novice)
- Auto-inject unknown topics to CA queue for exploration
- `/api/knowledge/*` endpoints for KG confidence check, learning, analytics
- When R1D3 doesn't know something, CA will explore it — next time it's in KG
- Legacy Spider code removed (spider_engine.py deleted)

**What changed in v0.2.9?**

The biggest refactor yet. SpiderAgent and DreamAgent became proper Agents (CAAgent) with ReAct loops and Tool interfaces. 21 tools across 4 categories. Hermes error handling from NousResearch. Neo4j storage layer. DreamAgent generates insights without any search API calls. All configuration moved to `config.json` — zero hard-coded values.

---

## License

MIT © 2026

---

_设计理念：**好奇驱动，主动探索，元认知调控，自我进化**_
