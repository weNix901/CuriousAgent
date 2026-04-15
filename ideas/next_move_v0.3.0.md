# v0.3.0 Planning Spec — R1D3 × CA Cognitive Hook Integration

> **Core Vision**: Let R1D3 *know what it knows* and *know what it doesn't know*. When it knows it doesn't know → trigger CA exploration → transform "unknown" into "known". Next time, answer directly from KG.

---

## Part 1: Current State Audit — Problems & Deficiencies

### 1.1 Interaction Architecture Today

```
R1D3 (OpenClaw Agent)
  │
  ├── curious-agent Skill (installed in openclaw.json)
  │     ├── check_confidence.sh   → GET /api/metacognitive/check
  │     ├── trigger_explore.sh    → POST /api/curious/inject
  │     ├── sync_discoveries.py   → read state.json → write memory/curious/*.md
  │     └── share_new_discoveries.py → read curious-discoveries.md
  │
  └── HEARTBEAT.md → calls sync + share scripts on every heartbeat
       │
       └── R1D3 reads memory/curious-discoveries.md → memory_search()
```

**CA API endpoints for R1D3**:
| Endpoint | Purpose | Used? |
|----------|---------|-------|
| `GET /api/r1d3/confidence?topic=...` | Query KG confidence for a topic | ❌ No |
| `POST /api/r1d3/inject` | Trigger directed exploration | ✅ Via trigger_explore.sh |
| `POST /api/r1d3/synthesize` | L3 insight synthesis | ❌ No |
| `GET /api/r1d3/discoveries/unshared` | Get unshared discoveries | ❌ No (uses file sync instead) |
| `GET /api/kg/trace/<topic>` | Root-cause trace in KG | ❌ No |
| `GET /api/kg/overview` | KG global overview | ❌ No |

### 1.2 Problem 1: No Cognitive Answer Framework — R1D3 Answers Blindly

**Current behavior**:
```
User asks: "What is FlashAttention?"
  → R1D3 memory_search("FlashAttention")
    → If found in memory/curious/ → use it
    → If not found → fall back to LLM internal knowledge (no explicit trigger to CA)
```

**Problems**:
- R1D3 **never checks KG confidence** before answering. It relies on `memory_search` which only finds *already synced* discoveries, not the full KG.
- No distinction between "I know this from exploration" vs "I'm guessing from LLM knowledge".
- When R1D3 answers from LLM knowledge, the topic is **never injected back into CA** for exploration. So next time, it's still LLM knowledge again — infinite loop of "guessing".
- Violates our cognitive framework: **KG first → search second → LLM last → always learn**.

### 1.3 Problem 2: Discovery Sync is Passive and Delayed

**Current behavior**:
- `sync_discoveries.py` reads `state.json` and writes files to `memory/curious/`
- Only runs during heartbeat (every ~30 min) or manually
- R1D3 can only find discoveries that have been synced to files

**Problems**:
- **Latency**: CA finishes exploring at 10:00, R1D3 doesn't know until next heartbeat at 10:30
- **Lossy**: File sync drops structured data (confidence, gaps, sources, iteration count)
- **One-way**: R1D3 can't query "what do you know about X?" — only reads whatever was dumped to disk
- No real-time feedback: R1D3 answers a question at 10:05, CA finishes exploring it at 10:10, but R1D3 has no way to update its answer

### 1.4 Problem 3: Hook System is Dead Code

| File | Status |
|------|--------|
| `core/frameworks/agent_hook.py` | ✅ AgentHook ABC defined (5 methods) |
| `core/agents/hooks/explore_hook.py` | ✅ ExploreHook implemented (logs only) |
| `core/agents/hooks/dream_hook.py` | ✅ DreamHook implemented (logs only) |
| `core/frameworks/agent_runner.py` | ❌ **Zero** hook references |
| `core/agents/ca_agent.py` | ❌ **Zero** hook references |
| `core/agents/explore_agent.py` | ❌ **Zero** hook references |
| `core/agents/dream_agent.py` | ❌ **Zero** hook references |

