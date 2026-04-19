---
name: knowledge-query
description: "Query Curious Agent knowledge graph for topic confidence and answer guidance. Use when answering knowledge questions, explaining concepts, or when uncertain about a topic. NOT for commands, code writing, debugging, or task execution. Call skill first, then answer using the guidance returned."
---

# knowledge-query

Query CA (Curious Agent) knowledge graph before answering knowledge questions.

## When to Use

Use this skill when:
- User asks "什么是 X", "解释 Y", "Z 怎么做"
- Technical concept explanation needed
- Uncertain about a topic (confidence low)

**Do NOT use for**: commands (ls, git, etc.), code writing, debugging, file operations, daily chat.

## How to Use

Run the script with the topic:

```bash
python3 /root/.openclaw/skills/knowledge-query/scripts/query.py "topic here"
```

## Output Format

Script returns JSON with:
- `success`: true/false
- `output`: Formatted markdown context (ready to inject into your response)
- `metadata`: { topic, confidence (0-1), level, gaps }

## Confidence Levels

| Level | Confidence | Action |
|-------|-----------|--------|
| 🟢 Expert | >85% | Answer from KG directly |
| 🟡 Intermediate | 60-85% | Supplement with search |
| 🟠 Beginner | 30-60% | Search first, then answer |
| 🔴 Novice | <30% | Search → answer from LLM → inject to CA for exploration |

## Answer Flow

1. Run query.py with topic
2. Read the guidance from output
3. Follow the recommended strategy (search/search+answer/answer directly)
4. Cite sources when KG confidence is high

## Requirements

- CA API running on localhost:4848 (env `CA_API_URL` overrides)
- Script handles errors gracefully (returns warning if API down)
