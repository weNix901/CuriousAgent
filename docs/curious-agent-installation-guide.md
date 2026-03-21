# Curious Agent × OpenClaw 心跳集成接入手册

> 适用版本：Curious Agent v0.2+ | OpenClaw 2026.3+
> 让 Curious Agent 成为你的 AI 研究员的"好奇心内核"，通过 OpenClaw 心跳自动运行

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenClaw 主 Agent                            │
│                      (你的 AI 研究员)                            │
│                                                                 │
│   心跳触发 (默认 30m/次)                                        │
│         │                                                       │
│         ▼                                                       │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  读取 HEARTBEAT.md                                      │   │
│   │  → 执行 sync_discoveries.py 同步探索发现                │   │
│   │  → 检查是否有新发现需要分享                              │   │
│   │  → 若有发现，主动告诉用户                                 │   │
│   │  → 若无则回复 HEARTBEAT_OK                               │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  OpenClaw 主 Agent 记忆系统                            │   │
│   │  → 探索发现 → memory/curious-discoveries.md            │   │
│   │  → memory_search() 可检索                              │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Curious Agent 后台服务                                 │   │
│   │  → API: http://localhost:4848/                          │   │
│   │  → Web UI: http://10.1.0.13:4849/                      │   │
│   │  → 定时探索 (每30分钟 via Cron 或独立进程)              │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**数据流向**：

```
用户 (飞书/Discord/...) 
         ▲
         │ 主动分享发现
         │
OpenClaw Agent ─── 心跳触发 ────▶ sync_discoveries.py ──▶ memory/curious/
         │                                    │
         │                                    ▼
         │                           memory/curious-discoveries.md
         │                                    │
         │                                    ▼
         │                           memory_search() 可检索
         │
         │
Curious Agent 后台服务
         │
         ├── 探索日志 ──▶ state.json (curious_api.py 写入)
         │
         └── Web UI ──▶ 实时查看探索状态
```

---

## 二、前置条件

### 2.1 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.11+ |
| OpenClaw | 2026.3+ |
| 网络 | 能访问 Bocha Search API（用于 Web 搜索） |
| 端口 | 4848/4849 未被占用（可配置） |

### 2.2 目录结构

```
/root/dev/curious-agent/          ← Curious Agent 安装目录
├── curious_agent.py              ← 主程序（CLI 入口）
├── curious_api.py                ← API 服务（Web UI）
├── knowledge/
│   └── state.json                ← 探索状态文件
├── logs/                         ← 日志目录
├── memory/curious/               ← 发现存储（sync_discoveries.py 写入）
└── run_curious.sh                ← 一键启动脚本

/root/.openclaw/workspace-researcher/  ← OpenClaw Agent 工作空间
├── HEARTBEAT.md                  ← 心跳任务清单（关键！）
├── scripts/
│   └── sync_discoveries.py       ← 同步脚本（从 Curious Agent 同步到记忆）
└── memory/
    └── curious/                  ← 发现的永久存储
```

### 2.3 检查当前状态

```bash
# 1. 确认 Curious Agent 已安装
ls -la /root/dev/curious-agent/

# 2. 确认 Python 版本
python3 --version  # 应为 3.11+

# 3. 确认端口可用
netstat -tlnp | grep -E "4848|4849"
# 若有输出说明端口被占用，需要先停止旧进程
```

---

## 三、部署步骤

### Step 1：部署 Curious Agent 后台服务

```bash
# 进入安装目录
cd /root/dev/curious-agent

# 启动 API 服务（后台运行）
bash run_curious.sh

# 验证启动成功
curl http://localhost:4848/api/curious/state | python3 -m json.tool | head -20
```

**预期输出**：
```json
{
  "status": "ok",
  "curiosity_queue_size": 12,
  "exploration_log_size": 5,
  "uptime_seconds": 3600
}
```

### Step 2：配置 OpenClaw 心跳

编辑 OpenClaw 配置文件（`~/.openclaw/openclaw.json`）：

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "30m",
        "target": "last",
        "directPolicy": "allow"
      }
    }
  }
}
```

**配置说明**：

| 字段 | 值 | 含义 |
|------|-----|------|
| `every` | `"30m"` | 心跳间隔（30分钟） |
| `target` | `"last"` | 发现时主动推送给用户 |
| `directPolicy` | `"allow"` | 允许直接发送消息 |

**其他可选配置**：

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "30m",
        "target": "last",
        "activeHours": {
          "start": "08:00",
          "end": "22:00",
          "timezone": "Asia/Shanghai"
        },
        "lightContext": true,
        "includeReasoning": false
      }
    }
  }
}
```

