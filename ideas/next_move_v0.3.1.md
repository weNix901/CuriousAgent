# next_move_v0.3.1.md - CA 全景可视化与外部 Agent 交互观测

> **目标**: 在 CA 侧实现对 5 个 OpenClaw Hook 的调用观测 + CA 内部工作全景可视化 + 外部 Agent ↔ CA 交互完整可追溯
>
> **前置**: v0.3.0 的 5 个 Hook 已定义、API 端点已确认
>
> **日期**: 2026-04-16

---

## 一、当前 5 个 Hook 全景梳理

| # | Hook 名称 | 类型 | 触发事件 | 调用 CA API | 方向 |
|---|-----------|------|----------|-------------|------|
| 1 | `knowledge-query` | Internal | `message:received` | `/api/r1d3/confidence` | R1D3 → CA(查询) |
| 2 | `knowledge-learn` | Internal | `message:sent` | `/api/knowledge/learn` | R1D3 → CA(写入) |
| 3 | `knowledge-bootstrap` | Internal | `agent:bootstrap` | `/api/kg/overview` | R1D3 → CA(查询) |
| 4 | `knowledge-gate` | Plugin SDK | `before_agent_reply` | `/api/knowledge/check` + `/api/kg/confidence` | R1D3 → CA(查询) |
| 5 | `knowledge-inject` | Plugin SDK | `after_tool_call` | `/api/knowledge/record` | R1D3 → CA(写入) |

**观测核心问题**: 当前 Hook 是"单向请求→CA API",CA 侧只知道"有人调了我的 API",但不知道:
- 哪个 Agent 调的?
- 调的哪个 Hook 触发的?
- 传入的原始上下文是什么(用户消息?搜索结果?)?
- Hook 处理后注入了什么到 R1D3 的上下文?
- 调用是否成功?延迟如何?

---

## 二、Phase 0:Hook 调用观测基础设施

### 2.1 Hook Call Audit Log(Hook 调用审计日志)

在 CA API 侧新增一个"Hook 调用审计"机制,所有外部 Hook 请求都经过此中间件:

**数据结构**:

```python
# core/models/hook_audit.py
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional

class HookDirection(Enum):
    INBOUND = "inbound"   # R1D3 → CA
    OUTBOUND = "outbound"  # CA → R1D3 (webhook)

class HookStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"  # 缓存命中或条件不满足跳过

@dataclass
class HookCallRecord:
    id: str                          # UUID
    timestamp: str                   # ISO 8601
    direction: str                   # inbound/outbound
    hook_name: str                   # knowledge-query, knowledge-learn, etc.
    hook_type: str                   # internal / plugin_sdk
    hook_event: str                  # message:received, message:sent, etc.
    agent_id: str                    # R1D3 (未来可接入更多)
    agent_session: str               # OpenClaw session id(从请求头获取)

    # 请求
    endpoint: str                    # /api/r1d3/confidence
    method: str                      # GET/POST
    request_headers: dict            # 脱敏后的请求头
    request_payload: Optional[str]   # 截断到 4KB
    request_raw_topic: str           # 提取的主题词

    # 响应
    status: str                      # success/error/timeout/skipped
    status_code: int                 # HTTP status
    response_payload: Optional[str]  # 截断到 4KB
    latency_ms: int                  # 响应延迟
    error_message: Optional[str]     # 错误信息

    # 语义标记
    confidence_level: Optional[str]  # novice/competent/proficient/expert
    knowledge_injected: bool         # 是否注入了知识到 Agent 上下文
    injection_snippet: Optional[str] # 注入内容的摘要(100字)

    # 关联
    related_topic: Optional[str]     # 关联的 KG 节点
    related_queue_item: Optional[str] # 关联的 queue item ID
    ca_trace_id: Optional[str]       # 如果触发了 CA 内部探索,关联 trace ID
```

**存储**: SQLite(新增 `hook_audit.db`),索引在 `(agent_id, timestamp)` 和 `(hook_name, timestamp)`

### 2.2 Hook 访问日志文件(hook_access.log)

**目的**: 让 main agent 可以直接 `tail` / `grep` 日志判断 Hook 链路是否通了。

