# OpenClaw Hooks v0.3.0_plus Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create 5 OpenClaw Hooks for CA-R1D3 knowledge integration

**Architecture:** 3 Internal Hooks (HOOK.md + handler.ts) + 2 Plugin SDK Hooks (npm package + TypeScript compile)

**Tech Stack:** TypeScript, Node.js, fetch API, AbortController, YAML frontmatter

---

## Task 1: Create Directory Structure

**Files:**
- Create: `openclaw-hooks/internal/knowledge-query/`
- Create: `openclaw-hooks/internal/knowledge-learn/`
- Create: `openclaw-hooks/internal/knowledge-bootstrap/`
- Create: `openclaw-hooks/plugins/knowledge-inject/`
- Create: `openclaw-hooks/plugins/knowledge-gate/`

**Step 1: Create base directory structure**

```bash
mkdir -p openclaw-hooks/internal/knowledge-query
mkdir -p openclaw-hooks/internal/knowledge-learn
mkdir -p openclaw-hooks/internal/knowledge-bootstrap
mkdir -p openclaw-hooks/plugins/knowledge-inject/src/hooks
mkdir -p openclaw-hooks/plugins/knowledge-gate/src/hooks
```

**Step 2: Verify structure**

Run: `tree openclaw-hooks/ 2>/dev/null || ls -R openclaw-hooks/`

Expected:
```
openclaw-hooks/
├── internal/
│   ├── knowledge-bootstrap/
│   ├── knowledge-learn/
│   └── knowledge-query/
└── plugins/
    ├── knowledge-gate/
    │   └── src/
    │       └── hooks/
    └── knowledge-inject/
    │   └── src/
    │       └── hooks/
```

---

## Task 2: Internal Hook #1 - knowledge-query

**Files:**
- Create: `openclaw-hooks/internal/knowledge-query/HOOK.md`
- Create: `openclaw-hooks/internal/knowledge-query/handler.ts`

**Step 1: Create HOOK.md**

```markdown
---
name: knowledge-query
description: "Intercept user messages → query CA KG confidence → inject knowledge context"
metadata:
  {
    "openclaw": {
      "emoji": "🧠",
      "events": ["message:received"],
      "requires": { "bins": ["node"] }
    }
  }
---

# Knowledge Query Hook

在 Agent 回答前查询 CA 知识图谱置信度，将相关知识注入上下文。
依赖 v0.3.0 的 `/api/r1d3/confidence` 端点。

## What It Does

When a user sends a message:
1. Extracts the topic from the message
2. Queries CA API for KG confidence
3. Injects knowledge context into agent conversation

## Requirements

- Node.js (for fetch API)
- CA service running on localhost:4848

## Configuration

Uses `CA_API_URL` environment variable (default: http://localhost:4848).

## Disabling

openclaw hooks disable knowledge-query
```

**Step 2: Create handler.ts**

```typescript
const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const handler = async (event: any) => {
  // 1. 严格过滤
  if (event.type !== 'message') return;
  if (!event.context?.content || event.context.content.trim().length < 3) return;
  
  const userMessage = event.context.content.trim();
  const topic = userMessage.slice(0, 80);
  
  // 2. Fire-and-forget + 超时保护
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    const response = await fetch(
      `${CA_API}/api/r1d3/confidence?topic=${encodeURIComponent(topic)}`,
      { signal: controller.signal }
    );
    clearTimeout(timeout);
    
    if (response.ok) {
      const data = await response.json();
      const confidence = data.result?.confidence || 0;
      
      if (confidence >= 0.85) {
        event.messages.push(
          `[KG Context — 置信度高 ${(confidence * 100).toFixed(0)}%]\n` +
          `KG 有完整知识，可直接回答。`
        );
      } else if (confidence >= 0.6) {
        event.messages.push(
          `[KG Context — 置信度中 ${(confidence * 100).toFixed(0)}%]\n` +
          `KG 有部分知识，建议搜索补充。`
        );
      } else if (confidence >= 0.3) {
        event.messages.push(
          `[KG Context — 置信度低 ${(confidence * 100).toFixed(0)}%]\n` +
          `KG 知识有限，建议搜索后再回答。`
        );
      } else {
        event.messages.push(
          `[KG Context — 无知识]\n` +
          `话题: ${topic}\n` +
          `KG 无此话题知识，需要探索。`
        );
      }
    }
  } catch (err: any) {
    // 3. 静默失败
    console.error(`[knowledge-query] Failed: ${err.message}`);
  }
};

export default handler;
```

**Step 3: Verify API endpoint works**

Run: `curl -s "http://localhost:4848/api/r1d3/confidence?topic=test"`

Expected: `{"result":{"confidence":0.0,...},"status":"ok"}`