| 字段 | 含义 |
|------|------|
| `activeHours` | 仅在指定时段运行心跳 |
| `lightContext` | 心跳时仅加载 HEARTBEAT.md（节省 token） |
| `includeReasoning` | 是否发送推理过程 |

### Step 3：创建/更新 HEARTBEAT.md

在 OpenClaw Agent 工作空间创建/编辑 `HEARTBEAT.md`：

**完整版 HEARTBEAT.md**：

```markdown
# HEARTBEAT.md — 好奇心心跳清单

## 好奇心同步
- [x] 同步 Curious Agent 探索发现

### 👁️ 好奇发现主动分享（每次心跳）

读取 `memory/curious-discoveries.md`，找到最新/最有价值的发现，**以我的口吻主动分享给用户**。

不是推送通知，是我有感而发想说。

运行同步脚本：
```bash
python3 /root/.openclaw/workspace-researcher/scripts/sync_discoveries.py
```

## 安全检查
- [ ] 扫描是否有注入攻击尝试

## 可选：运行探索（每 4 小时心跳选一次）
```bash
# 仅当需要主动探索时启用
# python3 /root/dev/curious-agent/curious_agent.py --run --run-depth medium
```

## 记忆维护（每 24 小时心跳选一次）
- [ ] 读取 memory/curious/ 最近发现
- [ ] 更新 memory/curious-discoveries.md 索引
- [ ] 提炼重要发现到 MEMORY.md
```

**简化版 HEARTBEAT.md**（如果只需要同步功能）：

```markdown
# HEARTBEAT.md

## 好奇心同步
同步 Curious Agent 探索发现：
```bash
python3 /root/.openclaw/workspace-researcher/scripts/sync_discoveries.py
```
读取发现并以我的口吻分享给用户（若有新发现）。

若无需关注，回复 HEARTBEAT_OK。
```

---

## 四、核心脚本说明

### 4.1 sync_discoveries.py

**作用**：从 Curious Agent 的 `state.json` 同步探索发现到 OpenClaw 记忆系统。

**文件位置**：`/root/.openclaw/workspace-researcher/scripts/sync_discoveries.py`

**核心逻辑**：
```
1. 读取 /root/dev/curious-agent/knowledge/state.json
2. 检查上次同步时间戳
3. 将未同步的探索结果写入 memory/curious/ 目录
4. 更新 memory/curious-discoveries.md 索引
```

**用法**：
```bash
# 手动同步
python3 /root/.openclaw/workspace-researcher/scripts/sync_discoveries.py

# 输出示例
SYNC: 2 discoveries synced | archived 0 old files
  + /root/.openclaw/workspace-researcher/memory/curious/2026-03-21-metacognitive-monitoring.md
  + /root/.openclaw/workspace-researcher/memory/curious/2026-03-21-predictive-coding.md
```

**在心跳中的行为**：
- 有新发现 → 输出发现列表，Agent 读取并分享给用户
- 无新发现 → 输出 `SYNC: No new discoveries`

### 4.2 curious_agent.py

**作用**：Curious Agent 的主程序，执行探索任务。

**文件位置**：`/root/dev/curious-agent/curious_agent.py`

**常用命令**：

```bash
# 查看状态
python3 curious_agent.py --status

# 注入新话题
python3 curious_agent.py --inject "metacognition" --score 8.0 --depth 8.0 --reason "用户研究兴趣"

# 运行一轮探索
python3 curious_agent.py --run

# 指定深度运行
python3 curious_agent.py --run --run-depth deep

# 查看待探索列表
python3 curious_agent.py --list-pending

# 删除话题
python3 curious_agent.py --delete "过时的话题"

# 守护进程模式（定时探索）
python3 curious_agent.py --daemon --interval 30
```

### 4.3 curious_api.py

**作用**：Curious Agent 的 API 服务 + Web UI。

**启动方式**：
```bash
cd /root/dev/curious-agent
python3 curious_api.py
```

**访问地址**：
- API：http://localhost:4848/
- Web UI：http://10.1.0.13:4849/

---

## 五、OpenClaw 与 Curious Agent 的交互方式

OpenClaw Agent 可以通过三种方式与 Curious Agent 交互：

