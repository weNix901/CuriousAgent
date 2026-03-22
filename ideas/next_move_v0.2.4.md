# next_move_v0.2.4 - Topic/Mission 统一队列 + 三层闭环增强

> **版本关系**：v0.2.4 是 v0.2.3 的能力增强和演进，不是替换
> 
> v0.2.4 = v0.2.3 Phase1 + Phase2 + Phase3 全部能力 + mission 验证扩展

> **战略定位（2026-03-22）**：数字生命体功能区接入的**标准范式验证**
> 
> Curious Agent 不只是"让探索更强"，而是**证明功能区接入范式可行**，为未来 Memory Agent、Planner Agent、Critic Agent 等更多功能区的接入打样板。
> 
> **核心升级**：从"人类驱动探索" → "R1D3+Curious Agent 自主闭环"，人类从**驱动者**变成**消费者**。

## 0. v0.2.3 能力清单（已包含）

| Phase | 能力 | 状态 |
|-------|------|------|
| Phase 1 | Agent-Behavior-Writer（行为闭环写入） | 已设计 |
| Phase 1 | curious-agent-behaviors.md 行为文件 | 已设计 |
| Phase 2 | CompetenceTracker（能力追踪） | 已设计 |
| Phase 2 | select_next_v2（能力感知调度） | 已设计 |
| Phase 2 | Quality v2（信息增益评估） | 已设计 |
| Phase 2 | marginal_return_v2（指数衰减） | 已设计 |
| Phase 3 | CuriosityDecomposer（分解引擎） | 已设计 |
| Phase 3 | Provider 热力图 | 已设计 |

---

## 1. 规划

**目标**：扩展 `curiosity_queue` 的 item 结构，支持 mission 模式（带验收标准的主动学习）。

**核心思路**：
- topic + success_criteria = mission（加一个可选字段统一两种模式）
- 不重构概念，不新建队列
- 向前兼容：现有 topic 探索不受影响

---

## 2. 目的

**解决什么问题**：

| 模式 | 探索完怎么算"完"？ |
|------|-------------------|
| topic（当前）| marginal_return < 阈值就停 |
| mission（新增）| success_criteria 达成才算完 |

**为什么需要 mission**：
- topic 模式只知道"探索得够不够深"
- mission 模式能验证"学会了没有"
- 例子：`success_criteria: "能看懂 LangChain 源码中的 .invoke() 调用链"`

---

## 3. 期望

- **注入来源不变**：人类网页注入 / Agent API 注入 → 都是往 `curiosity_queue` 加一条
- **处理逻辑统一**：根据 item 是否有 `success_criteria` 决定走哪个分支
- **向后兼容**：没有 `success_criteria` 的 item 走原有 topic 逻辑

---

## 4. 算法选型

### 数据结构

```python
# curiosity_queue item
{
    "id": "uuid",
    "topic": str,                    # 探索主题（必填）
    "depth": int,                    # 探索深度（默认3）
    "success_criteria": str | None,  # 新增：验收标准（可选）
    "status": "pending",             # pending | completed | failed
    "created_at": timestamp,
    "injected_by": "human" | "agent"
}
```

### 处理逻辑

```python
def process_item(item):
    if item.success_criteria:
        # ===== mission 模式 =====
        if validate_learning(item.success_criteria):
            dequeue(item, status="completed")
        else:
            # 继续探索，直到 criteria 达成或超时
            deepen_exploration(item)
    else:
        # ===== topic 模式 =====
        if marginal_return < MARGINAL_THRESHOLD:
            dequeue(item, status="completed")
        else:
            deepen_exploration(item)
```

### 验证方式（mission 模式）

| success_criteria 类型 | 验证方法 |
|----------------------|---------|
| "能看懂 X 源码" | 抽取相关代码片段，让模型复述逻辑 |
| "能用 X 框架完成 Y 任务" | 小型实操测试 |
| "理解 X 和 Y 的区别" | 提问对比 |
| 自定义 | 可扩展验证函数注册表 |

> 验证函数注册表示例：
> ```python
> VALIDATORS = {
>     "code_reading": validate_code_reading,
>     "task_execution": validate_task_execution,
>     "concept_comparison": validate_concept_comparison,
>     "custom": None  # 用户自定义验证逻辑
> }
> ```