**文件位置**: `logs/hook_access.log`(相对于 CA 根目录)

**日志格式**(类 Nginx access log,人眼可读):

```
[2026-04-16 11:30:02.123] knowledge-query   R1D3  session=abc123
  → GET /api/r1d3/confidence?topic=Attention机制
  ← 200 120ms {"confidence": 0.92, "level": "expert"}

[2026-04-16 11:30:15.456] knowledge-gate    R1D3  session=abc123
  → POST /api/knowledge/check
  ← 200 95ms {"success": true, "result": {"status": "found"}}

[2026-04-16 11:30:30.789] knowledge-inject  R1D3  session=def456
  → POST /api/knowledge/record {"topic": "Transformer", "content": "...(200字截断)"}
  ← 201 85ms {"success": true, "node_created": "Transformer"}
```

**每条记录包含**:
- 时间戳(精确到毫秒)
- Hook 名称(knowledge-query / knowledge-learn / knowledge-bootstrap / knowledge-gate / knowledge-inject)
- Agent ID(从 `X-OpenClaw-Agent-Id` Header 提取)
- Session ID(从 `X-OpenClaw-Session-Id` Header 提取)
- 请求方法 + 端点 + 查询参数
- 请求体摘要(截断到 200 字)
- 响应状态码 + 延迟(毫秒)
- 响应体摘要(截断到 200 字)

**实现**: 在 `curious_api.py` 的 Flask `after_request` 钩子中,只针对 6 个 Hook 端点写日志(见 2.6 端点清单),异步追加到文件。

**Main agent 使用方式**:
```bash
# 检查最近调用
tail -50 /root/dev/curious-agent/logs/hook_access.log

# 只看某个 Hook
grep knowledge-query /root/dev/curious-agent/logs/hook_access.log

# 测试中实时监控
tail -f /root/dev/curious-agent/logs/hook_access.log
```

### 2.3 CA API 中间件

```python
# core/api/hook_audit_middleware.py
```

**实现方式**: Flask `after_request` 钩子 + 白名单匹配
- **只针对 6 个 Hook 端点**拦截(见 2.6 清单),不拦截其他 40+ 个 CA 内部端点
- 从 `X-OpenClaw-Agent-Id` 请求头识别 Agent 身份
- 从 `X-OpenClaw-Hook-Name` 请求头识别 Hook 来源
- 双写：追加到 `logs/hook_access.log` + 写入 SQLite 审计库
- 同步写入（v0.3.1 先简单实现，每条 Hook 请求增加 <1ms 延迟）
  - 如果后期延迟成问题，改用 Python queue + 后台线程异步写入

### 2.4 Hook 侧改造(5 个 Hook 都需要加 Header)

每个 Hook 的 handler.ts 在 fetch CA API 时,注入标准 Header:

```typescript
const headers = {
  "Content-Type": "application/json",
  "X-OpenClaw-Agent-Id": "r1d3",
  "X-OpenClaw-Session-Id": env.OPENCLAW_SESSION_ID || "unknown",
  "X-OpenClaw-Hook-Name": "knowledge-query",  // 每个 Hook 不同
  "X-OpenClaw-Hook-Event": "message:received",
  "X-OpenClaw-Hook-Type": "internal",          // 或 "plugin_sdk"
};
```

### 2.5 Webhook 推送审计(CA → R1D3)

CA 主动往 R1D3 推送时(未来 webhook 机制),同样记录:

```python
@dataclass
class WebhookRecord:
    id: str
    timestamp: str
    target_agent: str          # R1D3
    webhook_type: str          # discovery_ready, queue_injected, etc.
    payload: str               # 截断到 4KB
    delivery_status: str       # delivered/failed/retry
    response_code: Optional[int]
    retry_count: int
```