| 交互方式 | 适用场景 | 复杂度 |
|---------|---------|--------|
| **exec 工具调用 CLI** | 触发探索、注入话题、管理队列 | ⭐ 简单 |
| **REST API 调用** | 查询状态、动态配置、集成外部系统 | ⭐⭐ 中等 |
| **文件系统读写** | 读取 state.json、读取发现文件 | ⭐ 简单 |

### 5.1 exec 工具调用（最常用）

OpenClaw 的 `exec` 工具可以直接运行 `curious_agent.py`：

```bash
# 触发一轮探索
python3 /root/dev/curious-agent/curious_agent.py --run

# 注入新话题（OpenClaw 可以告诉 Agent "帮我注入一个话题"）
python3 /root/dev/curious-agent/curious_agent.py \
  --inject "LLM self-reflection mechanisms" \
  --score 8.5 \
  --depth 8.0 \
  --reason "用户近期研究兴趣"

# 查看当前状态
python3 /root/dev/curious-agent/curious_agent.py --status

# 查看待探索队列
python3 /root/dev/curious-agent/curious_agent.py --list-pending

# 删除已过时的话题
python3 /root/dev/curious-agent/curious_agent.py --delete "过时话题"

# 指定探索深度
python3 /root/dev/curious-agent/curious_agent.py --run --run-depth deep

# 纯好奇模式（无人工干预）
python3 /root/dev/curious-agent/curious_agent.py --run --pure-curious
```

**在 HEARTBEAT.md 中使用示例**：

```markdown
## 可选：运行主动探索
运行深度探索：
bash
python3 /root/dev/curious-agent/curious_agent.py --run --run-depth deep
```

### 5.2 REST API 调用

Curious Agent 提供 REST API，OpenClaw 可以通过 `exec` + `curl` 调用：

#### 查询状态

```bash
curl http://localhost:4848/api/curious/state
```

**响应**：
```json
{
  "status": "ok",
  "curiosity_queue_size": 33,
  "exploration_log_size": 8,
  "uptime_seconds": 86400,
  "current_topic": "Embodied Generative Cognitive",
  "last_exploration": "2026-03-21T08:30:00Z"
}
```

#### 触发一轮探索（POST）

```bash
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"depth": "medium"}'
```

#### 注入新话题（POST）

```bash
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "metacognitive monitoring",
    "score": 8.5,
    "depth": 8.0,
    "reason": "用户研究兴趣"
  }'
```

#### 查询待探索队列（GET）

```bash
curl http://localhost:4848/api/curious/queue/pending
```

**响应**：
```json
{
  "pending": [
    {"topic": "Metacognitive Monitoring", "score": 8.5, "status": "pending"},
    {"topic": "Predictive Coding", "score": 7.8, "status": "pending"}
  ],
  "total": 2
}
```

#### 删除话题（DELETE）

```bash
curl -X DELETE "http://localhost:4848/api/curious/queue?topic=过时话题"
```

#### 完整 API 端点列表

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/curious/state` | 查询系统状态 |
| POST | `/api/curious/run` | 触发一轮探索 |
| POST | `/api/curious/inject` | 注入新话题 |
| POST | `/api/curious/trigger` | 触发特定话题探索 |
| DELETE | `/api/curious/queue?topic=xxx` | 删除指定话题 |
| GET | `/api/curious/queue/pending` | 获取待探索队列 |
| GET | `/` | Web UI 首页 |

### 5.3 通过 Cron 定时触发

OpenClaw Cron 可以定时触发 Curious Agent 探索：

```bash
# 每 4 小时运行一次深度探索
openclaw cron add \
  --name "Curious Agent 深度探索" \
  --cron "0 */4 * * *" \
  --session isolated \
  --message "cd /root/dev/curious-agent && python3 curious_agent.py --run --run-depth deep" \
  --announce \
  --target last

# 每 2 小时运行一次普通探索
openclaw cron add \
  --name "Curious Agent 普通探索" \
  --cron "0 */2 * * *" \
  --session isolated \
  --message "cd /root/dev/curious-agent && python3 curious_agent.py --run --run-depth medium" \
  --announce \
  --target last

# 查看已创建的 Cron 任务
openclaw cron list
```

### 5.4 通过文件系统交互

Curious Agent 的状态存储在 `state.json`，OpenClaw 可以直接读取：

```bash
# 读取当前状态
cat /root/dev/curious-agent/knowledge/state.json | python3 -m json.tool