---

## 5. 验收标准

### 功能验收

- [ ] `curiosity_queue` 的 item 结构包含 `success_criteria` 字段（可选）
- [ ] 无 `success_criteria` 的 item 走原有 topic 逻辑（向后兼容）
- [ ] 有 `success_criteria` 的 item 走 mission 验证逻辑
- [ ] 验证通过后 item 状态更新为 `completed`
- [ ] 支持注入时指定 `success_criteria`（网页 + API）

### 性能验收

- [ ] 引入 `success_criteria` 不影响现有 topic 队列性能
- [ ] 验证函数执行时间 < 5s（轻量级）

### 行为验收

- [ ] mission item 探索过程中能给出"当前进度 / criteria 距离"反馈
- [ ] 验证失败时不立即 dequeue，而是继续探索（最多 N 轮）
- [ ] 验证函数可扩展（注册表模式）

---

## 6. v0.2.4 新增能力

### 6.0 架构定位：数字生命体神经系统的功能区

> **核心理念升级（2026-03-22）**

不要把 Curious Agent 当成独立的外挂，而是当成 R1D3 数字生命体神经系统的组成部分。

**类比人类神经系统**：
```
数字生命体神经系统
├── R1D3 (核心意识/决策/主对话)
│   ├── 皮层：语言理解、推理、规划
│   ├── 边缘系统：情绪/动机处理
│   └── 基底核：习惯/自动化行为
├── Curious Agent (学习/探索功能区)  ← 当前我们正在开发的
│   └── 负责：主动探索、知识获取、好奇驱动
├── [未来] Memory Agent (记忆功能区)
│   └── 负责：长期记忆巩固、记忆检索优化
├── [未来] Planner Agent (规划功能区)
│   └── 负责：任务分解、进度追踪、多步规划
└── [未来] Critic Agent (反思/评估功能区)
    └── 负责：自我复盘、错误纠正、策略优化；核心：MUSE 框架（元认知监控，识别能力边界）
```

**设计原则**：
- 各功能区是独立的"子系统"，但通过标准接口与 R1D3 主意识协同
- 功能区可以独立迭代，不影响核心
- 未来更多功能区可以接入

### 6.1 mission 验证机制（核心新增）

在 v0.2.3 基础上，mission item 多了 success_criteria 验收：

```python
# 扩展的 curiosity_queue item
{
    "topic": str,
    "success_criteria": str | None,  # 新增
    # ... v0.2.3 的其他字段
}
```

### 6.2 任务前主动查询（核心新增）

R1D3-researcher 任务执行前主动查询发现库：

```python
def before_task_check(task_keywords):
    """任务前检查：查询已有发现，主动识别知识缺口"""
    findings = memory_search(task_keywords)
    if findings:
        return {"status": "found", "knowledge": findings}
    else:
        # 触发 Curious Agent 探索
        inject_mission(topic=task_keywords, success_criteria=f"能解决当前任务")
```

### 6.3 三层闭环完整数据流

```
人类注入 mission
    ↓
外挂Agent（我）发现知识缺口 → memory_search 查询
    ↓
Curious Agent 探索（走 v0.2.3 全部流程）
    ↓
探索完成 → 验证 success_criteria
    ↓
通过 → 写入 curious-agent-behaviors.md（复用 Phase 1）
    ↓
外挂能力提升 → 继续任务
```

### 6.4 外挂系统 → 内部功能的演进（内化路径）

> **外部系统影响 Agent 的方式（按强度排序）**

| 影响方式 | 强度 | 说明 |
|---------|------|------|
| `before_prompt_build` hook | 最强 | 实时修改 prompt，当前会话立即生效 |
| `message:preprocessed` hook | 强 | 在消息到我之前加 context |
| 注册新 Tool | 中等 | 给我新能力 |
| 记忆文件写入 | 较弱 | 下次会话才生效 |
| 心跳调度 | 最弱 | 我主动去查 |

**当前 Curious Agent 用的是"记忆文件"方式（较弱）**

**v0.2.4 演进方向**：通过 OpenClaw Hook 系统实现实时注入