### 2.6 新增 API 端点(仅审计查询端点,Hook 调用的 6 个端点已存在)

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/audit/hooks` | GET | 查询 Hook 调用记录(分页、过滤) |
| `/api/audit/hooks/<id>` | GET | 单条 Hook 调用详情 |
| `/api/audit/hooks/stats` | GET | Hook 调用统计(按 Hook/按 Agent) |
| `/api/audit/webhooks` | GET | Webhook 推送记录 |
| `/api/audit/agent/<agent_id>/activity` | GET | 某 Agent 的完整活动轨迹 |

**Hook 实际调用的 6 个端点**(已在 `curious_api.py` 实现,无需新增):

| # | 端点 | 方法 | 调用方 Hook |
|---|------|------|-------------|
| 1 | `/api/r1d3/confidence` | GET | knowledge-query |
| 2 | `/api/knowledge/learn` | POST | knowledge-learn |
| 3 | `/api/kg/overview` | GET | knowledge-bootstrap |
| 4 | `/api/knowledge/check` | POST | knowledge-gate |
| 5 | `/api/kg/confidence/<topic>` | GET | knowledge-gate |
| 6 | `/api/knowledge/record` | POST | knowledge-inject |

---

## 三、Phase 1:CA 内部工作全景可视化

### 3.1 Queue 可视化

**需求**: 完整展示 curiosity queue 的状态,每个 topic 可点击查看详情

**新增 API**:
```
GET /api/queue/list?status=pending&limit=50    → 列出队列项
GET /api/queue/<item_id>                        → 单个 queue item 详情
GET /api/queue/stats                            → 队列统计(各状态计数)
GET /api/queue/by-topic/<topic>                 → 按 topic 查相关 queue item
```

**Queue Item 详情字段**:
- topic, score, depth, status, lineage (parent chain)
- created_at, claimed_at, completed_at
- claimed_by (哪个 SpiderAgent / 进程)
- exploration_result 摘要(探索完才有)
- decompose_level(1-4,四级分解层级)

**UI 呈现**:
- Tab 页 "Queue",分栏展示:Pending / Exploring / Done / Failed
- 每个 item 可点击展开详情 modal
- 支持按 score 排序、按 topic 搜索、按 status 过滤
- 实时刷新(5s 轮询)

### 3.2 KG 完整可视化

**当前状态**: 已有 D3 力导向图,但信息量不足

**增强方案**:

**新增 API**:
```
GET /api/kg/nodes?page=1&limit=100&search=xxx&type=xxx    → 节点列表
GET /api/kg/nodes/<node_id>                                → 单节点完整详情
GET /api/kg/edges?node=<node_id>                           → 某节点的关联边
GET /api/kg/subgraph?root=<topic>&depth=3                  → 子图(指定深度)
GET /api/kg/stats                                          → KG 统计
GET /api/kg/quality-distribution                           → 质量分布
```

**单节点详情字段**:
- name, type (root/decomposed/learned/dreamt)
- confidence (0-1), quality_score, exploration_count
- parent, children[](完整关系链)
- created_at, updated_at, last_explored_at
- assertions[](知识断言列表)
- sources[](探索来源 URL)
- decomposition_path(如果是分解节点,展示从根到它的路径)
- provider_heatmap(哪些 Provider 验证过它)

**UI 增强**:
- 图谱视图增加节点搜索(模糊匹配 topic 名)
- 点击节点弹出详情 panel(右侧滑出,不是 modal)
- 支持子图展开:点击节点 → 加载 depth=2 的子图
- 支持"高亮路径":选两个节点,高亮它们之间的最短路径
- 质量分布热力条:顶部显示 high/medium/low quality 比例
- 节点类型图例增强(root/decomposed/learned/dreamt 不同形状)

### 3.3 Explorer Agent 实时可视化

**需求**: 实时展示 Explorer Agent 的探索进度,让"AI 在做什么"一目了然

**实现方案**: 在 ExploreAgent `_react_loop` 中注入 TraceWriter

```python
# core/trace/explorer_trace.py
@dataclass
class TraceStep:
    step_id: str
    trace_id: str
    step_num: int            # 1, 2, 3...
    timestamp: str
    action: str              # "search_web" / "fetch_page" / "query_kg" / ...
    action_input: str        # JSON 截断到 500 字
    output_summary: str      # 截断到 300 字
    output_size: int         # 原始输出字节数
    duration_ms: int         # 该步骤耗时
    llm_call: bool           # 是否调用了 LLM
    llm_tokens: Optional[int] # LLM token 消耗

