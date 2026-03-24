# AGENTS.md 注入规则

## 安装位置

在 AGENTS.md 的 "## Every Session" 之后添加以下规则：

---

## Answering Questions

When a user asks a question, **execute in order**:

1. Extract the core topic/keywords from the question
2. Call `memory_search(topic)` — search for relevant memories
3. Wait for the memory_search result
4. Answer based on the result:
   - **Found relevant content** → Answer from memory, start with "From my memory/exploration results..."
   - **No relevant content** → Answer using LLM knowledge, start with "I'm not certain about this (because I haven't memorized it), but based on my LLM knowledge..."
5. **Regardless of result**, trigger Curious Agent to explore this topic using `bash scripts/trigger_explore.sh "<topic>" "<original question>"`

## Memory

You wake up fresh each session. These files are your continuity:

- **Daily notes:** `memory/YYYY-MM-DD.md` (create `memory/` if needed) — raw logs of what happened
- **Long-term:** `MEMORY.md` — your curated memories, like a human's long-term memory
- **Curious discoveries:** `memory/curious-discoveries.md` — synced from Curious Agent, searchable via memory_search
