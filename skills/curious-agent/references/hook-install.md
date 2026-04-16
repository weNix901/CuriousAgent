# CA Hook 安装指南

> 详细安装步骤。SKILL.md 中简要提及，按需加载。

## 前置条件

```bash
# 1. CA 服务正在运行
curl -s http://localhost:4848/api/kg/overview | head -1
# 应返回 JSON

# 2. Node.js 可用（Hook 需要）
node --version
```

## Internal Hook（3 个）

Internal Hook 直接复制即可，无需编译。

| Hook | 事件 | 功能 |
|------|------|------|
| knowledge-query | message:received | 用户发消息 → 查 KG 注入上下文 |
| knowledge-learn | message:sent | Agent 回复 → 检测低置信度注入队列 |
| knowledge-bootstrap | agent:bootstrap | Session 启动 → 注入知识摘要 |

```bash
for hook in knowledge-query knowledge-learn knowledge-bootstrap; do
  cp -r /root/dev/curious-agent/openclaw-hooks/internal/$hook ~/.openclaw/hooks/$hook
  echo "✅ Installed: $hook"
done
```

**验证**:
```bash
openclaw hooks list
# 应看到 3 个 hook
```

## Plugin SDK Hook（2 个）

Plugin Hook 需要编译为 JavaScript 后才能被 OpenClaw 加载。

| Plugin | 事件 | 功能 |
|--------|------|------|
| knowledge-inject | after_tool_call | web_search 后 → 自动记录到 KG |
| knowledge-gate | before_agent_reply | 回复前 → 双重查 KG 注入上下文 |

### knowledge-inject

```bash
cd /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-inject
npm install
npm run build
# 输出到 dist/ 目录
openclaw plugins link $(pwd)
echo "✅ Installed: knowledge-inject"
```

### knowledge-gate

```bash
cd /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-gate
npm install
npm run build
openclaw plugins link $(pwd)
echo "✅ Installed: knowledge-gate"
```

**验证**:
```bash
openclaw plugins list
# 应看到 @curious-agent/knowledge-inject 和 @curious-agent/knowledge-gate
```

## 配置 CA API 地址

确保 OpenClaw 环境有 `CA_API_URL` 变量：

在 `~/.openclaw/openclaw.json` 中：
```json
{
  "env": {
    "CA_API_URL": "http://localhost:4848"
  }
}
```

或者在 shell profile 中：
```bash
export CA_API_URL=http://localhost:4848
```

## 重启并验证

```bash
openclaw gateway restart
sleep 3
openclaw hooks list
```

应看到 5 个 Hook 全部 ready：
- knowledge-query ✅
- knowledge-learn ✅
- knowledge-bootstrap ✅
- knowledge-inject ✅（Plugin）
- knowledge-gate ✅（Plugin）

## 故障排查

### Hook 未加载

```bash
# 检查文件是否存在
ls -la ~/.openclaw/hooks/knowledge-query/HOOK.md
ls -la ~/.openclaw/hooks/knowledge-query/handler.ts

# 检查 Plugin 编译输出
ls /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-inject/dist/
```

### CA 服务未运行

```bash
cd /root/dev/curious-agent
nohup python3 curious_api.py > /tmp/curious_api.log 2>&1 &
curl -s -o /dev/null -w "%{http_code}" http://localhost:4848/
# 应返回 200
```

### Hook 静默失败（不生效）

Hook 都有 try/catch 静默失败，需查看 OpenClaw 日志：
```bash
# 查看 OpenClaw 日志中的 hook 错误
grep -i "knowledge-" ~/.openclaw/logs/*.log 2>/dev/null | tail -20
```

### Plugin 加载失败

```bash
# 检查 package.json 是否有 openclaw.hooks 字段
cat /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-inject/package.json | grep -A2 '"openclaw"'

# 重新编译
cd /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-inject
rm -rf dist && npm run build
```
