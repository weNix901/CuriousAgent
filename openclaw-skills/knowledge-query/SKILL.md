---
name: knowledge-query
description: "Query CA knowledge graph before answering knowledge questions. ONLY for concept explanations. MUST extract core topic (2-10 words), NOT entire sentences. MUST NOT use for commands, code, debugging, tasks."
---

# knowledge-query

Query CA (Curious Agent) knowledge graph to check confidence level before answering knowledge questions.

## ⚠️ CRITICAL: Topic Extraction Rules

**YOU MUST extract the CORE topic, NOT the full user sentence.**

| User Message | WRONG Topic ❌ | RIGHT Topic ✅ |
|---|---|---|
| "什么是agent上下文管理系统？" | "什么是agent上下文管理系统？" | "agent上下文管理系统" |
| "解释一下transformer attention机制" | "解释一下transformer attention机制" | "transformer attention" |
| "agent记忆机制是怎么实现的？" | "agent记忆机制是怎么实现的？" | "agent记忆机制" |
| "帮我看看RAG和vector search的区别" | "帮我看看RAG和vector search的区别" | "RAG" 或 "vector search" |

**Topic Format Requirements:**
- Length: 2-10 words (noun phrases, not questions)
- Language: Chinese or English keywords only
- No question words: 不要包含"什么是"、"解释"、"怎么"、"帮我"等
- No command words: 不要包含"检查"、"commit"、"push"、"debug"等

## ✅ WHEN TO USE (Must Invoke)

Invoke this skill ONLY when user asks about:

1. **概念解释**: "什么是 X", "X 是什么", "解释 X", "X 的原理"
2. **技术对比**: "X 和 Y 的区别", "比较 X 和 Y"
3. **机制说明**: "X 是怎么工作的", "X 的实现原理"
4. **名词询问**: 用户提到不熟悉的技术术语

**Example valid triggers:**
- "什么是 FlashAttention？"
- "agent memory 有哪些类型？"
- "RAG 和 semantic search 有什么区别？"

## ❌ MUST NOT USE (Skip This Skill)

**NEVER invoke this skill for:**

| Category | Examples | Reason |
|---|---|---|
| 命令执行 | "ls", "git status", "npm install", "重启服务" | These are operations, not knowledge |
| 代码编写 | "写一个函数", "帮我写代码", "实现 X 功能" | Code generation, not explanation |
| 问题调试 | "为什么报错", "debug 这个问题", "检查一下" | Troubleshooting, not knowledge |
| 任务执行 | "commit", "push", "创建 PR", "部署" | Task execution, not explanation |
| 日常对话 | "好的", "谢谢", "继续" | No knowledge query needed |
| 文件操作 | "读一下这个文件", "修改配置" | File operations, not knowledge |

**If user's intent is ANY of the above → SKIP this skill entirely.**

## How to Use

### Step 1: Extract Core Topic

Before calling the script, extract the core topic from user's message:

```python
# 思考过程示例:
# User: "什么是agent上下文管理系统？"
# 1. 剔除问题词: "什么是" → 剩余 "agent上下文管理系统"
# 2. 检查长度: 7个字 → 合格 (2-10 words)
# 3. 确认是名词短语 → 合格
# → Topic = "agent上下文管理系统"
```

### Step 2: Run Query Script

```bash
python3 /root/.openclaw/skills/knowledge-query/scripts/query.py "<extracted_topic>"
```

**Script path alternatives (if not installed):**
- CA project: `/root/dev/curious-agent/openclaw-skills/knowledge-query/scripts/query.py`

### Step 3: Process Output

Script returns JSON:
```json
{
  "success": true,
  "output": "[KG Context — Expert (85%)]\n话题: agent上下文管理系统\n置信度: 0.85\nKG 有完整知识，可直接回答。",
  "metadata": {"topic": "...", "confidence": 0.85, "level": "expert", "gaps": []}
}
```

**Read the `output` field and follow guidance:**

| Level | Confidence | Your Action |
|-------|-----------|-------------|
| 🟢 Expert | ≥85% | Answer from KG knowledge directly, cite sources |
| 🟡 Intermediate | 60-85% | Use KG knowledge + supplement with web search |
| 🟠 Beginner | 30-60% | Search first, then answer with combined knowledge |
| 🔴 Novice | <30% | Answer from LLM, optionally inject topic to CA for exploration |

## Execution Checklist

Before invoking, verify ALL conditions:

```
[ ] User asks about a concept/explanation/mechanism (NOT command/code/debug)
[ ] Extracted topic is 2-10 words (noun phrase, no question words)
[ ] Topic is NOT a command keyword (git, commit, ls, debug, etc.)
```

If ANY condition fails → **SKIP this skill** and proceed directly.

## Requirements

- CA API running on `localhost:4848` (env `CA_API_URL` overrides)
- Script handles errors gracefully (returns warning if API down)
- Timeout: 2 seconds (non-blocking)

## Error Handling

If `success: false`:
- Log: `[KG Context — 不可用] CA API 无响应，跳过知识查询。`
- Proceed with normal answer (do NOT retry, do NOT block)