**Root cause**: The hook interfaces were designed but never wired into the ReAct loop. They're like neurons with synapses but no axons — the structure exists, the signal never flows.

### 1.5 Problem 4: No OpenClaw-Level Hook for R1D3

Currently, R1D3's interaction with CA is entirely through **Skill scripts** (shell scripts + Python file sync). There is **no OpenClaw hook** that:
- Intercepts R1D3's question-answering flow
- Forces the cognitive framework (KG → search → LLM → learn)
- Provides deterministic, guaranteed behavior (not probabilistic LLM spontaneous action)

The `hooks.internal` in `openclaw.json` only has `session-memory`, `boot-md`, `command-logger` — none related to CA.

### 1.6 Problem Summary Matrix

| # | Problem | Severity | Impact |
|---|---------|----------|--------|
| P1 | No cognitive answer framework | **Critical** | R1D3 answers blindly, never learns from its knowledge gaps |
| P2 | Passive/delayed discovery sync | **High** | Latency + data loss + no real-time awareness |
| P3 | Hook system is dead code | **High** | v0.2.9 promised hooks, delivered skeleton |
| P4 | No OpenClaw-level hook | **High** | No deterministic R1D3-CA interaction mechanism |
| P5 | R1D3 doesn't inject "I don't know" topics to CA | **Critical** | Knowledge gaps never close — system doesn't evolve |

---

## Part 2: v0.3.0 Architecture — Cognitive Hook Design

### 2.1 Core Concept: The Cognitive Answer Loop

```
User asks a question
       │
       ▼
┌─────────────────────────────────────┐
│  Step 1: Query KG Confidence        │
│  POST /api/r1d3/confidence          │
│  GET  /api/kg/trace/<topic>         │
│                                     │
│  If confidence ≥ 0.6 → Answer from │
│  KG knowledge (cited with sources) │
│  → DONE                             │
└──────────────┬──────────────────────┘
               │ confidence < 0.6
               ▼
┌─────────────────────────────────────┐
│  Step 2: Web Search                 │
│  Search for the topic online        │
│                                     │
│  If found → Record as knowledge     │
│  point (write to KG via API)        │
│  → Inject to CA for deep explore    │
│  → Answer from search results       │
│  → DONE                             │
└──────────────┬──────────────────────┘
               │ Not found / insufficient
               ▼
┌─────────────────────────────────────┐
│  Step 3: LLM Internal Knowledge     │
│  Answer based on LLM training data  │
│                                     │
│  BUT ALSO:                          │
│  → Inject topic to CA for           │
│    exploration (async)              │
│  → Mark as "I guessed this"         │
│  → Next time → will be in KG!       │
└─────────────────────────────────────┘
```

**The cognitive loop in one sentence**:
> "知道已经知道的 → 直接从 KG 回答；知道自己不知道的 → 搜索 + 注入 CA 探索 → 下次变成已经知道的"

### 2.2 The OpenClaw Hook: `curious-cognitive-hook`

**What it is**: An OpenClaw hook installed at the gateway level, intercepting R1D3's session message flow.

**What it does**:
1. **Intercepts** every user question before R1D3 answers
2. **Forces** the cognitive answer loop (KG → Search → LLM → Learn)
3. **Injects** knowledge gaps into CA automatically
4. **Records** the answer strategy for pattern learning

**Where it lives**:
```
/root/dev/curious-agent/core/hooks/cognitive_hook.py  # CA-side implementation
/root/.openclaw/workspace-researcher/hooks/            # OpenClaw-side wrapper
```

**Registration** (in `openclaw.json`):
```json
{
  "hooks": {
    "external": {
      "curious-cognitive": {
        "enabled": true,
        "type": "session-intercept",
        "config": {
          "api_url": "http://localhost:4848",
          "confidence_threshold": 0.6,
          "auto_inject_unknowns": true,
          "search_before_llm": true
        }
      }
    }
  }
}
```

### 2.3 Hook Lifecycle

