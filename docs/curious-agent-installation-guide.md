# Curious Agent × OpenClaw 心跳集成接入手册

> 适用版本：**Curious Agent v0.2.3** | OpenClaw 2026.3+
> 测试状态：**320 测试全部通过** | 最后更新：2026-03-23
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
│   │  Curious Agent v0.2.3 后台服务                         │   │
│   │  → API: http://localhost:4848/                          │   │
│   │  → Web UI: http://10.1.0.13:4849/                      │   │
│   │  → 定时探索 (每30分钟 via Cron 或独立进程)              │   │
│   │  → 话题分解引擎 + 双 Provider 验证                      │   │
│   │  → 元认知监控（质量评估 + 边际收益检测）                │   │
│   │  → 行为闭环（高质量发现自动转行为规则）                 │   │
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
Curious Agent v0.2.3 后台服务
         │
         ├── 探索日志 ──▶ state.json (curious_api.py 写入)
         │
         ├── 话题分解 ──▶ CuriosityDecomposer
         │
         ├── 质量评估 ──▶ MetaCognitiveMonitor
         │
         ├── 行为写入 ──▶ AgentBehaviorWriter
         │
         └── Web UI ──▶ 实时查看探索状态
```

**v0.2.3 核心新特性**：

| 特性 | 说明 |
|------|------|
| **话题分解引擎** | LLM 自动生成子话题，双 Provider 验证，过滤幻觉 |
| **元认知监控** | MGV 循环（Monitor-Generate-Verify），自动检测边际收益递减 |
| **行为闭环** | quality ≥ 7.0 自动写入行为规则，Agent 自我进化 |
| **双 Provider 架构** | Bocha (中文) + Serper (学术)，2+ 通过才算验证 |
| **完整测试覆盖** | 320 个测试全部通过，质量有保障 |

---

## 二、前置条件

### 2.1 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.11+ |
| OpenClaw | 2026.3+ |
| 网络 | 能访问 Bocha Search API（用于 Web 搜索） |
| 端口 | 4848/4849 未被占用（可配置） |
| API Keys | BOCHA_API_KEY、SERPER_API_KEY（用于双 Provider 验证） |

### 2.2 目录结构

```
/root/dev/curious-agent/          ← Curious Agent 安装目录
├── curious_agent.py              ← 主程序（CLI 入口）
├── curious_api.py                ← API 服务（Web UI）
├── core/
│   ├── curiosity_decomposer.py   ← 话题分解引擎（v0.2.3 新增）
│   ├── meta_cognitive_monitor.py ← 元认知监控（v0.2.3 新增）
│   ├── agent_behavior_writer.py  ← 行为写入器（v0.2.3 新增）
│   └── provider_*.py             ← 双 Provider 实现
├── knowledge/
│   └── state.json                ← 探索状态文件
├── logs/                         ← 日志目录
├── memory/curious/               ← 发现存储（sync_discoveries.py 写入）
├── tests/                        ← 320 个测试用例
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

# 4. 确认测试通过
cd /root/dev/curious-agent
python3 -m pytest tests/ --tb=no -q
# 期望: 320 passed

# 5. 确认 API Keys 配置
echo $BOCHA_API_KEY
echo $SERPER_API_KEY
# 两者都应该有值
```

---

## 三、部署步骤

### Step 1：配置环境变量

```bash
# 编辑 ~/.bashrc 或 ~/.zshrc，添加以下环境变量
export BOCHA_API_KEY="your-bocha-api-key"
export SERPER_API_KEY="your-serper-api-key"
export VOLCENGINE_API_KEY="your-volcengine-api-key"  # 用于 LLM

# 使配置生效
source ~/.bashrc
```

**说明**：v0.2.3 需要双 Provider 验证（Bocha + Serper），确保两个 API Key 都已配置。

### Step 2：部署 Curious Agent 后台服务

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
  "uptime_seconds": 3600,
  "version": "v0.2.3"
}
```

### Step 3：配置 OpenClaw 心跳

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

### Step 4：创建/更新 HEARTBEAT.md

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

Curious Agent v0.2.3 提供完整的 REST API，OpenClaw 可以通过 `exec` + `curl` 调用：

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

#### 触发一轮探索（POST）- v0.2.3 修复后

```bash
# v0.2.3 修复：现在可以正确注入指定 topic
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "你的话题", "depth": "medium"}'
```