@dataclass
class ExplorerTrace:
    trace_id: str
    topic: str
    queue_item_id: str
    started_at: str
    finished_at: Optional[str]
    status: str              # running / done / failed
    total_steps: int         # ReAct 循环执行次数
    steps_completed: int     # 已完成步骤数
    tools_used: list         # ["search_web", "fetch_page", "add_to_kg", ...]
    kg_nodes_created: list   # ["Attention机制", "Transformer架构", ...]
    quality_score: Optional[float]
    error: Optional[str]
```

**注入点**: `core/agents/explore_agent.py` 的 `_execute_action` 方法

```python
# explore_agent.py _execute_action 方法中注入
async def _execute_action(self, action, action_input):
    step_start = time.time()

    # 记录 trace step
    self.trace_writer.record_step(
        trace_id=self.current_trace_id,
        step_num=self.current_step_num,
        action=action,
        action_input=truncate_json(action_input, 500),
    )

    # 执行原始工具调用
    result = await tool.execute(**action_input)

    duration_ms = int((time.time() - step_start) * 1000)

    # 更新 trace step
    self.trace_writer.update_step(
        output_summary=truncate(result, 300),
        output_size=len(result),
        duration_ms=duration_ms,
    )

    return result
```

**存储**: SQLite `traces.db`,两张表 `explorer_traces` + `trace_steps`

**新增 API**:
```
GET /api/explorer/active              → 正在进行的探索
GET /api/explorer/recent?limit=20     → 最近完成的探索
GET /api/explorer/trace/<trace_id>    → 单次探索完整 trace(含所有步骤)
```

**UI 呈现**(内部可视化 Tab 顶部,上下布局):
- 上半部分:Explorer Agent 实时活动流
- 左侧:实时活动流(类似 Git log),每条探索记录一行:
  ```
  🔍 [正在] Attention机制 | 7 steps | search_web→fetch_page→... | 45s
  ✅ [完成] Transformer架构 | 10 steps | quality:7.2 | 3 nodes | 1m23s
  ❌ [失败] 量子计算优化 | 3 steps | error: timeout | 12s
  ```
- 点击任意探索记录 → 右侧展开详细 trace:
  - 每一步的动作/工具/输入摘要/输出摘要/耗时
  - LLM 调用标识和 token 消耗
  - 创建的 KG 节点
  - 质量评分和置信度
  - 时间线可视化

### 3.4 Dream Agent 可视化

**需求**: Dream Agent 在后台"做梦"时做了什么加工

**实现方案**: Dream Agent 已有 L1-L4 线性管道结构,在每个阶段注入计时和候选追踪

```python
# core/trace/dream_trace.py
@dataclass
class DreamTrace:
    trace_id: str
    started_at: str
    finished_at: Optional[str]
    status: str                  # running / done / failed

    # L1-L4 各阶段结果
    l1_candidates: list          # L1 light sleep: 候选话题列表
    l1_count: int
    l1_duration_ms: int

    l2_scored: list              # L2 deep sleep: 带 6 维评分的候选
    l2_count: int
    l2_duration_ms: int

    l3_filtered: list            # L3 filtering: 通过阈值的候选
    l3_count: int
    l3_duration_ms: int

    l4_topics: list              # L4 rem sleep: 最终生成的话题
    l4_count: int
    l4_duration_ms: int

    # 产出洞察
    insights_generated: list     # [{id, type, source_topics, confidence}, ...]
    total_duration_ms: int
    error: Optional[str]
```

**注入点**: `core/agents/dream_agent.py` 的 `run` 方法和 L1-L4 四个方法

```python
# dream_agent.py run 方法中注入
def run(self, input_data: str = "") -> DreamResult:
    trace = DreamTrace(trace_id=str(uuid.uuid4()), started_at=now())
    self.dream_trace_writer.start(trace)

    candidates = self._l1_light_sleep()     # 记录候选数和耗时
    scored = self._l2_deep_sleep(candidates) # 记录评分结果
    filtered = self._l3_filtering(scored)    # 记录通过数
    topics = self._l4_rem_sleep(filtered)    # 记录生成话题和洞察

    trace.finished_at = now()
    trace.status = "done"
    self.dream_trace_writer.finish(trace)

    return DreamResult(...)