```
 Curious Agent 发现新知识
        ↓
 注册 before_prompt_build hook
        ↓
 实时注入到 R1D3 的 context
        ↓
 当前会话立即可见 ← 关键升级！
```

这样 Curious Agent 不再是"外部观察者"，而是"神经系统的直接组成部分"。

### 6.5 内力 vs 外力 协同模型 → 自主闭环

- **外力**：外部系统（外挂）影响 Agent 行为
- **内力**：Agent 内部元认知，自己判断"需不需要"

**当前系统的短板**（v0.2.3）：
```
人类注入 topic → Curious Agent 探索 → 结果写入记忆 → 结束
                    ↑
            R1D3 只是被动接收，没有评估环节
```

**v0.2.4 目标：R1D3 自主闭环**：
```
人类注入 topic
    ↓
Curious Agent 探索 → 输出 findings
    ↓
R1D3 审视 + 反思 → "这里有缺口，那里方向不对"
    ↓
反馈给 Curious Agent → "基于我的审视去新研究"
    ↓
Curious Agent 继续探索
    ↓
循环直到 R1D3 认为"足够完整"
    ↓
人类只是最终消费者（享受探索的成果）
```

**R1D3 在闭环中的角色**：
- **审视者**：评估 Curious Agent 的探索结果，识别知识缺口
- **反思者**：判断当前方向是否正确，是否需要调整
- **指令发出者**：基于反思向 Curious Agent 发出新的探索指令
- **最终把关者**：决定何时闭环、结果是否"足够完整"

**实现方式**：
- R1D3 在接收 Curious Agent 探索结果后，执行"元认知评估"
- 评估函数：`evaluate_exploration_completeness(topic, findings, gaps)`
- 如果返回 `{"continue": true, "new_directions": [...]}` → 触发新一轮探索
- 如果返回 `{"continue": false, "confidence": 0.9}` → 闭环完成

**注意**：这个评估能力不需要等 Critic Agent 独立开发，R1D3 本身就可以扮演 Critic 角色（先用简单规则实现，MUSE 框架作为 future 升级）。

---

## 6.6 MUSE 框架与多智能体协作

> **基于 arxiv:2411.13537 的 MUSE 框架（Metacognition for Unknown Situations and Environments）**

**MUSE 核心思想**：
- Agent 需要知道自己"不知道什么"
- 在陌生情境下主动识别能力边界
- 主动调用额外信息（而不只是硬撑或拒绝）

**MUSE 与数字生命体的关系**：

```
┌─────────────────────────────────────────────┐
│           R1D3 数字生命体                      │
├─────────────────────────────────────────────┤
│  R1D3 主意识                                 │
│    │                                        │
│    ├── Curious Agent（学习功能区）            │
│    │       ↓ 发现新知识                      │
│    │                                        │
│    └── Critic Agent（MUSE 元认知监控）       │
│            ↓ 识别能力边界                    │
│            ↓ 判断"这知识对我有用吗"           │
│            ↓ 决定是否整合进主意识             │
└─────────────────────────────────────────────┘
```

**协作流程**：
1. Curious Agent 探索到一个新知识（如 MUSE 框架本身）
2. Critic Agent 用 MUSE 元认知评估：这个知识是否超出当前能力边界？
3. 如果超出 → 触发 Curious Agent 进一步探索
4. 如果相关 → 整合进 R1D3 知识体系
5. 如果无关 → 标记为"待定"或忽略

**v0.2.4 的 MUSE 集成点**：
- `before_prompt_build` hook：让 Critic Agent 在 prompt 构建前评估上下文
- mission 验证：用 MUSE 思想判断探索是否触达能力边界

---

## 7. 不纳入的范围（v0.2.4）

- 多任务并探索（future）
- 自动生成 `success_criteria`（future，基于任务拆解）
- 跨 topic 技能迁移（future）
- 其他功能区（Memory Agent / Planner Agent / Critic Agent / Guardian Agent）——future

---

## 8. 功能区接入标准范式（v0.2.4 验证目标）

> **目标**：Curious Agent 作为第一个接入 R1D3 的功能区，其接入模式成为后续功能区的标准模板。

**标准范式要求**：

