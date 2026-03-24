---
name: curious-agent
description: "Curious Agent 接入工具包。When an agent needs to check its knowledge confidence on a topic, trigger active exploration, sync discoveries, or share new findings with the user. Covers: (1) confidence checking before answering, (2) injecting topics for exploration, (3) syncing exploration results to memory, (4) proactive sharing of new discoveries. Trigger scenarios: user asks a question, agent wants to check its knowledge boundary, agent wants to explore a topic proactively."
---

# Curious Agent Skill

接入 Curious Agent 的完整工具包，包含 4 个工具和 3 个配置注入文件。

## 快速安装

### Step 1: 安装 scripts

将 `scripts/` 目录下的所有文件复制到 agent workspace 的 `scripts/` 目录：

```bash
mkdir -p YOUR_WORKSPACE/scripts
cp -r skills/curious-agent/scripts/* YOUR_WORKSPACE/scripts/
chmod +x YOUR_WORKSPACE/scripts/*.sh
```

### Step 2: 注入配置规则

将 `references/` 下的 3 个文件内容合并到对应配置：

| 文件 | 注入位置 |
|------|---------|
| `references/agents_md_rules.md` | 合并到 `AGENTS.md` 的 "Every Session" 之后 |
| `references/soul_md_rules.md` | 合并到 `SOUL.md` 的 `## 📋 职责` 之后 |
| `references/heartbeat_md_rules.md` | 合并到 `HEARTBEAT.md` 的 `## Proactive Behaviors` |

### Step 3: 注册 Skill

在 OpenClaw 的 `openclaw.json` 中添加：

```json
"skills": {
  "entries": {
    "curious-agent": {
      "enabled": true,
      "env": {
        "CURIOUS_API_URL": "http://localhost:4848"
      }
    }
  }
}
```

---

## 工具清单

### Tool 1: check_confidence.sh

检查 agent 对某个主题的置信度。

```bash
bash scripts/check_confidence.sh "主题关键词"
```

**返回字段**：
- `should_explore: true` → 置信度低，需要探索
- `should_explore: false` → 置信度足够，可以直接回答
- `explore_count` → 已探索次数（超过 3 次停止）

**使用时机**：用户提问后，agent 可以先用此工具判断是否需要触发探索。

### Tool 2: trigger_explore.sh

主动触发 Curious Agent 定向探索。

```bash
bash scripts/trigger_explore.sh "主题" "上下文"
```

**参数**：
- `$1`: topic（必填）
- `$2`: context（可选）

**返回**：`status: ok` → 任务已加入队列

**使用时机**：
- agent 检查置信度后发现 `should_explore: true`
- 用户提问但 agent 没有相关记忆
- agent 想主动延伸当前话题

### Tool 3: sync_discoveries.py

同步 Curious Agent 的探索发现到记忆系统。

```bash
python3 scripts/sync_discoveries.py
```

**行为**：
- 从 Curious Agent KG 读取新探索结果
- 写入 `memory/curious/` 目录（每个发现一个 .md 文件）
- 更新 `memory/curious-discoveries.md` 索引（标记 `shared:false`）

**使用时机**：每次心跳时调用。

### Tool 4: share_new_discoveries.py

检查并返回未分享的发现。

```bash
# 只列出，不标记
python3 scripts/share_new_discoveries.py --list

# 列出并标记为已分享
python3 scripts/share_new_discoveries.py --share
```

**返回格式**：
```json
{
  "undiscovered": [
    {"title": "Agent Memory Systems", "score": 8.2, "shared": false},
    ...
  ],
  "count": N
}
```

---

## 典型工作流

### 回答流程

```
用户提问 → memory_search → 找到答案 → 直接回答（expert 模式）
                              ↓ 没找到
                       check_confidence.sh
                              ↓
                   should_explore: true?
                              ↓ 是
                    trigger_explore.sh
                              ↓
                    先诚实回答（novice 模式）
                    探索结果后续同步
```

### 心跳流程

```
每次心跳：
  1. sync_discoveries.py      → 同步最新发现
  2. share_new_discoveries.py → 检查 shared:false
  3. 有未分享 → 主动告诉用户："你之前问的 XXX，我现在有答案了..."
  4. mark shared:true
```

---

## 配置项

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `CURIOUS_API_URL` | `http://localhost:4848` | Curious Agent API 地址 |
| `CURIOUS_STATE` | `/root/dev/curious-agent/knowledge/state.json` | KG 状态文件路径 |
| `CURIOUS_DIR` | `memory/curious` | 发现文件目录 |
| `CURIOUS_INDEX` | `memory/curious-discoveries.md` | 索引文件路径 |

---

## API 端点参考

| 功能 | 端点 | 方法 |
|------|------|------|
| 置信度检查 | `/api/metacognitive/check?topic=` | GET |
| 触发探索 | `/api/curious/inject` | POST |
| 查看状态 | `/api/curious/state` | GET |

Curious Agent Web UI: http://10.1.0.13:4848