# 读取探索日志
cat /root/dev/curious-agent/knowledge/state.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
for log in d.get('exploration_log', [])[-3:]:
    print(f\"话题: {log['topic']}\")
    print(f\"  评分: {log.get('score', 'N/A')}\")
    print(f\"  耗时: {log.get('duration', 'N/A')}s\")
    print()
"

# 读取好奇心队列
cat /root/dev/curious-agent/knowledge/state.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
pq = d.get('curiosity_queue', [])
pending = [q for q in pq if q.get('status') == 'pending']
print(f'待探索: {len(pending)} 条')
for q in pending[:5]:
    print(f\"  - {q['topic']} (评分: {q.get('score', 0)})\")
"
```

### 5.5 交互场景示例

#### 场景 1：用户说"帮我研究一下 RAG 技术"

OpenClaw Agent 执行：
```bash
python3 /root/dev/curious-agent/curious_agent.py \
  --inject "RAG retrieval-augmented generation" \
  --score 9.0 \
  --depth 8.0 \
  --reason "用户直接要求研究"
```

#### 场景 2：用户问"上次探索了什么"

OpenClaw Agent 执行：
```bash
python3 /root/dev/curious-agent/curious_agent.py --status
```
然后读取输出回答用户。

#### 场景 3：OpenClaw 发现用户对某话题感兴趣，自动注入

```bash
# 发现用户多次提到 "agent planning"，自动注入
python3 /root/dev/curious-agent/curious_agent.py \
  --inject "agent planning and replanning" \
  --score 8.0 \
  --depth 7.5 \
  --reason "用户多次提到"
```

#### 场景 4：定时深度研究

通过 Cron 每周一早上运行：
```bash
openclaw cron add \
  --name "周一深度研究" \
  --cron "0 9 * * 1" \
  --session isolated \
  --message "cd /root/dev/curious-agent && python3 curious_agent.py --run --run-depth deep" \
  --announce \
  --target last
```

---

## 六、验证与测试

### 6.1 验证 Curious Agent 服务

```bash
# 检查 API 是否正常运行
curl http://localhost:4848/api/curious/state

# 检查探索队列
curl http://localhost:4848/api/curious/queue | python3 -m json.tool | head -30
```

### 5.2 验证同步脚本

```bash
# 运行同步脚本
python3 /root/.openclaw/workspace-researcher/scripts/sync_discoveries.py

# 检查发现文件
ls -la /root/.openclaw/workspace-researcher/memory/curious/
```

### 6.3 验证心跳触发

```bash
# 手动触发一次心跳（立即执行）
openclaw system event --text "Check curiosity" --mode now

# 查看日志
tail -50 /root/.openclaw/logs/agent-*.log
```

### 5.4 端到端测试

```bash
# 1. 注入一个测试话题
cd /root/dev/curious-agent
python3 curious_agent.py --inject "test curiosity integration" --score 5.0 --depth 5.0

# 2. 运行一轮探索
python3 curious_agent.py --run

# 3. 等待几秒让状态写入
sleep 5

# 4. 同步到记忆系统
python3 /root/.openclaw/workspace-researcher/scripts/sync_discoveries.py

# 5. 检查发现文件
cat /root/.openclaw/workspace-researcher/memory/curious-discoveries.md | head -20
```

---

## 六、故障排查

### 问题 1：心跳没有触发

**检查**：
```bash
# 确认心跳配置正确
cat ~/.openclaw/openclaw.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('agents',{}).get('defaults',{}).get('heartbeat',{}))"

# 确认 OpenClaw 运行中
openclaw status

# 查看心跳调度
openclaw sessions list
```

**解决**：重启 OpenClaw 使配置生效
```bash
openclaw gateway restart
```

### 问题 2：sync_discoveries.py 报错 "No curious-agent state found"

**检查**：
```bash
# 确认 Curious Agent 服务运行中
curl http://localhost:4848/api/curious/state

# 确认 state.json 存在
ls -la /root/dev/curious-agent/knowledge/state.json
```

**解决**：启动 Curious Agent 服务
```bash
cd /root/dev/curious-agent
bash run_curious.sh
```

### 问题 3：端口被占用

**错误**：`Address already in use`

**检查**：
```bash
netstat -tlnp | grep -E "4848|4849"
```

**解决**：杀死占用进程
```bash
# 方法1：使用 fuser
fuser -k 4848/tcp 4849/tcp

# 方法2：手动 kill
pkill -f "curious_api.py"
sleep 2
bash run_curious.sh
```

### 问题 4：HEARTBEAT_OK 被发送但没有新发现

**这是正常行为** — 没有新发现时，Agent 正确回复了 HEARTBEAT_OK。

**若想主动探索**：在 HEARTBEAT.md 中取消注释探索命令，或使用 Cron 触发：
```bash
# 每 4 小时运行一次主动探索
openclaw cron add \
  --name "Curious Agent 探索" \
  --cron "0 */4 * * *" \
  --session main \
  --message "python3 /root/dev/curious-agent/curious_agent.py --run --run-depth medium" \
  --wake now
```

---

## 七、高级配置

### 7.1 自定义心跳频率

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "15m",    // 15 分钟（高频）
        "every": "1h",      // 1 小时（低频）
        "every": "0m"       // 禁用心跳
      }
    }
  }
}
```

### 7.2 只在特定时段运行

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "30m",
        "activeHours": {
          "start": "09:00",
          "end": "21:00",
          "timezone": "Asia/Shanghai"
        }
      }
    }
  }
}
```

### 7.3 配置飞书推送

若使用飞书作为通知渠道：

```json
{
  "agents": {
    "defaults": {
      "heartbeat": {
        "every": "30m",
        "target": "feishu"
      }
    }
  },
  "channels": {
    "feishu": {
      "enabled": true
    }
  }
}
```

### 7.4 与 Cron 配合使用

**心跳负责**：同步发现 + 轻量检查
**Cron 负责**：定时主动探索

```bash
# 每 4 小时运行一次主动探索（Cron）
openclaw cron add \
  --name "Curious Agent 深度探索" \
  --cron "0 */4 * * *" \
  --session isolated \
  --message "cd /root/dev/curious-agent && python3 curious_agent.py --run --run-depth deep" \
  --announce \
  --target last