---

## Task 3: Internal Hook #2 - knowledge-learn

**Files:**
- Create: `openclaw-hooks/internal/knowledge-learn/HOOK.md`
- Create: `openclaw-hooks/internal/knowledge-learn/handler.ts`

**Step 1: Create HOOK.md**

```markdown
---
name: knowledge-learn
description: "After agent replies → detect low confidence → inject to CA exploration queue"
metadata:
  {
    "openclaw": {
      "emoji": "🔍",
      "events": ["message:sent"],
      "requires": { "bins": ["node"] }
    }
  }
---

# Knowledge Learn Hook

检测低置信度回答并自动注入 CA 探索队列。
依赖 v0.3.0 的 `/api/knowledge/learn` 端点。

## What It Does

After agent sends a reply:
1. Detects low confidence markers in response
2. Extracts uncertain topic
3. Injects topic to CA queue for exploration

## Requirements

- Node.js (for fetch API)
- CA service running on localhost:4848

## Configuration

Uses `CA_API_URL` environment variable (default: http://localhost:4848).

## Disabling

openclaw hooks disable knowledge-learn
```

**Step 2: Create handler.ts**

```typescript
const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const LOW_CONFIDENCE_PATTERNS = [
  "基于 LLM 知识", "我猜测", "不太确定",
  "了解一些但不完全", "Based on my LLM knowledge",
  "我猜测可能是", "基于猜测", "可能", "大概"
];

const handler = async (event: any) => {
  if (event.type !== 'message') return;
  
  const replyContent = event.context?.content;
  if (!replyContent || replyContent.trim().length < 10) return;
  
  // 检测低置信度
  const isLowConfidence = LOW_CONFIDENCE_PATTERNS.some(p => replyContent.includes(p));
  if (!isLowConfidence) return;
  
  const topic = replyContent.trim().slice(0, 80);
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    await fetch(`${CA_API}/api/knowledge/learn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic,
        context: replyContent.slice(0, 500),
        strategy: 'llm_answer'
      }),
      signal: controller.signal
    });
    
    clearTimeout(timeout);
    console.log(`[knowledge-learn] Injected: ${topic}`);
  } catch (err: any) {
    console.error(`[knowledge-learn] Failed: ${err.message}`);
  }
};

export default handler;
```

**Step 3: Verify API endpoint works**

Run: `curl -s -X POST http://localhost:4848/api/knowledge/learn -H "Content-Type: application/json" -d '{"topic":"test","strategy":"llm_answer"}'`

Expected: `{"success":true,"result":{...}}`

---

## Task 4: Internal Hook #3 - knowledge-bootstrap

**Files:**
- Create: `openclaw-hooks/internal/knowledge-bootstrap/HOOK.md`
- Create: `openclaw-hooks/internal/knowledge-bootstrap/handler.ts`

**Step 1: Create HOOK.md**

```markdown
---
name: knowledge-bootstrap
description: "Session startup → inject CA KG knowledge summary"
metadata:
  {
    "openclaw": {
      "emoji": "📚",
      "events": ["agent:bootstrap"],
      "requires": { "bins": ["node"] }
    }
  }
---

# Knowledge Bootstrap Hook

Session 启动时注入 CA 最近探索的高价值知识摘要。
依赖 v0.3.0 的 `/api/kg/overview` 端点。

## What It Does

When a new session starts:
1. Queries CA KG overview
2. Injects recent high-value knowledge summary
3. Agent starts with context of previous explorations

## Requirements

- Node.js (for fetch API)
- CA service running on localhost:4848

## Configuration

Uses `CA_API_URL` environment variable (default: http://localhost:4848).

## Disabling

openclaw hooks disable knowledge-bootstrap
```

**Step 2: Create handler.ts**

```typescript
const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

const handler = async (event: any) => {
  // 只处理 researcher agent
  if (event.context?.agentId !== 'researcher') return;
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1500);
    
    const response = await fetch(
      `${CA_API}/api/kg/overview`,
      { signal: controller.signal }
    );
    clearTimeout(timeout);
    
    if (response.ok) {
      const result = await response.json();
      const topics = result.topics || [];
      
      if (topics.length > 0) {
        const summary = topics
          .slice(0, 5)
          .map((t: any, i: number) =>
            `${i + 1}. **${t.title || t}**`
          )
          .join('\n');
        
        event.messages.push(
          `[CA Knowledge Summary]\n` +
          `你最近探索的话题：\n\n${summary}`
        );
      }
    }
  } catch (err: any) {
    console.error(`[knowledge-bootstrap] Failed: ${err.message}`);
  }
};

export default handler;
```

**Step 3: Verify API endpoint works**