```
Session Message Arrives
       │
       ▼
  ┌─────────────┐
  │ before_turn │ ← Hook intercepts
  │             │   1. Extract topic from user question
  │             │   2. Query CA /api/r1d3/confidence
  │             │   3. Query CA /api/kg/trace/<topic>
  │             │   4. Return confidence result to R1D3 context
  └──────┬──────┘
         │
         ▼
  R1D3 answers (with confidence context injected)
         │
         ▼
  ┌─────────────┐
  │ after_turn  │ ← Hook reviews answer
  │             │   1. Detect answer strategy used:
  │             │      - "kg_answer" → DONE (knowledge used)
  │             │      - "search_answer" → inject to CA for deep explore
  │             │      - "llm_answer" → inject to CA + mark as uncertain
  │             │   2. If confidence was low AND topic not injected → inject now
  │             │   3. Update /api/r1d3/discoveries state
  └─────────────┘
```

### 2.4 Hook Implementation — CA Side (`core/hooks/cognitive_hook.py`)

```python
"""
CognitiveHook — v0.3.0
Intercepts R1D3's answer flow to enforce the cognitive framework:
  KG first → Search second → LLM last → Always learn

This hook is called by OpenClaw's external hook mechanism.
It provides deterministic, guaranteed behavior — not probabilistic LLM choices.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from core.frameworks.agent_hook import AgentHook, AgentHookContext
from core.repository.base import KnowledgeRepository
from core.api.r1d3_tools import R1D3ToolHandler


class AnswerStrategy(Enum):
    KG_ANSWER = "kg_answer"           # Confidence ≥ threshold, answer from KG
    SEARCH_ANSWER = "search_answer"   # KG miss, found via web search
    LLM_ANSWER = "llm_answer"         # Both KG and search miss, LLM fallback


@dataclass
class CognitiveResult:
    topic: str
    strategy: AnswerStrategy
    confidence: float
    answer_source: str  # "kg", "search", "llm"
    injected_to_ca: bool
    kg_data: Optional[dict] = None
    search_results: Optional[list] = None
    gaps: list = field(default_factory=list)


class CognitiveHook(AgentHook):
    """
    Hook that enforces the cognitive answer loop.
    
    Called by OpenClaw external hook mechanism on every session turn.
    Provides deterministic behavior: always check KG first, inject unknowns to CA.
    """
    
    def __init__(self, config: dict):
        self.api_url = config.get("api_url", "http://localhost:4848")
        self.confidence_threshold = config.get("confidence_threshold", 0.6)
        self.auto_inject = config.get("auto_inject_unknowns", True)
        self.search_before_llm = config.get("search_before_llm", True)
        self.handler = R1D3ToolHandler()
    
    # === AgentHook interface ===
    
    def before_iteration(self, context: AgentHookContext) -> None:
        """Called before R1D3 answers a question."""
        # Extract topic from context.metadata (injected by OpenClaw)
        topic = context.metadata.get("topic")
        if not topic:
            return
        
        # Query KG confidence
        result = self.handler.curious_check_confidence(topic)
        confidence = result.get("confidence", 0.0)
        level = result.get("level", "novice")
        gaps = result.get("gaps", [])
        
        # Query KG trace for detailed knowledge
        kg_data = None
        if confidence >= self.confidence_threshold:
            kg_data = self._query_kg_trace(topic)
        
        # Inject guidance into context for R1D3 to consume
        context.metadata["cognitive_guidance"] = {
            "topic": topic,
            "confidence": confidence,
            "level": level,
            "strategy": self._recommend_strategy(confidence),
            "kg_data": kg_data,
            "gaps": gaps,
            "should_search": confidence < self.confidence_threshold and self.search_before_llm,
            "should_inject": confidence < self.confidence_threshold and self.auto_inject,
        }
    
    def after_iteration(self, context: AgentHookContext) -> None:
        """Called after R1D3 answers — review and inject if needed."""
        guidance = context.metadata.get("cognitive_guidance", {})
        topic = guidance.get("topic")
        if not topic:
            return
        
        strategy_used = context.metadata.get("answer_strategy")
        confidence = guidance.get("confidence", 0.0)
        
        # Post-answer actions
        if strategy_used == AnswerStrategy.SEARCH_ANSWER.value:
            # R1D3 found it via search → record to KG + inject for deep explore
            self._record_search_to_kg(topic, context)
            self._inject_to_ca(topic, context, depth="medium")
        
        elif strategy_used == AnswerStrategy.LLM_ANSWER.value:
            # R1D3 guessed from LLM → inject to CA + mark uncertain
            self._inject_to_ca(topic, context, depth="deep", priority=True)
            context.metadata["answer_uncertain"] = True
        
        elif strategy_used == AnswerStrategy.KG_ANSWER.value:
            # Perfect — KG knowledge was used. No action needed.
            pass
        
        # Safety net: if confidence was low and topic was NOT injected, inject now
        if confidence < self.confidence_threshold and self.auto_inject:
            if not context.metadata.get("already_injected"):
                self._inject_to_ca(topic, context, depth="medium")
    
    def on_tool_call(self, context: AgentHookContext) -> None:
        """Track tool usage for cognitive pattern learning."""
        pass
    
    def on_error(self, context: AgentHookContext) -> None:
        """Log cognitive hook errors."""
        pass
    
    def on_complete(self, context: AgentHookContext) -> None:
        """Session complete — log cognitive statistics."""
        pass
    
    # === Internal methods ===
    
    def _recommend_strategy(self, confidence: float) -> str:
        if confidence >= self.confidence_threshold:
            return "use_kg"
        elif self.search_before_llm:
            return "search_then_llm"
        else:
            return "llm_fallback"
    
    def _query_kg_trace(self, topic: str) -> Optional[dict]:
        """Query KG for detailed trace of a topic."""
        try:
            return self.repo.get_topic_with_children(topic)
        except:
            return None
    
    def _record_search_to_kg(self, topic: str, context: AgentHookContext) -> None:
        """Record search results as a knowledge point in KG."""
        search_results = context.metadata.get("search_results", [])
        if not search_results:
            return
        # POST /api/queue/add or direct KG write
        self.handler.repo.add_topic(
            topic=topic,
            findings="\n".join([r.get("snippet", "") for r in search_results[:3]]),
            sources=[r.get("url", "") for r in search_results[:3]],
        )
    
    def _inject_to_ca(self, topic: str, context: AgentHookContext, 
                      depth: str = "medium", priority: bool = False) -> None:
        """Inject topic to CA for exploration."""
        context_str = context.metadata.get("answer_text", "")[:500]
        self.handler.curious_agent_inject(topic, context_str, depth, source="r1d3_hook")
        context.metadata["already_injected"] = True
```

