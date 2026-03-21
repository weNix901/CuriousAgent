# Curious Agent v0.2.2 — Next Move

> 为 OpenCode 提供实现路径参考
> 创建时间：2026-03-21 | 设计者：R1D3-researcher + weNix

---

## 一、核心问题（v0.2.1 生产环境证据）

```
最近 10 次探索日志：
  Topic: "Embodied Generative Cognitive"
  触发: 00:00 → 00:30 → 01:00 → ... → 04:00（连续10次）
  notified_user: 全部 false
  exploration_depth / layers_explored: 全部 N/A
  
结论：同一话题被无意义重复探索 10 次，无任何新发现。
```

| 问题 | 表现 | 根因 |
|------|------|------|
| **无限循环** | 同一话题被探索 10+ 次 | 缺乏"已达上限"检查 |
| **价值缺失** | 60 次探索，0 次通知用户 | 缺乏探索质量评估 |

---

## 二、OpenCode 移交状态

| 内容 | 状态 | 位置 |
|------|------|------|
| 设计文档 | ✅ 完整 | `docs/plans/2026-03-21-v0.2.2-metacognitive-monitor-design.md` |
| 核心 .py 模块 | ❌ 未实现 | 需 OpenCode 开发 |
| API 端点 | ❌ 未实现 | 需 OpenCode 开发 |
| Web UI 区域 | ❌ 未实现 | 需 OpenCode 开发 |

---

## 三、推荐实现路径（按依赖排序）

> **核心原则**：按依赖关系线性推进，避免来回返工

```
Step 1           Step 2           Step 3           Step 4           Step 5           Step 6
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│Knowl-    │     │ Meta-   │     │ Meta-   │     │ 集成    │     │  API    │     │ Web UI  │
│edgeGraph │ ──▶ │Cognitive│ ──▶ │Cognitive│ ──▶ │ MGV     │ ──▶ │ 端点    │ ──▶ │ 元认知  │
│扩展      │     │Monitor  │     │Controller│     │ 循环    │     │         │     │ 区域    │
│          │     │         │     │         │     │         │     │         │     │         │
│state.json│     │纯监测   │     │纯决策   │     │curious_ │     │3个端点  │     │状态+历史│
│扩展字段  │     │9个方法  │     │3个决策  │     │agent.py │     │+Web UI  │     │+质量分布│
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
     │               │               │               │
     └───────────────┴───────────────┴───────────────┘
                    依赖关系
```

### Step 1: KnowledgeGraph 扩展（state.json 持久化）

**文件**：`core/knowledge_graph.py`

**目标**：为 `meta_cognitive` 字段提供读写支持

**新增方法**：

```python
# 1. 新增字段初始化（load 时自动）
def _ensure_meta_cognitive(self, state: dict) -> dict:
    """确保 state.json 包含 meta_cognitive 字段"""
    if "meta_cognitive" not in state:
        state["meta_cognitive"] = {
            "explore_counts": {},
            "marginal_returns": {},
            "last_quality": {},
            "exploration_log": []
        }
    return state

# 2. 新增 mark_topic_done(topic, reason)
def mark_topic_done(self, topic: str, reason: str):
    """标记话题为已完成，阻止后续探索"""
    # 在 topics[topic]["done_reason"] 写入原因
    # 可选原因: "max_explore_count" | "marginal_return_too_low"

# 3. 新增 update_last_exploration_notified(topic, notified)
def update_last_exploration_notified(self, topic: str, notified: bool):
    """更新最近一次探索的 notified 标记"""
    # 在 exploration_log 最后一条记录中更新 notified_user

# 4. 修改 save_state() — 保留 meta_cognitive 字段
def save_state(self, state: dict):
    """保存时确保 meta_cognitive 不丢失"""
```

**验证**：加载现有 `state.json` 时能自动初始化空 `meta_cognitive`，不影响现有数据

---

### Step 2: MetaCognitiveMonitor（纯监测模块）

**文件**：`core/meta_cognitive_monitor.py`

**依赖**：Step 1（需要 KnowledgeGraph 的 `meta_cognitive` 读写能力）

**核心方法（9个）：