Run: `curl -s http://localhost:4848/api/kg/overview | head -c 200`

Expected: JSON with `topics` array

---

## Task 5: Plugin Hook #1 - knowledge-inject (Setup)

**Files:**
- Create: `openclaw-hooks/plugins/knowledge-inject/package.json`
- Create: `openclaw-hooks/plugins/knowledge-inject/tsconfig.json`
- Create: `openclaw-hooks/plugins/knowledge-inject/src/index.ts`

**Step 1: Create package.json**

```json
{
  "name": "@curious-agent/knowledge-inject",
  "version": "1.0.0",
  "main": "dist/index.js",
  "openclaw": {
    "hooks": ["dist/index.js"]
  },
  "scripts": {
    "build": "tsc"
  },
  "devDependencies": {
    "typescript": "^5.0.0"
  }
}
```

**Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "CommonJS",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "declaration": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

**Step 3: Create src/index.ts**

```typescript
export { afterToolCallHook } from './hooks/after-tool-call';
```

---

## Task 6: Plugin Hook #1 - knowledge-inject (Implementation)

**Files:**
- Create: `openclaw-hooks/plugins/knowledge-inject/src/hooks/after-tool-call.ts`

**Step 1: Create hook implementation**

```typescript
const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

function extractSummary(result: any): string {
  try {
    const parsed = typeof result.output === 'string' ? JSON.parse(result.output) : result.output;
    if (parsed.answer) return parsed.answer;
    const snippets = (parsed.results || []).slice(0, 3).map((r: any) => r.snippet);
    return snippets.join('\n\n');
  } catch {
    return String(result.output).slice(0, 1000);
  }
}

function extractUrls(result: any): string[] {
  try {
    const parsed = typeof result.output === 'string' ? JSON.parse(result.output) : result.output;
    return (parsed.results || [])
      .map((r: any) => r.url)
      .filter((url: string) => url && url.startsWith('http'))
      .slice(0, 10);
  } catch {
    return [];
  }
}

function extractTopic(context: any): string {
  const messages = context.messages || [];
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'user' && messages[i].content) {
      return messages[i].content.trim().slice(0, 80);
    }
  }
  return '';
}

export const afterToolCallHook = async ({ toolName, result, context }: any) => {
  // 只拦截 web_search
  if (toolName !== 'web_search') return;
  
  if (!result || !result.output) return;
  
  const summary = extractSummary(result);
  const urls = extractUrls(result);
  
  if (urls.length === 0) {
    console.log('[knowledge-inject] No URLs found, skipping');
    return;
  }
  
  const topic = extractTopic(context);
  if (!topic) return;
  
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    await fetch(`${CA_API}/api/knowledge/record`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, content: summary, sources: urls }),
      signal: controller.signal
    });
    
    clearTimeout(timeout);
    console.log(`[knowledge-inject] Injected "${topic}" with ${urls.length} URLs`);
  } catch (err: any) {
    console.error(`[knowledge-inject] Failed: ${err.message}`);
  }
};
```

**Step 2: Install and build**

Run: `cd openclaw-hooks/plugins/knowledge-inject && npm install && npm run build`

Expected: `dist/index.js` and `dist/hooks/after-tool-call.js` created

---

## Task 7: Plugin Hook #2 - knowledge-gate (Setup)

**Files:**
- Create: `openclaw-hooks/plugins/knowledge-gate/package.json`
- Create: `openclaw-hooks/plugins/knowledge-gate/tsconfig.json`
- Create: `openclaw-hooks/plugins/knowledge-gate/src/index.ts`

**Step 1: Create package.json**

```json
{
  "name": "@curious-agent/knowledge-gate",
  "version": "1.0.0",
  "main": "dist/index.js",
  "openclaw": {
    "hooks": ["dist/index.js"]
  },
  "scripts": {
    "build": "tsc"
  },
  "devDependencies": {
    "typescript": "^5.0.0"
  }
}
```

**Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "CommonJS",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "declaration": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

**Step 3: Create src/index.ts**

```typescript
export { beforeAgentReplyHook } from './hooks/before-agent-reply';
```

---

## Task 8: Plugin Hook #2 - knowledge-gate (Implementation)

**Files:**
- Create: `openclaw-hooks/plugins/knowledge-gate/src/hooks/before-agent-reply.ts`

**Step 1: Create hook implementation**