### 2.5 Hook Implementation — OpenClaw Side

The OpenClaw-side hook wrapper sits between the session and R1D3's turn processing:

```
User message → CognitiveHook.before_turn() → R1D3 receives enriched context
R1D3 answers → CognitiveHook.after_turn() → Auto-inject if needed
```

**OpenClaw wrapper** (to be implemented as OpenClaw external hook or session middleware):
```python
"""
curious_cognitive_hook.py — OpenClaw-side wrapper
Installed as an external hook in openclaw.json
"""

import os
import requests
from typing import Any

CURIOUS_API_URL = os.environ.get("CURIOUS_API_URL", "http://localhost:4848")


def before_turn(session, message: str) -> dict[str, Any]:
    """
    Called by OpenClaw before R1D3 processes a message.
    Extracts topic, queries KG, injects cognitive guidance.
    """
    # Simple topic extraction (can be enhanced with LLM)
    topic = _extract_topic(message)
    if not topic:
        return {}
    
    # Query CA for confidence
    resp = requests.get(f"{CURIOUS_API_URL}/api/r1d3/confidence", params={"topic": topic})
    if resp.status_code != 200:
        return {}
    
    data = resp.json().get("result", {})
    confidence = data.get("confidence", 0.0)
    level = data.get("level", "novice")
    gaps = data.get("gaps", [])
    
    # Build guidance message for R1D3
    guidance = _build_guidance(topic, confidence, level, gaps)
    
    return {
        "topic": topic,
        "cognitive_guidance": guidance,
        "kg_confidence": confidence,
    }


def after_turn(session, message: str, response: str, context: dict) -> None:
    """
    Called by OpenClaw after R1D3 answers.
    Reviews answer strategy, injects unknowns to CA.
    """
    topic = context.get("topic")
    confidence = context.get("kg_confidence", 0.0)
    
    if not topic or confidence >= 0.6:
        return  # KG answered confidently, no action needed
    
    # Low confidence → detect if R1D3 used search or LLM
    # and inject to CA for exploration
    _inject_if_needed(topic, response, confidence)


def _extract_topic(message: str) -> str | None:
    """Extract the main topic from a user question."""
    # Simple heuristic: strip question words, get key nouns
    # Can be replaced with LLM-based extraction
    import re
    # Remove question words
    cleaned = re.sub(r'\b(what|how|why|when|where|who|is|are|do|does|did|can|could|will|would|should)\b', '', message.lower())
    cleaned = re.sub(r'[?\.,!;:()"\']', '', cleaned).strip()
    words = cleaned.split()
    if len(words) < 2:
        return None
    # Return the most meaningful phrase (2-4 words)
    return ' '.join(words[:4])


def _build_guidance(topic: str, confidence: float, level: str, gaps: list) -> str:
    """Build a guidance message for R1D3 to follow."""
    if confidence >= 0.85:
        return (
            f"[COGNITIVE FRAMEWORK] Topic: '{topic}' | "
            f"KG confidence: {confidence:.0%} ({level}) | "
            f"🟢 Answer from KG knowledge. Cite sources. "
            f"No need to search or guess."
        )
    elif confidence >= 0.6:
        return (
            f"[COGNITIVE FRAMEWORK] Topic: '{topic}' | "
            f"KG confidence: {confidence:.0%} ({level}) | "
            f"🟡 Partial KG knowledge. Supplement with web search. "
            f"Record findings as knowledge points. Inject to CA for deep exploration."
        )
    elif confidence >= 0.3:
        return (
            f"[COGNITIVE FRAMEWORK] Topic: '{topic}' | "
            f"KG confidence: {confidence:.0%} ({level}) | "
            f"🟠 KG has limited knowledge. Search the web first. "
            f"If found → record to KG + inject to CA. "
            f"If not found → answer from LLM knowledge + inject to CA (mark as uncertain)."
        )
    else:
        return (
            f"[COGNITIVE FRAMEWORK] Topic: '{topic}' | "
            f"KG confidence: {confidence:.0%} ({level}) | "
            f"🔴 No KG knowledge. Search the web. "
            f"Then answer from LLM if search fails. "
            f"ALWAYS inject this topic to CA for exploration. "
            f"Next time it will be in KG!"
        )


def _inject_if_needed(topic: str, response: str, confidence: float) -> None:
    """Inject topic to CA if R1D3 answered without sufficient KG knowledge."""
    payload = {
        "topic": topic,
        "context": f"R1D3 answered without KG knowledge (confidence={confidence:.0%}). Answer: {response[:200]}",
        "depth": "deep" if confidence < 0.3 else "medium",
        "source": "r1d3_hook",
        "priority": confidence < 0.3,
    }
    try:
        requests.post(f"{CURIOUS_API_URL}/api/r1d3/inject", json=payload)
    except Exception as e:
        pass  # Log error in production
```

