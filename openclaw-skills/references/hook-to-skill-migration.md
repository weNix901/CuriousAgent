# Hook → Skill 迁移方案

## 背景

原设计：`knowledge-query` Hook 在 `message:received` 事件拦截**所有**用户消息 → 查询 CA KG。

问题：
1. **效率浪费**：执行类指令（"帮我跑命令"、"写代码"）不需要知识查询，每次都拦截浪费资源
2. **增加延迟**：每条消息都要等 API 响应才能继续
3. **语义错误**：知识查询是 Agent 能力，应该由 Agent 按需调用，不是强制拦截

## 迁移目标

- ✅ **精准触发**：由 Agent 自主判断何时需要知识查询
- ✅ **复用现有 API**：CA 的 `/api/knowledge/confidence` 完全不用改
- ✅ **符合 OpenClaw 规范**：Skill 接口标准，方便调用
- ✅ **兼容过渡**：原 Hook 可保留作为可选配置，默认禁用

## 迁移步骤

### 1. 安装 Skill

```bash
# 创建 Skill 目录
mkdir -p ~/.openclaw/skills/knowledge-query

# 复制文件
cp /root/dev/curious-agent/openclaw-skills/knowledge-query/SKILL.md ~/.openclaw/skills/knowledge-query/
cp /root/dev/curious-agent/openclaw-skills/knowledge-query/handler.py ~/.openclaw/skills/knowledge-query/

# 增加执行权限
chmod +x ~/.openclaw/skills/knowledge-query/handler.py

# 验证安装
openclaw skills list
# 应看到 knowledge-query ✅
```

### 2. 禁用原 Hook（可选但推荐）

```bash
# 禁用 knowledge-query Hook
openclaw hooks disable knowledge-query

# 验证
openclaw hooks list
# knowledge-query 应为 ❌ disabled
```

### 3. 更新 R1D3 工作流

修改 `AGENTS.md`（或 R1D3 的回答流程）：

**原流程（Hook 版）：**
```
用户消息 → Hook 拦截查询 KG → 注入置信度 → R1D3 回答
```

**新流程（Skill 版）：**
```
用户消息 → R1D3 分析意图
    ├─ 判断为**知识问询类** → 主动调用 `skill knowledge-query {"topic": "..."}` → 获取 KG 上下文 → 回答
    └─ 判断为**执行操作类** → 直接执行，不查询 KG
```

### 4. R1D3 意图判断规则

什么样的消息需要调用 knowledge-query？

| 类型 | 需要查询？ | 示例 |
|------|-----------|------|
| 知识问询 | ✅ | "什么是 X"、"解释 Y"、"Z 怎么做"、"分析一下..." |
| 技术概念 | ✅ | "Hook vs Skill"、"React 原理" |
| 事实查询 | ✅ | "现在天气"、"最新版本" |
| 命令执行 | ❌ | "ls -la"、"帮我重启服务"、"修改这个文件" |
| 代码编写 | ❌ | "写一个 Python 函数"、"帮我 debug" |
| 日常对话 | ❌ | "你好"、"今天天气不错" |

## 其他 Hook 的评估

当前安装了 5 个 CA Hook，评估是否需要迁移：

| Hook | 事件 | 当前功能 | 是否需要迁移 | 理由 |
|------|------|---------|-------------|------|
| **knowledge-query** | `message:received` | 拦截查询 KG | ✅ **已迁移** | 本文就是迁移它 |
| **knowledge-learn** | `message:sent` | Agent 回复后检测低置信度 → 注入探索队列 | ❌ **保持 Hook** | 需要在回答后自动检测，Agent 自己不会主动调用学习 |
| **knowledge-bootstrap** | `agent:bootstrap` | Session 启动注入知识摘要 | ❌ **保持 Hook** | 生命周期事件触发，不是 Agent 主动调用 |
| **knowledge-inject** | `after_tool_call` | web_search 后自动记录到 KG | ❌ **保持 Hook** | 工具调用后的自动处理，不需要 Agent 判断 |
| **knowledge-gate** | `before_agent_reply` | 回复前二次查 KG 注入 | ⚠️ **可考虑迁移** | 和 knowledge-query 类似，也是知识查询。但它是二次检查，可以保持 Hook 作为"保险 gate" |

### 结论：

只迁移 `knowledge-query`，其他 4 个保持 Hook 不变。`knowledge-gate` 作为最终检查门，保持 Hook 是合理的。

## Hybrid 方案（可选）

如果你想保留 Hook 的自动触发，但又不想全量匹配，可以改造成**轻量意图分类 Hook**：

```typescript
// handler.ts 改造
const is_knowledge_query = (text: string): boolean => {
  // 简单关键词/正则判断
  const knowledge_patterns = [
    /什么是|解释|如何|怎么|为什么|分析|介绍/i,
    /^what is|^how to|^explain|^why/i,
  ];
  return knowledge_patterns.some(p => p.test(text));
};

const handler = async (event) => {
  // 先判断意图，不是知识查询直接放行
  if (!is_knowledge_query(event.context.content)) {
    return; // 不注入任何东西，直接继续
  }
  // 是知识查询 → 才调用 KG API
  // ... existing logic
};
```

这种方案适合**默认自动检测**，但仍会有一定误判。最佳方案还是让 Agent 自己判断 → 调用 Skill。

## 回滚方案

如果迁移后有问题，随时可以回滚：

```bash
# 恢复 Hook
openclaw hooks enable knowledge-query

# 删除 Skill
rm -rf ~/.openclaw/skills/knowledge-query
```

## 验收标准

迁移完成后：

1. ✅ `openclaw skills list` 显示 `knowledge-query` ✓ ready
2. ✅ `openclaw hooks list` 显示 `knowledge-query` ❌ disabled（可选，如果选择完全迁移）
3. ✅ 知识问询类消息：R1D3 调用 `knowledge-query` Skill → 获取 KG 上下文 → 正确回答
4. ✅ 执行操作类消息：R1D3 直接执行，不触发 KG 查询 → 响应更快
5. ✅ CA API 负载降低：查询量减少 30-50%（取决于对话比例）

## 作者

Curious Agent Team • 2026-04-19