```python
class MetaCognitiveMonitor:
    def __init__(self, kg: KnowledgeGraph): ...

    # 只读查询（无副作用）
    def get_explore_count(self, topic: str) -> int: ...
    def get_marginal_returns(self, topic: str) -> list[float]: ...
    def get_last_quality(self, topic: str) -> float: ...

    # 评估（无副作用）
    def assess_exploration_quality(self, topic: str, findings: dict) -> float:
        """
        三维质量评分（0-10）：
        - new_discovery_rate × 0.4（关键词新增率）
        - depth_improvement × 0.3（理解深度提升）
        - user_relevance × 0.3（与用户兴趣相关性）
        """
    def compute_marginal_return(self, topic: str, current_quality: float) -> float:
        """
        边际收益 = current_quality - previous_quality
        首次探索默认返回 1.0
        """
        prev = self.get_last_quality(topic)
        return current_quality - prev if prev > 0 else 1.0

    # 写入（有副作用）
    def record_exploration(self, topic: str, quality: float,
                           marginal_return: float, notified: bool):
        """写入 meta_cognitive 到 state.json"""
        # 1. explore_counts[topic] += 1
        # 2. marginal_returns[topic].append(marginal_return)
        # 3. last_quality[topic] = quality
        # 4. exploration_log 追加记录
```

**边界处理**：
| 场景 | 处理 |
|------|------|
| 话题不存在 | `get_explore_count` → 0 |
| 无历史质量 | `compute_marginal_return` → 1.0 |
| `assess_exploration_quality` 失败 | 返回 5.0（默认中等） |
| `record_exploration` 失败 | 抛出异常 |

---

### Step 3: MetaCognitiveController（纯决策模块）

**文件**：`core/meta_cognitive_controller.py`

**依赖**：Step 2（完全依赖 Monitor 的输出，不直接访问 KnowledgeGraph）

**核心方法（3个）：

```python
class MetaCognitiveController:
    def __init__(self, monitor: MetaCognitiveMonitor, config: dict = None):
        # 可通过 config 覆盖默认值
        self.thresholds = {
            "max_explore_count": 3,
            "min_marginal_return": 0.3,
            "high_quality_threshold": 7.0,
        }
        self.thresholds.update(config.get("thresholds", {}))

    def should_explore(self, topic: str) -> tuple[bool, str]:
        """探索前检查：是否可以开始探索"""
        # 1. explore_count >= max → 阻止
        # 2. 连续 2 次 marginal_return < min → 阻止

    def should_continue(self, topic: str) -> tuple[bool, str]:
        """探索后检查：同一话题是否继续探索"""
        # 基于边际收益趋势判断

    def should_notify(self, topic: str) -> tuple[bool, str]:
        """探索后检查：是否通知用户"""
        # quality >= high_quality_threshold → 通知
```

**决策真值表**：

| 探索次数 | 边际收益趋势 | 质量分 | should_explore | should_continue | should_notify |
|---------|------------|--------|---------------|----------------|--------------|
| 0 | — | — | ✅ | — | — |
| 1 | 高(0.9) | 8.0 | ✅ | ✅ | ✅ 通知 |
| 2 | 低(0.1) | 6.0 | ✅ | ❌ 停止 | ❌ 不通知 |
| 3 | -0.2 | 4.0 | ❌ 阻止 | ❌ 停止 | ❌ 不通知 |
| 4+ | 任意 | 任意 | ❌ 阻止 | ❌ 停止 | ❌ 不通知 |

---

### Step 4: 集成到 CuriousAgent（Monitor-Generate-Verify 循环）

**文件**：`curious_agent.py`

**依赖**：Step 1 + Step 2 + Step 3

**修改 `run_one_cycle()` 的伪代码：

```python
def run_one_cycle(self, topic: str):
    # === Monitor 阶段 ===
    monitor = MetaCognitiveMonitor(self.kg)
    controller = MetaCognitiveController(monitor)

    # 探索前检查
    allowed, reason = controller.should_explore(topic)
    if not allowed:
        logger.info(f"探索被阻止: {topic} — {reason}")
        self.kg.mark_topic_done(topic, reason)
        return

    # === Generate 阶段 ===
    explorer = Explorer(exploration_depth=self.depth)
    findings = explorer.explore(topic)

    # === Monitor 评估 ===
    quality = monitor.assess_exploration_quality(topic, findings)
    marginal = monitor.compute_marginal_return(topic, quality)
    monitor.record_exploration(topic, quality, marginal, notified=False)

    # === Verify 阶段 ===
    should_notify, notify_reason = controller.should_notify(topic)
    if should_notify:
        self.notify_user(topic, findings, quality)
        self.kg.update_last_exploration_notified(topic, True)

    # 继续决策
    continue_allowed, continue_reason = controller.should_continue(topic)
    if continue_allowed:
        self.kg.add_curiosity(topic, score=quality, reason=f"边际收益:{marginal:.2f}")
    else:
        self.kg.mark_topic_done(topic, continue_reason)
```

**关键行为变化**：