### 2.6 R1D3 Behavioral Change — The New Answer Protocol

When the hook is active, R1D3's answer behavior changes:

**Before (v0.2.x)**:
```
User: What is FlashAttention?
R1D3: [memory_search] → not found → [LLM knowledge] → "FlashAttention is..."
     (never injected to CA, next time still no KG knowledge)
```

**After (v0.3.0)**:
```
User: What is FlashAttention?
Hook before_turn: confidence=0.0 → "🔴 No KG knowledge. Search → LLM → inject to CA"
R1D3: 
  1. [memory_search] → not found in synced discoveries
  2. [web_search] → found 3 results → records as knowledge point
  3. [trigger_explore.sh] → injects "FlashAttention" to CA for deep exploration
  4. "Based on my search results, FlashAttention is... 
     (I've added this to my knowledge base for future reference, 
     and I'm doing a deeper exploration now)"

→ CA explores "FlashAttention" deeply (30 min later)
→ KG now has comprehensive knowledge
→ Next time user asks → confidence ≥ 0.8 → answer directly from KG
```

### 2.7 New API Endpoints (CA-side additions)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/r1d3/cognitive/before` | POST | Hook calls before R1D3 answers |
| `/api/r1d3/cognitive/after` | POST | Hook calls after R1D3 answers |
| `/api/r1d3/cognitive/stats` | GET | Get cognitive loop statistics |
| `/api/kg/record_search` | POST | Record search results as KG knowledge point |

