# OpenClaw Hooks v0.3.0_plus 设计文档

> **日期**: 2026-04-15
> **状态**: 已验证，准备实施
> **前置条件**: CA API 服务运行于 localhost:4848

---

## 一、设计目标

为 Curious Agent v0.3.0_plus 创建 5 个 OpenClaw Hook，实现 R1D3 与 CA 的知识闭环：

- **R1D3 → CA**: 检测未知话题，注入探索队列
- **CA → R1D3**: KG 知识注入，置信度反馈
- **Web Search → CA**: 搜索结果自动记录到 KG

---

## 二、架构设计

### 2.1 目录结构

```
/root/dev/curious-agent/openclaw-hooks/
├── internal/                    # Internal Hooks (workspace 级)
│   ├── knowledge-query/         # message:received → 查 KG 置信度
│   │   ├── HOOK.md              # YAML frontmatter + Markdown
│   │   └── handler.ts           # TypeScript 实现
│   ├── knowledge-learn/         # message:sent → 低置信度注入
│   │   ├── HOOK.md
│   │   └── handler.ts
│   └── knowledge-bootstrap/     # agent:bootstrap → 知识摘要注入
│   │   ├── HOOK.md
│   │   └── handler.ts
└── plugins/                     # Plugin SDK Hooks
    ├── knowledge-inject/        # after_tool_call → web_search 记录
    │   ├── package.json         # npm 包配置
    │   ├── tsconfig.json        # TypeScript 配置
    │   ├── src/
    │   │   ├── index.ts         # 导出 hook
    │   │   └── hooks/
    │   │       └── after-tool-call.ts
    │   └── dist/                # 编译输出 (npm run build)
    └── knowledge-gate/          # before_agent_reply → KG 知识注入
    │   ├── package.json
    │   ├── tsconfig.json
    │   ├── src/
    │   │   ├── index.ts
    │   │   └── hooks/
    │   │       └── before-agent-reply.ts
    │   └── dist/
```

### 2.2 Hook 功能矩阵

| Hook | 类型 | 触发事件 | API 端点 | 作用 |
|------|------|---------|---------|------|
| knowledge-query | Internal | message:received | /api/r1d3/confidence | 用户提问前查 KG |
| knowledge-learn | Internal | message:sent | /api/knowledge/learn | 低置信度回答注入队列 |
| knowledge-bootstrap | Internal | agent:bootstrap | /api/kg/overview | Session 启动注入摘要 |
| knowledge-inject | Plugin | after_tool_call | /api/knowledge/record | web_search 结果记录 |
| knowledge-gate | Plugin | before_agent_reply | /api/knowledge/check + /api/kg/confidence | 回复前 KG 注入 |

---

## 三、关键设计决策

### 3.1 API 端点端口修正

**问题**: Spec 文档默认端口 `4849`，实际 CA API 运行于 `4848`

**解决方案**: 
```typescript
const CA_API = process.env.CA_API_URL || 'http://localhost:4848';
```

**验证结果** (2026-04-15):
- ✅ `/api/r1d3/confidence` — 返回 `{confidence, level, topic}`
- ✅ `/api/knowledge/learn` — POST 成功
- ✅ `/api/knowledge/check` — 返回 `{result: {found, confidence, gaps}}`
- ✅ `/api/knowledge/record` — POST 成功
- ✅ `/api/kg/overview` — 返回 `{topics, edges}`
- ✅ `/api/kg/confidence/<topic>` — 返回 `{confidence_high, confidence_low}`

### 3.2 错误处理策略

所有 handler.ts 必须遵循 OpenClaw 官方规范：

1. **严格过滤**: `if (event.type !== 'x') return;` 尽早返回
2. **必须 try/catch**: 防止 hook 崩溃影响其他 hook
3. **绝不 throw**: catch 只记日志，不中断流程
4. **超时保护**: AbortController + setTimeout (1000-1500ms)
5. **静默失败**: 所有错误 console.error，不影响正常对话

### 3.3 Internal Hook vs Plugin SDK Hook