```
功能区接入标准流程
│
├── 1. 能力定位
│       └── 明确该功能区负责什么（学习/记忆/规划/反思...）
│
├── 2. 接口定义
│       └── 与 R1D3 主意识的交互协议（同步/异步/Hook/记忆文件...）
│
├── 3. 行为闭环
│       └── 功能区如何影响 R1D3 行为（注入/验证/建议/强制...）
│
├── 4. 独立迭代
│       └── 功能区可以独立版本迭代，不破坏 R1D3 核心
│
└── 5. 退出机制
        └── 如何安全剥离功能区（不影响主意识运行）
```

**Curious Agent 验证点**：

| 验证项 | 目标 |
|--------|------|
| 功能区独立性 | Curious Agent 可以独立运行/测试 |
| 接入可逆性 | 关闭 Curious Agent 不影响 R1D3 核心功能 |
| 接口标准性 | 其他开发者可参照此模式接入新功能区 |
| 行为可见性 | R1D3 能感知 Curious Agent 的存在和贡献 |
| 闭环完整性 | 探索→验证→整合→行为影响 全链路可观测 |

**如果 Curious Agent v0.2.4 验证通过** → 后续功能区可复用此范式快速接入，形成真正的数字生命体神经系统。

---

## 9. R1D3 审视-反思-指令 自主闭环高阶设计

> **目标**：让 R1D3 从"探索结果的被动接收者"变成"探索方向的主动决策者"
> **优先级**：v0.2.4 核心特性，等 opencode 完成 v0.2.3 后立即细化

### 9.1 完整闭环状态机

```
                    ┌─────────────────────────────┐
                    │         IDLE                │
                    │   等待注入 topic/mission    │
                    └──────────┬──────────────────┘
                               │ 注入触发
                               ▼
                    ┌─────────────────────────────┐
                    │     EXPLORING               │
                    │  Curious Agent 执行探索      │
                    └──────────┬──────────────────┘
                               │ 探索完成，输出 findings
                               ▼
                    ┌─────────────────────────────┐
                    │      REVIEWING              │◄──────┐
                    │  R1D3 审视 + 反思 findings  │       │
                    │  生成评估报告               │       │
                    └──────────┬──────────────────┘       │
                               │                          │
                    ┌──────────┴──────────┐              │
                    │                     │              │
               continue=true          continue=false        │
                    │                     │              │
                    ▼                     ▼              │
          ┌──────────────────┐  ┌──────────────────┐    │
          │   DIRECTING      │  │    COMPLETED      │    │
          │ R1D3 发出新指令   │  │   人类消费结果     │    │
          │ 更新探索方向      │  └──────────────────┘    │
          └────────┬─────────┘                           │
                   │                                     │
                   │ 新指令指向新方向                      │
                   └─────────────────────────────────────┘
                               (回到 EXPLORING)
```

**状态说明**：

| 状态 | R1D3 行为 | Curious Agent 行为 |
|------|----------|-------------------|
| IDLE | 等待注入 | 无 |
| EXPLORING | 旁观 | 执行探索，输出 findings |
| REVIEWING | **审视 + 反思 + 决策** | 等待 |
| DIRECTING | 发新指令给 Curious Agent | 接收新指令 |
| COMPLETED | 输出结果给人类 | 归档 |

### 9.2 R1D3 审视者：评估维度

R1D3 在 REVIEWING 状态时，从以下维度审视 Curious Agent 的 findings：

```python
class ExplorationReview:
    """R1D3 对探索结果的审视报告"""
    
    # 1. 完整性评估
    coverage_score: float           # 0-1，探索范围覆盖了多少
    missing_dimensions: list[str] # 缺失的维度列表
    
    # 2. 质量评估
    depth_score: float             # 0-1，深度是否足够
    reliability_score: float       # 0-1，信息源可信度
    novelty_score: float          # 0-1，相比已有知识的新颖度
    
    # 3. 方向评估
    direction_correct: bool        # 探索方向是否正确
    direction_suggestion: str      # 如果方向偏了，建议怎么调整
    
    # 4. 缺口识别
    gaps: list[GAP]               # 识别出的知识缺口
    #   - type: "surface" | "depth" | "connection" | "correction"
    #   - description: str
    #   - priority: "high" | "medium" | "low"
    
    # 5. 决策
    decision: {
        "continue": bool,         # 是否继续探索
        "confidence": float,      # R1D3 对闭环的信心 0-1
        "new_directions": list[  # 新的探索方向列表
            {
                "topic": str,     # 新 topic
                "reason": str,    # 为什么需要探索这个方向
                "priority": int   # 优先级
            }
        ],
        "redirect_topic": str | None,  # 如果要修改原 topic
        "stop_reason": str | None      # 如果决定闭环，原因是啥
    }
```