### 2.8 Integration with Existing CA Components

```
                    ┌──────────────────────┐
                    │   OpenClaw Gateway    │
                    │  (session-intercept)  │
                    └──────────┬───────────┘
                               │
              before_turn ─────┼───── after_turn
                               │
                    ┌──────────▼───────────┐
                    │  CognitiveHook        │
                    │  (new, v0.3.0)        │
                    │                       │
                    │  • check_confidence   │
                    │  • kg_trace           │
                    │  • inject_to_ca       │
                    │  • record_search      │
                    └────┬──────┬─────┬────┘
                         │      │     │
                         ▼      ▼     ▼
              ┌──────────┐ ┌──────┐ ┌─────────┐
              │  KG Repo │ │ Queue│ │ Search  │
              │ (Neo4j/  │ │(SQLite│ │Provider │
              │  JSON)   │ │ )    │ │(Serper/ │
              │          │ │      │ │ Bocha)  │
              └──────────┘ └──────┘ └─────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   AgentRunner        │
              │  (ReAct loop)        │
              │  • ExploreAgent      │
              │  • DreamAgent        │
              │  • existing hooks:   │
              │    ExploreHook       │
              │    DreamHook         │
              └──────────────────────┘
```

**Existing hooks (ExploreHook, DreamHook)**: Keep them for AgentRunner internal lifecycle tracking. They fire on each ReAct iteration. CognitiveHook is a **higher-level** hook that fires on each R1D3 session turn — they operate at different layers.

---

## Part 3: Implementation Phases

### Phase 0: Cognitive Hook Core (P0 — Foundation)
- [ ] Create `core/hooks/cognitive_hook.py` (CA-side)
- [ ] Create `core/hooks/__init__.py`
- [ ] Implement `before_turn()` / `after_turn()` logic
- [ ] Add `_extract_topic()` with LLM-based extraction option
- [ ] Add `_build_guidance()` with 4-level confidence messages
- [ ] Test: hook correctly identifies KG hits/misses

### Phase 1: OpenClaw Hook Integration (P0 — Wiring)
- [ ] Create OpenClaw-side wrapper (`hooks/curious_cognitive_hook.py`)
- [ ] Register as external hook in `openclaw.json`
- [ ] Wire `before_turn` → inject cognitive guidance into R1D3 context
- [ ] Wire `after_turn` → detect answer strategy → auto-inject if needed
- [ ] Test: hook fires on every R1D3 session turn

### Phase 2: New CA API Endpoints (P1)
- [ ] `POST /api/r1d3/cognitive/before` — before_turn API
- [ ] `POST /api/r1d3/cognitive/after` — after_turn API
- [ ] `GET /api/r1d3/cognitive/stats` — cognitive loop statistics
- [ ] `POST /api/kg/record_search` — record search results as KG point
- [ ] Test: all endpoints return correct data

### Phase 3: ExploreHook & DreamHook Wiring (P1 — Fix Dead Code)
- [ ] Wire ExploreHook into AgentRunner ReAct loop
- [ ] Wire DreamHook into DreamAgent pipeline
- [ ] Make ExploreHook report exploration status to CognitiveHook
- [ ] Make DreamHook report dream insights to CognitiveHook
- [ ] Test: hooks actually fire during exploration/dreaming

### Phase 4: R1D3 Behavioral Update (P1)
- [ ] Update R1D3's AGENTS.md to document the cognitive framework
- [ ] Update R1D3's SOUL.md to reflect "know what I know/don't know"
- [ ] Update HEARTBEAT.md — sync still runs as backup, but hook is primary
- [ ] Test: R1D3 follows the framework consistently