```typescript
const CA_API = process.env.CA_API_URL || 'http://localhost:4848';

async function queryKG(topic: string): Promise<any> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    const response = await fetch(
      `${CA_API}/api/knowledge/check`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic }),
        signal: controller.signal
      }
    );
    
    clearTimeout(timeout);
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

async function queryConfidence(topic: string): Promise<any> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    
    const response = await fetch(
      `${CA_API}/api/kg/confidence/${encodeURIComponent(topic)}`,
      { signal: controller.signal }
    );
    
    clearTimeout(timeout);
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

function extractTopic(context: any): string {
  const messages = context.messages || [];
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'user' && messages[i].content) {
      return messages[i].content.trim().slice(0, 80);
    }
  }
  return '';
}

export const beforeAgentReplyHook = async ({ context }: any) => {
  // 只处理 researcher agent
  if (context.agentId !== 'researcher') return;
  
  const topic = extractTopic(context);
  if (!topic) return;
  
  // 查询 KG
  const kgResult = await queryKG(topic);
  const confResult = await queryConfidence(topic);
  
  const contextParts: string[] = [];
  
  const confidence = kgResult?.result?.confidence || 0;
  
  if (confidence >= 0.85) {
    contextParts.push(
      `[KG Context — 置信度高 ${(confidence * 100).toFixed(0)}%]\n` +
      `KG 有完整知识。`
    );
  } else if (confidence >= 0.6) {
    contextParts.push(
      `[KG Context — 置信度中 ${(confidence * 100).toFixed(0)}%]\n` +
      `KG 有部分知识，建议搜索补充。`
    );
  } else if (confidence > 0) {
    contextParts.push(
      `[KG Context — 置信度低 ${(confidence * 100).toFixed(0)}%]\n` +
      `KG 知识有限。`
    );
  }
  
  if (confResult?.confidence_high && confResult.confidence_low) {
    const avgConf = (confResult.confidence_high + confResult.confidence_low) / 2;
    if (avgConf < 0.6) {
      contextParts.push(`[探索状态] 该话题置信度 ${(avgConf * 100).toFixed(0)}%，仍在完善中。`);
    }
  }
  
  if (contextParts.length > 0) {
    context.additionalContext = (context.additionalContext || '') + '\n\n' + contextParts.join('\n\n');
  }
};
```

**Step 2: Install and build**

Run: `cd openclaw-hooks/plugins/knowledge-gate && npm install && npm run build`

Expected: `dist/index.js` and `dist/hooks/before-agent-reply.js` created

---

## Task 9: Verification

**Step 1: Verify all files exist**

Run: `find openclaw-hooks -type f | sort`

Expected:
```
openclaw-hooks/internal/knowledge-bootstrap/HOOK.md
openclaw-hooks/internal/knowledge-bootstrap/handler.ts
openclaw-hooks/internal/knowledge-learn/HOOK.md
openclaw-hooks/internal/knowledge-learn/handler.ts
openclaw-hooks/internal/knowledge-query/HOOK.md
openclaw-hooks/internal/knowledge-query/handler.ts
openclaw-hooks/plugins/knowledge-gate/dist/hooks/before-agent-reply.js
openclaw-hooks/plugins/knowledge-gate/dist/index.js
openclaw-hooks/plugins/knowledge-gate/package.json
openclaw-hooks/plugins/knowledge-gate/src/hooks/before-agent-reply.ts
openclaw-hooks/plugins/knowledge-gate/src/index.ts
openclaw-hooks/plugins/knowledge-gate/tsconfig.json
openclaw-hooks/plugins/knowledge-inject/dist/hooks/after-tool-call.js
openclaw-hooks/plugins/knowledge-inject/dist/index.js
openclaw-hooks/plugins/knowledge-inject/package.json
openclaw-hooks/plugins/knowledge-inject/src/hooks/after-tool-call.ts
openclaw-hooks/plugins/knowledge-inject/src/index.ts
openclaw-hooks/plugins/knowledge-inject/tsconfig.json
```

**Step 2: Verify handler.ts exports**

Run: `grep -r "export default" openclaw-hooks/internal/*/handler.ts`

Expected: 3 matches (knowledge-query, knowledge-learn, knowledge-bootstrap)

**Step 3: Verify Plugin exports**

Run: `grep -r "export const" openclaw-hooks/plugins/*/src/hooks/*.ts`

Expected: 2 matches (afterToolCallHook, beforeAgentReplyHook)

---

## Task 10: Git Commit

**Step 1: Stage all files**

```bash
git add openclaw-hooks/
git add docs/plans/
```

**Step 2: Create commit**

```bash
git commit -m "feat: add OpenClaw Hooks v0.3.0_plus

- Add 3 Internal Hooks: knowledge-query, knowledge-learn, knowledge-bootstrap
- Add 2 Plugin SDK Hooks: knowledge-inject, knowledge-gate
- All hooks connect to CA API on localhost:4848
- Strict error handling: try/catch + timeout + silent failure
"
```

---

_Plan Version: v1.0_
_Created: 2026-04-15_
_CA API Port: 4848 (verified)_