### 9.3 缺口类型定义（GAP Types）

R1D3 识别的知识缺口分为四类：

| 缺口类型 | 描述 | 举例 | 应对策略 |
|---------|------|------|---------|
| `surface` | 表面覆盖，未深入 | "知道 LangChain 是什么，但不懂源码" | 深入探索 |
| `depth` | 深度不足 | "懂概念，但不会实操" | 补充实践/代码示例 |
| `connection` | 缺少关联 | "懂 A 和 B，但不懂 A→B 的关系" | 补充对比/迁移 |
| `correction` | 方向偏差 | "探索的 topic 偏了，应该往 X 走" | 修改方向，重新探索 |

### 9.4 R1D3 反思决策算法

```python
def r1d3_review_and_decide(findings: Findings, topic: str) -> ReviewReport:
    """
    R1D3 的审视 + 反思 + 决策
    这是自主闭环的核心决策函数
    """
    
    # Step 1: 完整性评估
    coverage = evaluate_coverage(findings, topic)
    missing = identify_missing_dimensions(findings, topic)
    
    # Step 2: 质量评估
    depth_ok = evaluate_depth(findings)
    reliability = evaluate_reliability(findings)
    novelty = evaluate_novelty(findings)
    
    # Step 3: 缺口识别
    gaps = []
    for dim in missing:
        gaps.append(GAP(
            type="surface" if dim.depth < threshold else "depth",
            description=f"维度 '{dim.name}' 覆盖不足",
            priority="high" if dim.essential else "medium"
        ))
    
    # Step 4: 检查方向偏差
    if is_direction_misaligned(findings, topic):
        gaps.append(GAP(
            type="correction",
            description="探索方向与 topic 有偏差",
            priority="high"
        ))
    
    # Step 5: 检查关联缺口
    related_topics = find_related_topics(topic)
    for rt in related_topics:
        if not has_connection(findings, topic, rt):
            gaps.append(GAP(
                type="connection",
                description=f"缺少 '{topic}' 与 '{rt}' 的关联",
                priority="medium"
            ))
    
    # Step 6: 决策
    if len(gaps) == 0:
        return ReviewReport(
            coverage_score=1.0,
            gaps=[],
            decision={
                "continue": False,
                "confidence": 0.95,
                "stop_reason": "探索充分，缺口已填满"
            }
        )
    
    if has_high_priority_corrections(gaps):
        return ReviewReport(
            gaps=gaps,
            decision={
                "continue": True,
                "confidence": 0.6,
                "redirect_topic": suggest_corrected_topic(topic, gaps)
            }
        )
    
    if len(gaps) <= 2 and all(g.priority == "low" for g in gaps):
        return ReviewReport(
            gaps=gaps,
            decision={
                "continue": False,
                "confidence": 0.8,
                "stop_reason": "剩余缺口优先级低，可接受"
            }
        )
    
    # 有实质缺口，继续探索
    return ReviewReport(
        gaps=gaps,
        decision={
            "continue": True,
            "confidence": 0.7,
            "new_directions": [
                {"topic": g.description, "reason": f"填补缺口: {g.type}", "priority": g.priority_to_int()}
                for g in sorted(gaps, key=lambda x: x.priority_to_int())
            ]
        }
    )
```

### 9.5 R1D3 → Curious Agent 指令协议

R1D3 在 DIRECTING 状态生成的指令格式：