| 场景 | v0.2.1 行为 | v0.2.2 行为 |
|------|------------|------------|
| 同一话题探索第 4 次 | 继续探索 | **被阻止** |
| 边际收益 < 0.3 | 继续探索 | **停止** |
| 探索质量 >= 7.0 | 可能通知 | 通知用户 |
| 探索质量 < 7.0 | 可能通知 | **不通知** |

---

### Step 5: API 端点 + Web UI 区域

**文件**：`curious_api.py`（端点）、`ui/index.html`（UI）

**依赖**：Step 1 + Step 2

#### 端点设计

```python
# GET /api/metacognitive/check?topic=xxx
{
    "topic": "xxx",
    "explore_count": 2,
    "max_explore_count": 3,
    "allowed": true,
    "reason": "可以探索",
    "marginal_returns": [0.8, 0.3],
    "last_quality": 6.5
}

# GET /api/metacognitive/state
{
    "explore_counts": {...},
    "marginal_returns": {...},
    "last_quality": {...},
    "recent_log": [...]  # 最近 5 条
}

# GET /api/metacognitive/history/<topic>
{
    "topic": "xxx",
    "explore_count": 3,
    "marginal_returns": [0.9, 0.4, 0.1],
    "qualities": [8.0, 7.2, 6.8],
    "notified_count": 2,
    "done_reason": "max_explore_count"
}
```

#### Web UI 区域（HTML + CSS + 简单 JS，不引入 D3）

```
┌─────────────────────────────────────────────────────────────────┐
│  🧠 元认知状态                                      [刷新]      │
├─────────────────────────────────────────────────────────────────┤
│  当前话题: metacognition in LLM                    探索次数: 2/3 │
│  质量分: 7.5  边际收益: +0.4                    状态: 🔄 进行中 │
│                                                                  │
│  探索历史（最近 5 条）                                          │
│  #1 metacognition in LLM  质量:7.5  收益:+0.4  ✅ 已通知       │
│  #2 metacognition in LLM  质量:7.1  收益:+0.9  ✅ 已通知       │
│                                                                  │
│  📊 本轮探索质量分布                                             │
│  高质量(≥7.0): ████████████░░░░░░░░░░░░  2次                   │
│  中质量(5-7):  ██████░░░░░░░░░░░░░░░░░░░  1次                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 四、验收测试清单

每 Step 完成后即可独立验证：

| Step | 测试命令 | 预期结果 |
|------|---------|---------|
| 1 | 启动服务，查看 `state.json` 有 `meta_cognitive` 字段 | 字段存在且为空结构 |
| 2 | `python3 -c "from core.meta_cognitive_monitor import MetaCognitiveMonitor; ..."` | 9 个方法可调用 |
| 3 | `python3 -c "from core.meta_cognitive_controller import MetaCognitiveController; ..."` | 3 个决策函数正常返回 |
| 4 | 注入话题 → 执行 4 次探索 | 第 4 次被阻止，日志显示 "探索被阻止" |
| 5 | `curl "http://localhost:4848/api/metacognitive/state"` | 返回完整 meta_cognitive 状态 |
| 5 | 打开 Web UI | 看到元认知状态区域 |

---

## 五、版本依赖总结

```
v0.2.2
  ├── Step 1: knowledge_graph.py 扩展（state.json 持久化）
  ├── Step 2: core/meta_cognitive_monitor.py（纯监测）
  ├── Step 3: core/meta_cognitive_controller.py（纯决策）
  ├── Step 4: curious_agent.py（MGV 循环集成）
  ├── Step 5: curious_api.py（API 端点）
  └── Step 5: ui/index.html（Web UI 元认知区域）

前置条件：v0.2.1 ICM 融合评分 + Layer 3 深度探索（已就绪）
```

---

## 六、暂存 v0.2.3 的功能（P2）

以下功能从 v0.2.2 移除，不影响本次移交：

| 功能 | 原因 | 文档位置 |
|------|------|---------|
| DK-UV 自动缺口检测 | 算法待验证 | `docs/plans/2026-03-21-v0.2.3-advanced-metacognition-design.md` |
| 动态 α 参数调节 | 依赖长期数据积累 | 同上 |
| D3.js 知识关联图 | 工作量过大 | 同上 |
| 飞书通知集成 | 暂缓 | 同上 |
| SQLite 持久化 | 暂缓 | 同上 |
| 情境缓冲区（Episodic Buffer） | 暂缓 | 同上 |
| Reflexion 口头反思记忆 | 暂缓 | 同上 |

---

_创建时间：2026-03-21_
_为 OpenCode 提供实现路径参考_