| 特性 | Internal Hook | Plugin SDK Hook |
|------|--------------|-----------------|
| 文件 | HOOK.md + handler.ts | package.json + src/*.ts |
| 加载 | OpenClaw 直接加载 | 需 npm build 编译 |
| 导出 | `export default handler` | `export const hookFn` |
| 调试 | 直接修改 handler.ts | 需要 rebuild |

---

## 四、数据流设计

### 4.1 knowledge-query (用户提问 → KG 查询)

```
用户发送消息
    ↓
message:received 事件触发
    ↓
handler.ts 拦截
    ↓
调用 /api/r1d3/confidence?topic=xxx
    ↓
根据 confidence 注入上下文:
  - ≥0.85 (Expert): "KG 有完整知识"
  - 0.6-0.85 (Intermediate): "KG 有部分知识，建议搜索"
  - 0.3-0.6 (Beginner): "KG 知识有限"
  - <0.3 (Novice): "KG 无知识"
    ↓
event.messages.push() 注入
```

### 4.2 knowledge-learn (低置信度回答 → CA 队列)

```
Agent 回复消息
    ↓
message:sent 事件触发
    ↓
handler.ts 检测低置信度关键词:
  - "基于 LLM 知识"
  - "我猜测"
  - "不太确定"
    ↓
调用 POST /api/knowledge/learn
    ↓
CA 队列新增探索任务
    ↓
下次该话题在 KG 中
```

### 4.3 knowledge-bootstrap (Session 启动 → 知识摘要)

```
新 Session 启动
    ↓
agent:bootstrap 事件触发
    ↓
handler.ts 检查 agentId === 'researcher'
    ↓
调用 /api/kg/overview
    ↓
注入最近探索的高价值知识摘要
    ↓
event.messages.push() 注入
```

### 4.4 knowledge-inject (web_search → KG)

```
Agent 执行 web_search 工具
    ↓
after_tool_call 事件触发
    ↓
handler.ts 检查 toolName === 'web_search'
    ↓
提取搜索结果: summary + urls
    ↓
调用 POST /api/knowledge/record
    ↓
CA KG 新增知识节点
```

### 4.5 knowledge-gate (回复前 → KG 注入)

```
Agent 准备回复
    ↓
before_agent_reply 事件触发
    ↓
handler.ts 检查 agentId === 'researcher'
    ↓
调用 POST /api/knowledge/check
    ↓
调用 /api/kg/confidence/<topic>
    ↓
构建上下文注入:
  - KG 置信度信息
  - 探索状态信息
    ↓
context.additionalContext 注入
```

---

## 五、风险评估与缓解

| Hook | 风险等级 | 风险 | 缓解措施 |
|------|---------|------|---------|
| knowledge-bootstrap | 🟢 低 | 只在启动时触发 | 超时 1.5s，失败静默 |
| knowledge-learn | 🟡 中 | 回复后触发，不影响流程 | 超时 1s，fire-and-forget |
| knowledge-query | 🟡 中 | 拦截用户消息，有延迟风险 | 超时 1s，失败不阻塞 |
| knowledge-inject | 🔴 高 | in-process 执行，可能阻塞 | 最后启用，性能监控 |
| knowledge-gate | 🔴 高 | in-process 执行，可能阻塞 | 最后启用，性能监控 |

---

## 六、验收标准

| # | 标准 | 量化条件 | 测试方法 |
|---|------|---------|---------|
| 1 | 目录结构正确 | 5 个 Hook 目录存在 | `ls -la openclaw-hooks/` |
| 2 | HOOK.md 格式正确 | YAML frontmatter + Markdown | 人工检查 |
| 3 | handler.ts 导出正确 | `export default handler` | `grep "export default"` |
| 4 | Plugin 可编译 | `npm run build` 成功 | `npm run build` |
| 5 | API 调用成功 | 端点返回有效 JSON | curl 测试 |
| 6 | 错误静默处理 | CA 服务关闭时 Agent 正常 | 关闭 CA 测试 |

---

## 七、实施计划

### Phase 1: 目录结构 (5 min)
- 创建 `openclaw-hooks/internal/` 和 `openclaw-hooks/plugins/`
- 创建各 Hook 子目录

### Phase 2: Internal Hooks (30 min)
- 创建 3 个 Internal Hook
- 每个: HOOK.md + handler.ts
- 验证 API 调用

### Phase 3: Plugin Hooks (45 min)
- 创建 2 个 Plugin SDK Hook
- 每个: package.json + tsconfig.json + src/
- npm install && npm run build

### Phase 4: 端到端测试 (30 min)
- 启动 CA 服务 (已运行)
- 测试每个 Hook API 调用
- 关闭 CA 测试静默失败

---

_设计版本: v1.0_
_创建日期: 2026-04-15_
_验证状态: API 端点已验证，端口修正为 4848_