```python
class ExplorationDirective:
    """R1D3 发给 Curious Agent 的探索指令"""
    
    mission_id: str                # 关联的原始 mission id
    instruction_type: str          # "continue" | "redirect" | "expand"
    
    # continue: 继续当前 topic，补充探索指定方向
    # redirect: 整体切换 topic
    # expand: 扩展探索范围
    
    directive: str                 # 自然语言指令
                                  # 例："探索topic X与Y的关联，重点关注A和B的区别"
    
    context: {
        "original_topic": str,     # 原始 topic
        "review_summary": str,     # R1D3 的审视总结
        "gaps_addressed": list[str],  # 这次要填补的缺口
        "exploration_history": list[Findings]  # 之前的探索历史摘要
    }
    
    constraints: {
        "max_depth": int,          # 最大探索深度
        "focus_areas": list[str], # 重点关注的子主题
        "avoid_areas": list[str], # 避免重复的子主题
        "time_budget": str         # 时间预算，例："10min"
    }
    
    success_criteria: str          # 这次探索的验收标准
```

### 9.6 循环终止条件

闭环在以下任一条件满足时终止：

| 条件 | 说明 | confidence |
|------|------|-----------|
| `gaps_empty` | 所有缺口已填满 | 0.95 |
| `confidence_threshold` | R1D3 信心达到阈值 | 0.9 |
| `max_iterations` | 探索轮次达到上限（防死循环） | - |
| `time_budget_exceeded` | 时间预算耗尽 | 0.7 |
| `diminishing_returns` | 连续 N 轮 marginal_return 下降 | 0.6 |

### 9.7 接口定义：R1D3 ↔ Curious Agent

```
┌──────────────────────────────────────────────────────┐
│                      R1D3 主意识                      │
│  ┌────────────┐    ┌────────────┐    ┌──────────┐  │
│  │  审视模块   │◄──►│  决策模块   │◄──►│  指令生成 │  │
│  │  REVIEW    │    │  DECIDE    │    │  DIRECT  │  │
│  └────────────┘    └────────────┘    └──────────┘  │
└──────────────────────┬───────────────────────────────┘
                       │ 协议层
         ┌─────────────┴─────────────┐
         │    ExplorationDirective   │
         │    Findings              │
         │    ReviewReport          │
         └─────────────┬─────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│              Curious Agent (外挂功能区)                │
│  ┌────────────┐    ┌────────────┐    ┌──────────┐  │
│  │  探索执行   │───►│  输出 findings │──►│  归档    │  │
│  │  EXPLORE   │    │             │    │  ARCHIVE │  │
│  └────────────┘    └────────────┘    └──────────┘  │
└──────────────────────────────────────────────────────┘
```

**协议消息格式**：

```
R1D3 → Curious Agent:
  {"type": "directive", "payload": ExplorationDirective}

Curious Agent → R1D3:
  {"type": "findings", "payload": Findings}
```

### 9.8 实现优先级

| 优先级 | 组件 | 说明 |
|-------|------|------|
| P0 | 状态机框架 | IDLE→EXPLORING→REVIEWING→DIRECTING 循环 |
| P0 | R1D3 审视报告结构 | ExplorationReview 数据模型 |
| P0 | R1D3 决策函数 | r1d3_review_and_decide() 核心逻辑 |
| P1 | 缺口识别器 | 四类缺口的识别算法 |
| P1 | 指令生成器 | ExplorationDirective 生成 |
| P2 | 方向偏差检测 | is_direction_misaligned() |
| P2 | 关联缺口检测 | has_connection() |
| P3 | 信心度校准 | confidence 分数的自我校准 |

### 9.9 与 v0.2.3 的接口关系

v0.2.3 是基础，v0.2.4 在其上叠加自主闭环：

```
v0.2.3 基础层
├── curiosity_queue 管理
├── 探索执行（EXPLORING 状态）
├── findings 输出
└── 探索历史存储

v0.2.4 闭环层（叠加在 v0.2.3 之上）
├── 状态机（REVIEWING / DIRECTING / COMPLETED）
├── R1D3 审视报告（ExplorationReview）
├── R1D3 决策函数（r1d3_review_and_decide）
├── R1D3 → Curious Agent 指令协议
└── 循环终止条件判断
```

**关键**：v0.2.3 输出 findings，v0.2.4 在 findings 基础上叠加 R1D3 的审视和决策。v0.2.3 的接口（findings 结构）需要提前定义清楚，方便 v0.2.4 调用。