**说明**：v0.2.3 修复了 Bug #1，现在 `/api/curious/run` 接受 `topic` 参数，会正确探索注入的 topic。

#### 注入新话题（POST）- v0.2.3 支持字符串 depth

```bash
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "metacognitive monitoring",
    "score": 8.5,
    "depth": "medium",  // v0.2.3 支持字符串: shallow/medium/deep
    "reason": "用户研究兴趣"
  }'
```

**说明**：v0.2.3 修复了 Bug #3，`depth` 参数支持字符串 `"shallow"`、`"medium"`、`"deep"`。

#### 查询待探索队列（GET）

```bash
curl http://localhost:4848/api/curious/queue/pending
```

**响应**：
```json
{
  "status": "success",
  "count": 2,
  "items": [
    {"topic": "Metacognitive Monitoring", "score": 8.5, "status": "pending"},
    {"topic": "Predictive Coding", "score": 7.8, "status": "pending"}
  ]
}
```

#### 删除话题（DELETE）- v0.2.3 支持 JSON body

```bash
# v0.2.3 修复：支持 JSON body
curl -X DELETE http://localhost:4848/api/curious/queue \
  -H "Content-Type: application/json" \
  -d '{"topic": "过时话题"}'

# 或继续使用 query parameter
curl -X DELETE "http://localhost:4848/api/curious/queue?topic=过时话题"
```

**说明**：v0.2.3 修复了 Bug #4，DELETE 端点现在支持 JSON body。

#### 查询已完成 topics（GET）- v0.2.3 修复后

```bash
curl http://localhost:4848/api/metacognitive/topics/completed
```

**响应**：
```json
{
  "status": "ok",
  "completed_topics": [
    {"topic": "test_topic", "reason": "Exploration completed", "timestamp": "2026-03-23T10:00:00Z"}
  ]
}
```

**说明**：v0.2.3 修复了 Bug #7，现在 `completed_topics` 会正确记录已完成的探索。

#### 检查 topic 状态（GET）- v0.2.3 修复中文乱码

```bash
# v0.2.3 修复：支持中文 URL 参数
curl "http://localhost:4848/api/metacognitive/check?topic=测试中文"
```

**说明**：v0.2.3 修复了 Bug #6，中文 topic 现在可以正确处理，不会乱码。

#### 完整 API 端点列表

| 方法 | 端点 | 功能 | v0.2.3 更新 |
|------|------|------|-------------|
| GET | `/api/curious/state` | 查询系统状态 | - |
| POST | `/api/curious/run` | 触发一轮探索 | ✅ 修复 Bug #1，支持指定 topic |
| POST | `/api/curious/inject` | 注入新话题 | ✅ 修复 Bug #3，支持字符串 depth |
| POST | `/api/curious/trigger` | 触发特定话题探索 | - |
| DELETE | `/api/curious/queue` | 删除指定话题 | ✅ 修复 Bug #4，支持 JSON body |
| GET | `/api/curious/queue/pending` | 获取待探索队列 | ✅ 修复 Bug #8，所有 topic 都有 status 字段 |
| GET | `/api/metacognitive/check` | 检查 topic 状态 | ✅ 修复 Bug #6，支持中文 |
| GET | `/api/metacognitive/topics/completed` | 获取已完成 topics | ✅ 修复 Bug #7，正确记录完成状态 |
| GET | `/` | Web UI 首页 | - |

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
    print(f'话题: {log[\"topic\"]}')
    print(f'  评分: {log.get(\"score\", \"N/A\")}')
    print(f'  耗时: {log.get(\"duration\", \"N/A\")}s')
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
    print(f'  - {q[\"topic\"]} (评分: {q.get(\"score\", 0)})')
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

## 六、v0.2.3 Bug 修复说明

所有 v0.2.3 的已知 Bug 已修复：