```

**现有洞察文件兼容**: `knowledge/dream_insights/*.json` 已包含 `source_topics`、`insight_type`、`created_at` 等字段,直接读取即可,无需迁移。

**存储**: SQLite `traces.db` 新增 `dream_traces` 表;insight 内容从 `knowledge/dream_insights/` JSON 文件读取

**新增 API**:
```
GET /api/dream/active               → 当前正在做梦(如果有)
GET /api/dream/traces?limit=20      → 最近 Dream 运行记录
GET /api/dream/trace/<trace_id>     → 单次 Dream 完整 trace(L1-L4 各阶段详情)
GET /api/dream/insights?limit=20    → 最近洞察(从 JSON 文件读取)
GET /api/dream/insight/<id>         → 单条洞察详情
GET /api/dream/stats                → 做梦统计
```

**UI 呈现**(内部可视化 Tab 上半部分,Explorer 下方):
- 卡片式展示最近洞察,按 insight_type 分组着色
- 点击卡片 → 显示 L1-L4 完整链路:
  ```
  L1 light sleep: 47 候选 (120ms)
  L2 deep sleep:  47 → 12 评分 (350ms)
  L3 filtering:   12 → 3 通过阈值 (80ms)
  L4 rem sleep:   3 话题 → 2 洞察 (1.2s)
  ```
- 统计面板:今天跑了多少次 Dream、各阶段平均耗时、洞察产出趋势

### 3.5 Decomposition 可视化(补充)

**需求**: 四级分解引擎的可视化--树状展示好奇心的分解过程

**新增 API**:
```
GET /api/decomposition/tree/<root_topic>   → 分解树
GET /api/decomposition/stats               → 分解统计
```

**UI 呈现**:
- Tab 页 "Decomposition"
- 树状图(tree layout)展示每个 root topic 如何分解为 4 级 sub-topics
- 节点颜色表示状态:已探索/探索中/待探索/已跳过
- 点击子节点 → 右侧显示该节点的探索详情

### 3.6 System Health 面板(补充)

**需求**: 系统健康状态一目了然

**新增 API**:
```
GET /api/system/health
```

**展示内容**:
- CA API 状态(up/down)+ 运行时长
- 各进程状态(Daemon, API, SpiderAgent)
- 内存/CPU 使用率
- LLM Provider 状态(bocha/serper 配额剩余)
- KG 存储状态(JSON/Neo4j)
- 队列积压情况
- 最近错误(最近 10 条 error log)

### 3.7 Event Timeline(补充)

**需求**: 全局事件时间线,类似 Git log,记录 CA 系统内所有重要事件

**数据来源**:
- 事件总线(event_bus)持久化
- Hook 调用记录
- Explorer trace
- Dream insight 产出
- Queue 状态变更

**UI 呈现**:
- Tab 页 "Timeline"
- 统一时间线,带事件类型过滤:
  - 🔍 探索开始/完成
  - 💤 洞察产出
  - 📥 Queue 注入(手动/API/Hook)
  - 🔗 Hook 调用
  - ⚠️ 系统错误
  - 🌱 分解产生
- 点击事件 → 详情

### 3.8 Provider Heatmap 可视化(补充)

**需求**: 当前已有 `provider_heatmap.py`,但只在内存中。可视化它。

**UI 呈现**:
- Tab 页 "Providers"
- 热力矩阵:行=topic 类型,列=Provider,值=覆盖数
- 推断各 Provider 能力边界
- 配额消耗进度条

---

## 四、Phase 2:外部 Agent ↔ CA 交互可视化

### 4.1 Agent Registry

**需求**: 管理已接入的外部 Agent

**数据结构**:
```python
@dataclass
class AgentRecord:
    agent_id: str              # R1D3
    agent_name: str            # R1D3 Researcher
    connected_at: str
    last_seen_at: str
    hooks_used: list           # ["knowledge-query", "knowledge-inject", ...]
    total_calls: int           # 总调用次数
    success_rate: float        # 成功率
    avg_latency_ms: int        # 平均延迟
    webhook_status: str        # connected/disconnected
    metadata: dict             # 版本、配置等
```

**新增 API**:
```
GET /api/agents              → 已接入 Agent 列表
GET /api/agents/<agent_id>   → Agent 详情
```

### 4.2 Hook 调用看板

**UI 呈现**:
- Tab 页 "Hooks"
- 5 个 Hook 的卡片式仪表盘:

```
┌─────────────────────────────────────────────────┐
│ 🧠 knowledge-query  (message:received)           │
│ ─────────────────────────────────────────────── │
│ 今日调用: 42    成功率: 98%    平均延迟: 120ms   │
│ ┌─────────────────────────────────────────────┐ │
│ │ 11:15 R1D3 confidence=expert "Attention机制" │ │
│ │ 11:14 R1D3 confidence=novice  "量子纠缠"     │ │
│ │ 11:10 R1D3 confidence=proficient "GRPO算法"  │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

- 点击任意调用记录 → 弹出完整审计详情(request + response + 处理逻辑)
- 支持按 Hook 过滤、按 Agent 过滤、按时间范围过滤
- 错误率红色告警

### 4.3 Agent 活动轨迹

**UI 呈现**:
- Tab 页 "Agents"
- 选择 Agent → 显示该 Agent 的完整活动轨迹:

```
R1D3 Activity Timeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
11:15:02 📥 knowledge-query → /api/r1d3/confidence → expert ✅
11:15:02   请求: {"topic": "Attention机制"}
11:15:02   响应: {"confidence": 0.92, "level": "expert"}
           注入: "Attention核心是QKV计算,FlashAttention优化..."

11:14:30 📥 knowledge-inject → /api/knowledge/record → success ✅
11:14:30   请求: {"topic": "Transformer架构", "content": "..."}
11:14:30   响应: {"success": true, "node_created": "Transformer架构"}
           关联: 已链接到 "Attention机制" 节点
```

### 4.4 Webhook 推送监控(预留)

**需求**: 未来 CA 主动推送内容给 R1D3 时,监控推送状态

**推送场景(未来)**:
- 探索完成 → 推送 `discovery_ready` 给 R1D3
- 发现低置信度 → 推送 `confidence_alert` 给 R1D3
- 新知识产出 → 推送 `knowledge_update` 给 R1D3

**UI 呈现**:
- 在 Hook 看板中增加 "Outbound" 区域
- 显示推送列表:时间、类型、目标 Agent、状态、重试次数
- 失败可手动重发

### 4.5 API 健康 Dashboard(补充)

**需求**: 从 Agent 视角看 CA API 是否健康

**展示内容**:
- 每个 Agent 的最后 100 次调用成功率
- 延迟分布(P50/P95/P99)
- 各端点调用热度(哪个 API 最常被调用)
- 异常告警(连续失败、超时等)

### 4.6 Session Context 可视化(补充)

**需求**: 对于每个 OpenClaw Session,展示 CA 在该 Session 中注入了什么知识

**新增 API**:
```
GET /api/audit/sessions/<session_id>   → Session 内所有 Hook 调用
```

**UI 呈现**:
- 在 Hook 看板中可按 Session 过滤
- 展示一个 Session 的生命周期:
  ```
  Session: abc123 (2026-04-16 11:00)
  ├── 📚 bootstrap → 注入 3 条高价值知识摘要
  ├── 🧠 query("Attention机制") → expert → 注入 QKV 解释
  ├── 💉 inject("Transformer") → 记录到 KG
  ├── 🚦 gate("Attention机制") → check=found → 注入额外 context
  └── 🔍 learn("FlashAttention") → 注入探索队列
  ```

---

## 五、Phase 3:WebUI 增强实现方案

### 5.1 新 Tab 结构

当前 WebUI 已有 2 个 Tab(列表视图 / 图谱视图),v0.3.1 新增 2 个 Tab:

| Tab | 图标 | 内容 |
|-----|------|------|
| ~~列表视图~~(保留现有) | 📋 | 现有发现列表(不变) |
| ~~图谱视图~~(保留现有) | 🔮 | 现有 KG 图谱(不变) |
| **内部可视化**(新增) | 🖥️ | 首页直接展示 **Explorer Agent 实时追踪** + **Dream Agent 洞察** 两大面板(上下布局),下方为 Queue / KG 节点详情 / Decomposition / 系统健康 等辅助面板,无需导航切换 |
| **外部 Agent 交互**(新增) | 🔗 | Hook 调用看板 + Agent 活动轨迹 + Session Context + Webhook 监控 |

### 5.2 技术选型

**前端**: 继续使用纯 HTML/CSS/JS(无框架),新增 D3 图表
- 列表/树状图: D3 v7(已引入)
- 实时流: Server-Sent Events (SSE) 或轮询
- 图表: 复用 D3

**后端**: 在 `curious_api.py` 中新增端点
- Phase 0: 新增约 6 个审计查询端点 + `logs/hook_access.log` 文件日志
- Phase 1: 新增约 20 个内部可视化端点
- Phase 2: 新增约 3 个外部 Agent 交互端点
- SQLite 新增 `hook_audit.db`
- 事件总线增加 Hook 事件类型
- `Flask.after_request` 钩子实现 Hook 端点日志追加

**实时方案**:
- 轻量轮询(5s interval)→ 满足大部分场景
- SSE(可选)→ Explorer 实时进度

### 5.3 新增 API 端点清单

**Phase 0 新增(审计查询端点)**:
```
# Audit / Hook 调用查询
GET /api/audit/hooks
GET /api/audit/hooks/<id>
GET /api/audit/hooks/stats
GET /api/audit/webhooks
GET /api/audit/agent/<agent_id>/activity
GET /api/audit/sessions/<session_id>
```

**Hook 实际调用的端点**(`curious_api.py` 已实现,无需新增):
| 端点 | 方法 | Hook |
|------|------|------|
| `/api/r1d3/confidence` | GET | knowledge-query |
| `/api/knowledge/learn` | POST | knowledge-learn |
| `/api/kg/overview` | GET | knowledge-bootstrap |
| `/api/knowledge/check` | POST | knowledge-gate |
| `/api/kg/confidence/<topic>` | GET | knowledge-gate |
| `/api/knowledge/record` | POST | knowledge-inject |

**Phase 1 新增(内部可视化端点)**:
```
# Queue
GET /api/queue/list
GET /api/queue/<item_id>
GET /api/queue/stats
GET /api/queue/by-topic/<topic>

# KG 增强
GET /api/kg/nodes
GET /api/kg/nodes/<node_id>
GET /api/kg/edges
GET /api/kg/subgraph
GET /api/kg/quality-distribution

# Explorer
GET /api/explorer/active
GET /api/explorer/recent
GET /api/explorer/trace/<trace_id>

# Dream
GET /api/dream/active
GET /api/dream/insights
GET /api/dream/insight/<id>
GET /api/dream/stats

# Decomposition
GET /api/decomposition/tree/<root_topic>
GET /api/decomposition/stats

# System
GET /api/system/health
GET /api/providers/heatmap
```

**Phase 2 新增(外部 Agent 交互端点)**:
```
GET /api/agents
GET /api/agents/<agent_id>
```

### 5.4 开发顺序

```
Phase 0(1天): Hook 审计基础设施
  ├── hook_audit.py 数据模型
  ├── hook_audit_middleware.py 中间件
  │   └── 只拦截 6 个 Hook 端点(不通配整个路径前缀):
  │       1. GET  /api/r1d3/confidence     ← knowledge-query
  │       2. POST /api/knowledge/learn     ← knowledge-learn
  │       3. GET  /api/kg/overview         ← knowledge-bootstrap
  │       4. POST /api/knowledge/check     ← knowledge-gate
  │       5. GET  /api/kg/confidence/<t>   ← knowledge-gate
  │       6. POST /api/knowledge/record    ← knowledge-inject
  ├── 5 个 Hook 加标准 Header
  ├── logs/hook_access.log 文件日志(Flask after_request 钩子,人眼可读)
  ├── SQLite hook_audit.db 结构化存储(WebUI 用)
  ├── /api/audit/* 查询端点
  └── hook_audit.db + logs/ 目录初始化

Phase 1(3天): 内部可视化
  ├── Day 1: Queue 可视化 + API + TraceWriter 基础设施
  │   ├── traces.db (explorer_traces + trace_steps + dream_traces 表)
  │   ├── TraceWriter 基类
  │   ├── ExplorerAgent _execute_action 注入 trace
  │   └── DreamAgent L1-L4 注入 trace
  ├── Day 2: Explorer Agent 追踪 UI + Dream Agent 可视化 UI
  │   ├── Explorer 实时活动流
  │   ├── Dream L1-L4 链路展示
  │   └── insight 详情面板(从 JSON 文件读取)
  ├── Day 3: KG 增强 + Decomposition 树 + System Health + Event Timeline

Phase 2(2天): 外部 Agent 交互可视化
  ├── Day 1: Agent Registry + Hook 看板
  ├── Day 1: Agent 活动轨迹
  └── Day 2: Session Context + Webhook 监控

Phase 3(1天): WebUI 集成
  ├── Tab 重构(现有 2 个 + 新增 2 个 = 4 个 Tab)
  ├── 内部可视化 Tab:
  │   ├── 顶部:Explorer Agent 实时追踪 + Dream Agent 洞察(上下布局,直接可见)
  │   └── 下方:Queue / KG 详情 / Decomposition / 系统健康(可折叠分区)
  ├── 外部交互 Tab:Hook 看板 + Agent 轨迹
  └── 实时刷新优化
```

---

## 六、验收标准

### 6.1 Hook 观测

- [ ] 5 个 Hook 的每次调用都被记录到 `hook_audit.db`
- [ ] `logs/hook_access.log` 文件实时更新,main agent 可 `tail` 查看
- [ ] 日志格式人眼可读,包含 Hook 名称/Agent ID/请求摘要/响应摘要/延迟
- [ ] WebUI 中可以看到每次 Hook 调用的 request/response 内容
- [ ] 可以按 Hook 名称、Agent、时间范围过滤
- [ ] Hook 调用统计(成功率、延迟)实时更新

### 6.2 内部可视化

- [ ] Queue 页面展示所有状态项,可搜索/过滤/点击详情
- [ ] Explorer Agent 每次探索自动记录 trace,WebUI 可看到每一步动作
- [ ] Explorer trace 包含:工具调用、输入摘要、输出摘要、耗时、LLM token
- [ ] Dream Agent 每次运行记录 L1-L4 各阶段结果,WebUI 可看到完整链路
- [ ] Dream insight 可从 JSON 文件读取,显示来源话题和洞察内容
- [ ] KG 图谱支持节点搜索、详情面板、子图展开、路径高亮
- [ ] Decomposition 页面展示树状分解图
- [ ] System 页面展示进程状态/配额/错误
- [ ] traces.db 存储: explorer_traces + trace_steps + dream_traces 三张表

### 6.3 外部 Agent 交互

- [ ] Hook 看板展示 5 个 Hook 的调用统计和最近记录
- [ ] Agent 页面展示 R1D3 的完整活动轨迹
- [ ] Session Context 展示单个 Session 内 CA 注入知识的完整链路
- [ ] API 健康 Dashboard 展示各端点调用热度和成功率

---

## 七、未来扩展(v0.3.2+)

1. **多 Agent 支持**: 接入更多外部 Agent(非仅 R1D3)
2. **Webhook 推送**: CA 主动向 R1D3 推送发现/告警
3. **实时 WebSocket**: Explorer 进度实时推送到 WebUI(非轮询)
4. **知识演化追踪**: 同一 topic 随时间的置信度变化曲线
5. **Agent 行为分析**: 基于 Hook 调用模式分析 Agent 行为特征
6. **导出能力**: 导出 Hook 调用日志为 CSV/JSON
7. **告警通知**: Hook 连续失败时通过 R1D3 通知用户
