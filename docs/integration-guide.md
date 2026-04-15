# v0.3.0 Integration Guide — R1D3 × Curious Agent Cognitive Framework

## Overview

The Cognitive Framework enables R1D3 to "know what it knows and know what it doesn't know":

- KG confidence ≥ 0.6 → Answer from knowledge graph
- KG confidence < 0.6 → Search → Record → Inject to CA
- No KG knowledge → LLM fallback → Inject to CA for learning

## API Endpoints

### 1. Check KG Confidence

POST /api/knowledge/check

Request:
```json
{"topic": "FlashAttention"}
```

Response:
```json
{
  "success": true,
  "result": {
    "topic": "FlashAttention",
    "confidence": 0.45,
    "level": "beginner",
    "gaps": ["implementation details"],
    "guidance": "🟠 KG has limited knowledge...",
    "should_search": true,
    "should_inject": true
  }
}
```

### 2. Inject Topic for Learning

POST /api/knowledge/learn

Request:
```json
{"topic": "FlashAttention", "strategy": "llm_answer", "priority": false}
```

### 3. Record Search Results

POST /api/knowledge/record

Request:
```json
{"topic": "FlashAttention", "content": "...", "sources": ["https://..."]}
```

### 4. Get Analytics

GET /api/knowledge/analytics

Response:
```json
{"kg_hits": 0, "search_hits": 0, "llm_fallbacks": 0, "topics_learned": 5}
```

## Configuration

In config.json:
```json
{
  "hooks": {
    "cognitive": {
      "confidence_threshold": 0.6,
      "auto_inject_unknowns": true,
      "search_before_llm": true
    }
  }
}
```

## Confidence Levels

| Level | Confidence | Color | Action |
|-------|------------|-------|--------|
| Expert | ≥ 0.85 | 🟢 | Answer from KG, cite sources |
| Intermediate | 0.6-0.85 | 🟡 | Supplement with web search |
| Beginner | 0.3-0.6 | 🟠 | Search first, then inject to CA |
| Novice | < 0.3 | 🔴 | ALWAYS inject to CA for exploration |
