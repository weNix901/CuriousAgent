---
name: ca-integration
description: "Curious Agent 集成 — KG 优先认知框架、置信度感知、自动探索触发、OpenClaw Hook 安装指南。当用户提问时，先查 CA 知识图谱，再搜索，最后 LLM 猜测并触发后台探索。包含 4 个脚本工具和 5 个 Hook 的一键安装。Use when: (1) answering questions that may be in CA knowledge graph, (2) checking knowledge confidence on a topic, (3) triggering CA exploration, (4) syncing CA discoveries, (5) sharing CA findings with the user, (6) installing CA OpenClaw hooks for a new agent."
---

# Curious Agent 集成

将 CA（Curious Agent）知识图谱集成到 Agent 认知框架中，实现"知道自己知道什么、知道自己不知道什么"。

## 首次安装

> 首次加载此 Skill 时，执行以下 5 步安装。完成后只需保留运行时认知框架。

### Step 1: 安装 scripts

```bash
mkdir -p <workspace>/scripts
cp /root/dev/curious-agent/skills/curious-agent/scripts/*.sh <workspace>/scripts/
cp /root/dev/curious-agent/skills/curious-agent/scripts/*.py <workspace>/scripts/
chmod +x <workspace>/scripts/*.sh
```

### Step 2: 安装 OpenClaw Hook（Internal）

3 个 Internal Hook 直接从 CA 仓库复制到 OpenClaw hooks 目录：

```bash
# 复制 3 个 Internal Hook
for hook in knowledge-query knowledge-learn knowledge-bootstrap; do
  cp -r /root/dev/curious-agent/openclaw-hooks/internal/$hook ~/.openclaw/hooks/$hook
done

# 验证
ls ~/.openclaw/hooks/
```

### Step 3: 编译安装 Plugin SDK Hook

2 个 Plugin Hook 需要编译后通过 hooks install 安装：

```bash
# knowledge-inject
cd /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-inject
npm install && npm run build
openclaw hooks install $(pwd) --link

# knowledge-gate
cd /root/dev/curious-agent/openclaw-hooks/plugins/knowledge-gate
npm install && npm run build
openclaw hooks install $(pwd) --link
```

> 注：`openclaw hooks install` 标记为 deprecated，底层调用 `openclaw plugins install`，两者均可。不要用 `openclaw plugins link`（该命令不存在）。

详细安装步骤（含故障排查）见 [references/hook-install.md](references/hook-install.md)。

### Step 4: 配置 CA API 地址

在 `~/.openclaw/openclaw.json` 的 `env` 中确保有：

```json
{
  "env": {
    "CA_API_URL": "http://localhost:4848"
  }
}
```

### Step 5: 启动 CA 服务

> ⚠️ 必须先启动 CA 服务，否则所有 hook 会静默失败（连接不到 API）。

使用 CA 仓库的 `start.sh` 一键启动：

```bash
cd /root/dev/curious-agent
bash start.sh
```

`start.sh` 会自动：清理旧进程 → 检查 Neo4j → 启动 API（端口 4848）→ 启动 Daemon（后台探索）→ 验证就绪。

验证 CA 服务运行：

```bash
curl -s http://localhost:4848/api/kg/overview | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'KG: {len(d.get(\"nodes\",[]))} nodes, {len(d.get(\"edges\",[]))} edges')"
```

> **不要**手动分别启动 `curious_api.py` 和 `curious_agent.py`。必须同时运行两者，否则 Daemon 不消费队列会导致任务积压死锁。

### Step 6: 重启 OpenClaw 并验证

```bash
openclaw gateway restart
openclaw hooks list
# 应看到 5 个 hook: knowledge-query, knowledge-learn, knowledge-bootstrap, knowledge-inject, knowledge-gate
```

## 认知框架（运行时）

用户提问时，按以下顺序执行（Hook 未安装时手动执行）：

### Level 1：查 KG

```bash
bash scripts/check_confidence.sh "<话题>"
```

- `confidence > 0.6` 且 `found=true` → 从 KG 构建回答，标注 **"从我的知识中…"**，**停止**
- 未找到或置信度低 → 进入 Level 2

### Level 2：Web 搜索

调用 `web_search`，有结果 → 标注 **"我刚搜索了一下…"**

### Level 3：LLM 内化

标注 **"基于 LLM 的知识，我猜测…"**，然后触发探索：

```bash
bash scripts/trigger_explore.sh "<话题>"
```

### 与 Hook 的协作

安装 5 个 Hook 后：
- Level 1/2/3 会被 Hook **自动增强**（自动查 KG、自动注入上下文、自动记录搜索结果）
- Agent 的正常回答流程不变，Hook 在后台透明工作
- Agent 回复中的低置信度标记会被 knowledge-learn 自动检测并注入 CA 队列

## 心跳流程

```
每次心跳：
  1. sync_discoveries.py      → 同步 CA 最新发现
  2. share_new_discoveries.py → 检查未分享
  3. 有未分享 → 主动告诉用户
  4. 无新发现 → 不打扰
```

## 工具清单

| 工具 | 用途 | 使用时机 |
|------|------|---------|
| `check_confidence.sh` | 查话题置信度 | 用户提问后，判断是否需要探索 |
| `trigger_explore.sh` | 触发 CA 探索 | 确认需要探索时 |
| `sync_discoveries.py` | 同步发现到记忆 | 每次心跳 |
| `share_new_discoveries.py` | 检查未分享发现 | 每次心跳 |

## 配置项

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `CA_API_URL` | `http://localhost:4848` | CA API 地址 |
| `CURIOUS_STATE` | `/root/dev/curious-agent/knowledge/state.json` | KG 状态文件 |
| `CURIOUS_DIR` | `memory/curious` | 发现文件目录 |

## 参考

- 完整 API 端点文档：[references/api.md](references/api.md)
- Hook 详细安装指南：[references/hook-install.md](references/hook-install.md)
- CA 服务启动：`cd /root/dev/curious-agent && bash start.sh`
- CA Web UI: http://10.1.0.13:4848