# 每 30 分钟同步一次（心跳自动处理）
# 无需额外配置
```

### 7.5 多用户隔离

若多个 OpenClaw Agent 实例共享 Curious Agent 服务：

```bash
# 为每个用户创建独立端口
PORT=4850 USER_DIR=/home/user2/.openclaw/workspace-researcher bash run_curious.sh
```

对应的 `sync_discoveries.py` 路径也需要调整。

---

## 九、文件路径速查

| 文件 | 路径 | 作用 |
|------|------|------|
| HEARTBEAT.md | `/root/.openclaw/workspace-researcher/HEARTBEAT.md` | 心跳任务清单 |
| sync_discoveries.py | `/root/.openclaw/workspace-researcher/scripts/sync_discoveries.py` | 同步脚本 |
| curious_agent.py | `/root/dev/curious-agent/curious_agent.py` | 探索主程序 |
| curious_api.py | `/root/dev/curious-agent/curious_api.py` | API 服务 |
| run_curious.sh | `/root/dev/curious-agent/run_curious.sh` | 启动脚本 |
| state.json | `/root/dev/curious-agent/knowledge/state.json` | 探索状态 |
| curious-discoveries.md | `/root/.openclaw/workspace-researcher/memory/curious-discoveries.md` | 发现索引 |
| 发现存储 | `/root/.openclaw/workspace-researcher/memory/curious/*.md` | 单条发现 |

---

## 九、快速命令汇总

```bash
# === 启动 Curious Agent ===
cd /root/dev/curious-agent && bash run_curious.sh

# === 查看状态 ===
cd /root/dev/curious-agent && python3 curious_agent.py --status

# === 手动同步发现 ===
python3 /root/.openclaw/workspace-researcher/scripts/sync_discoveries.py

# === 注入新话题 ===
cd /root/dev/curious-agent && python3 curious_agent.py --inject "你的话题" --score 8.0 --depth 7.0

# === 运行一轮探索 ===
cd /root/dev/curious-agent && python3 curious_agent.py --run

# === 查看待探索队列 ===
cd /root/dev/curious-agent && python3 curious_agent.py --list-pending

# === 重启 OpenClaw（使心跳配置生效）===
openclaw gateway restart

# === 手动触发心跳 ===
openclaw system event --text "heartbeat check" --mode now
```

---

## 十、参考链接

- [OpenClaw 心跳文档](file:///root/.nvm/versions/node/v24.13.1/lib/node_modules/openclaw/docs/gateway/heartbeat.md)
- [OpenClaw Cron vs Heartbeat](file:///root/.nvm/versions/node/v24.13.1/lib/node_modules/openclaw/docs/automation/cron-vs-heartbeat.md)
- [Curious Agent README](file:///root/dev/curious-agent/README.md)

---

_文档版本：v1.0_
_创建时间：2026-03-21_
_适用：Curious Agent v0.2+ × OpenClaw 2026.3+_
+_