| Bug | 问题 | 修复状态 | 验证命令 |
|-----|------|----------|----------|
| **#1** | Topic 注入后探索了完全不同的 topic | ✅ 已修复 | `curl -X POST .../run -d '{"topic": "测试"}'` |
| **#2** | test shallow 分数 56.0（异常高分） | ✅ 已修复 | 评分公式已归一化，最大值 ~8.0 |
| **#3** | inject API 拒绝字符串 depth | ✅ 已修复 | `curl .../inject -d '{"depth": "medium"}'` |
| **#4** | DELETE queue 不接受 JSON body | ✅ 已修复 | `curl -X DELETE ... -d '{"topic": "xxx"}'` |
| **#6** | 中文 topic URL 参数乱码 | ✅ 已修复 | `curl ".../check?topic=中文"` |
| **#7** | completed_topics 永远为空 | ✅ 已修复 | `curl .../metacognitive/topics/completed` |
| **#8** | KG topic 缺少 status 字段 | ✅ 已修复 | 所有 topic 都有 status 字段 |

**注意**：Bug #5（metacognitive/check URL 编码问题）与 Bug #6 是同一个问题，已一并修复。

---

## 七、验证与测试

### 7.1 验证 Curious Agent 服务

```bash
# 检查 API 是否正常运行
curl http://localhost:4848/api/curious/state

# 检查探索队列
curl http://localhost:4848/api/curious/queue | python3 -m json.tool | head -30

# 运行测试套件
cd /root/dev/curious-agent
python3 -m pytest tests/ --tb=no -q
# 期望: 320 passed
```

### 7.2 验证同步脚本

```bash
# 运行同步脚本
python3 /root/.openclaw/workspace-researcher/scripts/sync_discoveries.py

# 检查文件
ls -la /root/.openclaw/workspace-researcher/memory/curious/
```

### 7.3 验证心跳触发

```bash
# 手动触发一次心跳（立即执行）
openclaw system event --text "Check curiosity" --mode now

# 查看日志
tail -50 /root/.openclaw/logs/agent-*.log
```

### 7.4 Bug 修复验证

```bash
# 验证 Bug #1 修复（Topic 注入）
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "OPENCODE测试专属topic", "depth": "medium"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'topic={d.get(\"topic\")}'); assert d.get('topic') == 'OPENCODE测试专属topic'"

# 验证 Bug #3 修复（字符串 depth）
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic": "测试depth", "depth": "medium"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status') == 'ok'"

# 验证 Bug #4 修复（DELETE JSON body）
curl -X DELETE http://localhost:4848/api/curious/queue \
  -H "Content-Type: application/json" \
  -d '{"topic": "不存在的topic"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status'))"

# 验证 Bug #6 修复（中文 URL）
curl "http://localhost:4848/api/metacognitive/check?topic=测试中文" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); t=d.get('topic',''); assert '测试' in t or '中文' in t, f'BUG: {t}'"

# 验证 Bug #7 修复（completed_topics）
curl http://localhost:4848/api/metacognitive/topics/completed \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'completed count: {len(d.get(\"completed_topics\",[]))}')"
```

### 7.5 端到端测试

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

## 八、故障排查

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

### 问题 5：SERPER_API_KEY 未配置

**错误**：`Provider serper disabled: no API key`

**解决**：
```bash
# 编辑 ~/.bashrc
export SERPER_API_KEY="your-serper-api-key"
source ~/.bashrc

# 重启服务
cd /root/dev/curious-agent
pkill -f curious_api.py
bash run_curious.sh
```

**说明**：v0.2.3 需要双 Provider 验证（Bocha + Serper），确保两个 API Key 都已配置。

---

## 九、高级配置

### 9.1 自定义心跳频率

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

### 9.2 只在特定时段运行

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

### 9.3 配置飞书推送

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

### 9.4 与 Cron 配合使用

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

### 9.5 多用户隔离

若多个 OpenClaw Agent 实例共享 Curious Agent 服务：

```bash
# 为每个用户创建独立端口
PORT=4850 USER_DIR=/home/user2/.openclaw/workspace-researcher bash run_curious.sh
```

对应的 `sync_discoveries.py` 路径也需要调整。

---

## 十、OpenClaw Agent 标准配置（AGENTS.md）

每个接入 Curious Agent 的 OpenClaw Agent 需要在 `AGENTS.md` 中配置以下规则，使其具备**回答前搜索记忆 + 主动触发探索**的能力。

### 10.1 标准 AGENTS.md 配置模板

以下规则应添加到目标 Agent 的 `AGENTS.md` 文件中（位置：在 "External vs Internal" 章节之后）：

