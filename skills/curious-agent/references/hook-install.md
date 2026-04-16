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
openclaw hooks install $(pwd) --link
echo "✅ Installed: knowledge-inject"
```

### knowledge-gate

```bash
cd /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-gate
npm install
npm run build
openclaw hooks install $(pwd) --link
echo "✅ Installed: knowledge-gate"
```

> 注：`openclaw hooks install` 底层调用 `openclaw plugins install`，两者均可。
> **不要**用 `openclaw plugins link`（该命令不存在）。

**验证**:
```bash
openclaw hooks list
# 应看到 knowledge-inject 和 knowledge-gate 均为 ✓ ready
```

> 注意：这两个包注册在 `hooks.internal.installs` 中，`openclaw plugins list` 不会显示它们。

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

使用 CA 仓库的 `start.sh` 一键启动（清理旧进程 + 检查 Neo4j + 启动 API + Daemon）：

```bash
cd /root/dev/curious-agent
bash start.sh
curl -s -o /dev/null -w "%{http_code}" http://localhost:4848/
# 应返回 200
```

`start.sh` 会完成以下工作：
1. 杀掉旧的 curious_agent/curious_api 进程
2. 检查 Neo4j 状态（未运行则自动启动）
3. 启动 `curious_api.py`（HTTP API，端口 4848）
4. 启动 `curious_agent.py --daemon`（后台探索 Daemon）
5. 验证 API 就绪

> **不要**手动分别启动 API 和 Daemon — 使用 `start.sh` 确保两者同时运行，避免死锁（API 无 Daemon 消费队列会导致任务积压）。

如果需要停止所有 CA 服务：
```bash
pkill -f curious_api.py
pkill -f curious_agent.py
```

### Hook 静默失败（不生效）

Hook 都有 try/catch 静默失败，需查看 OpenClaw 日志：
```bash
# 查看 OpenClaw 日志中的 hook 错误
grep -i "knowledge-" ~/.openclaw/logs/*.log 2>/dev/null | tail -20
```

### Plugin 加载失败

```bash
# 检查 dist/ 编译输出
ls /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-inject/dist/

# 检查安装记录
cat ~/.openclaw/openclaw.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('hooks',{}).get('internal',{}).get('installs',{}), indent=2))"

# 重新编译+安装
cd /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-inject
rm -rf dist && npm run build
openclaw hooks install $(pwd) --link
```
