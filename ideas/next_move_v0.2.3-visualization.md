# Curious Agent v0.2.x — 可视化方案设计

> 文档版本：v1.0 | 2026-03-21 | 设计者：R1D3-researcher
> 目标：为 Curious Agent 构建直观、实时的信息流可视化系统

---

## 1. 问题背景

Curious Agent 的信息流是一个**三层结构**：

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: 状态机（CuriosityEngine 的队列状态）         │
│   pending → exploring → completed → blocked        │
├─────────────────────────────────────────────────────┤
│ Layer 2: 知识网络（Knowledge Graph 的图结构）         │
│   topics + relations + confidence scores             │
├─────────────────────────────────────────────────────┤
│ Layer 3: 决策过程（MetaCognitiveMonitor 的评估）     │
│   quality → marginal_return → competence            │
└─────────────────────────────────────────────────────┘
```

**当前问题**：
- 用户无法直观看到 Curious Agent 在做什么
- 探索过程的决策逻辑不透明
- 知识图谱变化不可见

---

## 2. 三层可视化方案

### 2.1 Layer 1 可视化：状态机

**目标**：展示当前探索队列的状态流转

```
┌──────────────────────────────────────────────────────┐
│  🔴 exploring: "metacognition in LLMs" (进度 67%)  │
├──────────────────────────────────────────────────────┤
│  🟡 pending:                                         │
│     1. curiosity-driven RL        [score: 8.2]      │
│     2. agent planning replanning  [score: 7.8]      │
├──────────────────────────────────────────────────────┤
│  🟢 completed: 23 topics                            │
│  ⚫ blocked: 5 topics                                │
└──────────────────────────────────────────────────────┘
```

**实现**：直接读取 `state.json`，每 30s 刷新一次

---

### 2.2 Layer 2 可视化：知识图谱

**目标**：展示探索过程中知识网络的实时变化

**方案 A：文本树状图（轻量，V0.1）**

```
knowledge_graph/
├── metacognition/
│   ├── related_to: [self-reflection, monitoring, confidence]
│   ├── explore_count: 3
│   └── confidence: 0.72
├── curiosity-driven RL/
│   ├── related_to: [ICM, RND, CDE]
│   ├── explore_count: 2
│   └── confidence: 0.65
└── ...
```

**方案 B：图形化（V1.0+）**

- 工具：`pyvis` / `vis.js` / `networkx`
- 节点大小 = explore_count
- 节点颜色 = confidence（绿=高，红=低）
- 边粗细 = 关系强度

---

### 2.3 Layer 3 可视化：决策日志

**目标**：展示 Curious Agent 的"思考过程"

**方案：自然语言探索日志**

```markdown
# 探索日志 2026-03-21

## [20:00] 探索循环 #47 启动
→ 我选择了 "metacognition in LLMs" 作为下一个话题
→ 原因：CompetenceTracker 显示我在这个领域的置信度只有 0.35（低）
→ 预估质量：7.2（基于历史数据）

## [20:01] 探索执行
→ 找到了 3 篇相关论文
→ 发现摘要：Monitor-Generate-Verify 框架...

## [20:02] 质量评估
→ 信息增益评分：8.1（高于阈值 7.0）
→ 触发行为写入：已追加到 curious-agent-behaviors.md
→ 下次遇到复杂推理问题，我会先评估置信度

## [20:03] 能力更新
→ metacognition in LLMs 置信度：0.35 → 0.52
→ 趋势：↑ 上升
```

**优点**：
- 实现成本最低（写文件）
- 用户完全可理解
- 天然支持 memory_search 检索

---

## 3. 分阶段实施计划

### Phase 0（本周可做）：文本日志

```python
# core/exploration_logger.py

class ExplorationLogger:
    """用自然语言记录探索过程"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
    
    def log_exploration_start(self, topic, reason):
        self._write(f"""
{'='*50}
[探索开始] {topic}
  → 选择原因：{reason}
  → 当前时间：{datetime.now().strftime('%H:%M:%S')}
""")
    
    def log_quality_assessment(self, quality, signals):
        self._write(f"""
[质量评估] quality = {quality}
  → 信息增益：{signals.get('semantic_novelty', 'N/A')}
  → 置信度变化：{signals.get('confidence_delta', 'N/A')}
  → 图谱变化：{signals.get('graph_delta', 'N/A')}