```markdown
## Answering Questions

When a user asks a question, **execute in order**:

1. Extract the core topic/keywords from the question
2. Call `memory_search(topic)` — search for relevant memories
3. Wait for the memory_search result
4. Answer based on the result:
   - **Found relevant content** → Answer from memory, start with "From my memory/exploration results..."
   - **No relevant content** → Answer using LLM knowledge, start with "I'm not certain about this (because I haven't memorized it), but based on my LLM knowledge..."
5. **Regardless of result**, trigger Curious Agent to explore this topic
```

### 10.2 配置说明

| 规则步骤 | 说明 |
|---------|------|
| Step 1 | 从用户问题中提取核心 topic/关键词 |
| Step 2 | 调用 OpenClaw 内置 `memory_search` 工具搜索相关记忆 |
| Step 3 | 等待搜索结果返回 |
| Step 4 | 根据结果选择回答方式 |
| Step 5 | 触发 Curious Agent 探索该 topic |

### 10.3 触发探索命令

在 Step 5 中，使用以下命令触发 Curious Agent 探索：

```bash
# 注入 topic 并触发探索（推荐）
cd /root/dev/curious-agent && python3 curious_agent.py --inject "TOPIC_HERE" --score 7.0 --depth 6.0 --reason "用户提问触发"

# 或使用 API 方式
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic": "TOPIC_HERE", "score": 7.0, "depth": "medium", "reason": "用户提问触发"}'
```

### 10.4 预期效果

配置完成后，Agent 将具备以下行为：

| 场景 | 行为 |
|------|------|
| 用户问已有记忆的问题 | 从记忆回答，标注"从我的探索结果来看..." |
| 用户问新问题 | 诚实说"我不确定（因为我没记住），但..."，并触发探索 |
| 探索完成后 | 下次心跳时同步到 memory_search，下次可搜到 |
| 用户再次问同样问题 | 直接从记忆回答 |

### 10.5 验证配置

配置完成后，通过以下方式验证：

```bash
# 1. 确认 AGENTS.md 已更新
grep -A 10 "Answering Questions" /root/.openclaw/workspace-researcher/AGENTS.md

# 2. 测试 memory_search 工具可用
# （在 Agent 会话中尝试调用 memory_search）

# 3. 测试探索触发
cd /root/dev/curious-agent && python3 curious_agent.py --inject "测试配置" --score 5.0 --depth 5.0
```

---

## 十一、文件路径速查

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
| CuriosityDecomposer | `/root/dev/curious-agent/core/curiosity_decomposer.py` | 话题分解引擎 |
| MetaCognitiveMonitor | `/root/dev/curious-agent/core/meta_cognitive_monitor.py` | 元认知监控 |
| AgentBehaviorWriter | `/root/dev/curious-agent/core/agent_behavior_writer.py` | 行为写入器 |

---

## 十二、快速命令汇总

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

# === 运行测试套件 ===
cd /root/dev/curious-agent && python3 -m pytest tests/ --tb=no -q

# === Bug 修复验证 ===
# Bug #1: Topic 注入
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "测试", "depth": "medium"}'

# Bug #3: 字符串 depth
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic": "测试", "depth": "medium"}'

# Bug #4: DELETE JSON body
curl -X DELETE http://localhost:4848/api/curious/queue \
  -H "Content-Type: application/json" \
  -d '{"topic": "测试"}'

# Bug #6: 中文 URL
curl "http://localhost:4848/api/metacognitive/check?topic=中文测试"

# Bug #7: completed_topics
curl http://localhost:4848/api/metacognitive/topics/completed
```

---

## 十三、参考链接

- [OpenClaw 心跳文档](file:///root/.nvm/versions/node/v24.13.1/lib/node_modules/openclaw/docs/gateway/heartbeat.md)
- [OpenClaw Cron vs Heartbeat](file:///root/.nvm/versions/node/v24.13.1/lib/node_modules/openclaw/docs/automation/cron-vs-heartbeat.md)
- [Curious Agent README](file:///root/dev/curious-agent/README.md)
- [Curious Agent Bug List](file:///root/dev/curious-agent/ideas/buglist_v0.2.3.md)
- [Curious Agent Release Notes v0.2.3](file:///root/dev/curious-agent/RELEASE_NOTE_v0.2.3.md)

---

_文档版本：v1.2_
_更新时间：2026-03-24_
_新增：第十章 OpenClaw Agent 标准配置（AGENTS.md）_
_适用：Curious Agent v0.2.3 × OpenClaw 2026.3+_
_测试状态：320 测试全部通过_