### Phase 5: Statistics & Monitoring (P2)
- [ ] Track: KG hit rate, search rate, LLM fallback rate
- [ ] Track: topics injected → topics explored → topics learned
- [ ] Track: confidence growth over time (per topic)
- [ ] Dashboard: /api/r1d3/cognitive/stats
- [ ] Test: stats are accurate and actionable

### Phase 6: Pattern Learning (P2 — Future)
- [ ] Record answer patterns (which topics always need search? which are in KG?)
- [ ] Pre-fetch KG knowledge for high-frequency topics
- [ ] Proactive exploration: inject topics R1D3 *might* be asked about
- [ ] Test: pre-fetching reduces answer latency

---

## Part 4: Success Criteria

### v0.3.0 Definition of Done

| Metric | Before (v0.2.x) | After (v0.3.0) |
|--------|----------------|----------------|
| KG check before answering | ❌ Never | ✅ Every question |
| Unknown topics → CA injection | ❌ Manual only | ✅ Automatic |
| Discovery sync latency | ~30 min (heartbeat) | Real-time (hook) |
| Hook system (CA internal) | Dead code | Wired into ReAct loop |
| OpenClaw-level hook | None | CognitiveHook installed |
| Answer traceability | None | Every answer tagged with strategy |
| Knowledge growth | Manual curation | Automatic (answer → inject → learn) |

### The Cognitive Flywheel

```
Answer question
       │
       ▼
  Check KG → if miss → inject to CA
       │                      │
       │                      ▼
       │                 CA explores
       │                      │
       │                      ▼
       │                 KG grows
       │                      │
       └──────────────────────┘
              (next time)

Every unanswered question becomes tomorrow's answered question.
```

---

## Part 5: Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hook slows down R1D3 answering (extra API calls) | Medium | Async after_turn, cache confidence results |
| Topic extraction from questions is inaccurate | Medium | LLM-based extraction + fallback to full question |
| CA is not running when R1D3 needs it | High | Graceful degradation → fall back to file sync |
| Too many topics injected → CA queue explodes | High | Deduplication + priority queue + rate limiting |
| OpenClaw doesn't support external hooks yet | Critical | Implement as Skill wrapper (scripts) as v0.3.0-alpha, full hook when OpenClaw supports it |

### Fallback Plan (if OpenClaw external hooks are not available)

Implement the cognitive framework as a **Skill + AGENTS.md rule**:

```markdown
## 🧠 Cognitive Answer Framework (v0.3.0)

Before answering ANY question:

1. Run `bash scripts/check_confidence.sh "<topic>"`
2. Based on confidence level:
   - ≥ 0.6: Answer from memory_search results
   - 0.3-0.6: Search web → record findings → inject to CA
   - < 0.3: Search web → if fails, answer from LLM → inject to CA
3. After answering, if confidence was < 0.6:
   - Run `bash scripts/trigger_explore.sh "<topic>" "<context>"`
```

This is less deterministic than a real hook but achieves the same cognitive behavior.

---

## Part 6: Connection to R1D3 Vision

This v0.3.0 directly advances the **数字生命体** (Digital Lifeform) vision:

- **自主意识 (Self-awareness)**: R1D3 now knows its own knowledge boundaries — "I know this" vs "I'm guessing"
- **自主行为 (Self-directed action)**: Automatic topic injection to CA when knowledge is lacking
- **持续进化 (Continuous evolution)**: Every question answered = knowledge gap identified = exploration triggered = KG grown
- **内在动机 (Intrinsic motivation)**: The cognitive hook creates an intrinsic drive to fill knowledge gaps — not because a user asked, but because the system *knows* it doesn't know

> "知道自己已经知道的，和知道自己不知道的" — this is the essence of metacognition. v0.3.0 makes it real.

---

**Created**: 2026-04-14  
**Author**: R1D3-researcher  
**Status**: Draft — awaiting weNix review  
**Dependencies**: OpenClaw external hook support (or fallback to Skill-based implementation)