""")
    
    def log_behavior_write(self, section, topic):
        self._write(f"""
[行为写入] {topic}
  → 写入分节：{section}
  → curious-agent-behaviors.md 已更新
""")
```

**输出路径**：`logs/exploration-{date}.md`

---

### Phase 1（轻量 Web，1-2周）

**技术栈**：
- 后端：`FastAPI` 读取 `state.json`
- 前端：`HTML + Vanilla JS`（极简）

**功能**：
- 实时刷新状态机
- 知识图谱树状图
- 最新探索日志

**部署**：
```bash
# 启动服务
cd /root/dev/curious-agent
python3 -m uvicorn visualization_server:app --host 0.0.0.0 --port 4850

# 访问
http://10.1.0.13:4850
```

---

### Phase 2（图形化知识图谱，1个月）

**技术栈**：
- 图渲染：`vis.js`（浏览器端）
- 数据流：`FastAPI` WebSocket 推送更新

**功能**：
- 力导向图展示知识网络
- 节点点击查看详情
- 探索过程动画演示

---

## 4. 技术选型参考

| 方案 | 实现成本 | 效果 | 适用阶段 |
|------|---------|------|---------|
| 文本日志 | < 1天 | ⭐⭐ | Phase 0 |
| 终端 UI (rich) | 1-2天 | ⭐⭐⭐ | 开发者版 |
| 简单 Web (HTML+JS) | 1周 | ⭐⭐⭐ | Phase 1 |
| 图形知识图谱 | 2-4周 | ⭐⭐⭐⭐ | Phase 2 |
| LangSmith 集成 | 1周 | ⭐⭐⭐⭐⭐ | production |

---

## 5. 轻量化备选：终端 UI

如果不想部署 Web 服务，可以用 `rich` 库在终端展示：

```python
from rich.console import Console
from rich.table import Table
from rich.live import Live

console = Console()

def render_dashboard(state):
    table = Table(title="Curious Agent Dashboard")
    table.add_column("Status")
    table.add_column("Topic")
    table.add_column("Score")
    
    for item in state["curiosity_queue"]:
        status_icon = "🔴" if item["status"] == "pending" else "🟡"
        table.add_row(status_icon, item["topic"], str(item["score"]))
    
    console.print(table)
```

---

## 6. LangSmith 集成方案（参考）

LangSmith 的 Agent Tracing 是最成熟的方案：

```python
from langsmith import traceable

@traceable(name="curious-agent-exploration")
def run_exploration(topic):
    # 探索逻辑
    result = explorer.explore(topic)
    
    # LangSmith 自动记录：
    # - 输入/输出
    # - Token 消耗
    # - 耗时
    # - 子步骤
    
    return result
```

**优点**：
- 开箱即用
- 支持多框架
- 已有 UI

**缺点**：
- 需要 LangSmith API Key
- 数据不上本地
- 有使用限制

---

## 7. 建议的演进路线

```
V0.1（本周）
  文本日志 → logs/exploration-{date}.md
  用户可以通过 cat 查看探索过程

V0.5（下周）
  终端 UI → 用 rich 库
  实时显示队列状态和探索进度

V1.0（两周后）
  简单 Web → FastAPI + HTML/JS
  部署到 http://10.1.0.13:4850

V2.0（一个月后）
  知识图谱可视化 → vis.js
  图形化展示知识网络变化

V3.0（可选）
  LangSmith 集成 → production 级别 tracing
```

---

## 8. 关键文件变更

| 文件 | 变更 |
|------|------|
| `core/exploration_logger.py` | 新增：自然语言日志模块 |
| `visualization_server.py` | 新增：轻量 Web 服务（Phase 1） |
| `logs/` | 新增目录：存放每日探索日志 |
| `curious_agent.py` | 集成 ExplorationLogger 调用 |

---

## 9. 参考资料

- [LangSmith Observability](https://www.langchain.com/langsmith) — Agent Tracing 成熟方案
- [vis.js](https://visjs.org/) — 浏览器端图形可视化
- [rich](https://github.com/Textualize/rich) — Python 终端 UI 库
- [pyvis](https://pyvis.readthedocs.io/) — Python 网络图可视化
