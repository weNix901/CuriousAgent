# SPEC v0.2.5 — KG 根技术追溯能力

> **唯一目标**: 从任意知识点追溯到根技术，并形成完整的因果链
> **发布日期**: TBD

---

## 背景

v0.2.4 的 KG 只能向下分解（parent → children），无法向上回溯（child → parent → root）。

这导致两个问题：
1. **R1D3 无法消费 KG** — 无法回答"metacognitive monitoring 的根技术是什么"
2. **跨子图根技术被埋没** — transformer attention 横跨多个探索分支，但在各分支里都不显眼

v0.2.5 只解决这两个问题。

---

## 核心数据结构

### 1. 双向父子关系

```python
# knowledge/state.json 的 topic 结构变更
topics[topic_name] = {
    "known": bool,
    "depth": int,
    "status": "unexplored | partial | complete | explored",
    "quality": float,           # 新增
    
    # 向下关系（已有）
    "children": ["child1", "child2"],
    "explored_children": [],
    
    # 向上关系（新增）
    "parents": ["parent1", "parent2"],    # 谁派生了这个 topic
    "root_score": float,                    # 根技术评分（新增）
    "is_root_candidate": bool,              # 是否候选根节点（新增）
    "cross_domain_count": int,              # 跨多少个探索分支（新增）
    
    # 溯源链（新增）
    "derived_from": [              # 因果链：谁解释了这个 topic
        {
            "source": "self-reflection mechanisms",
            "relation": "explains",
            "confidence": 0.85
        }
    ],
    "explains": [],               # 反向：这个 topic 解释了哪些 topic
    
    # 元数据
    "first_observed": timestamp,
    "last_updated": timestamp
}
```

### 2. 根技术候选池

```python
# 独立区域，不属于任何 topic
state["root_technology_pool"] = {
    "candidates": [
        {
            "name": "transformer attention",
            "root_score": 9.2,          # 由 cross_domain_count 和 explains_count 共同决定
            "cross_domain_count": 7,    # 出现在多少个不同探索分支
            "explains_count": 23,        # 直接解释了多久 topic
            "domains": ["LLM", "CV", "NLP", "RL", "Speech", "Recommendation", "TimeSeries"],
            "confidence": 0.91,
            "candidatesources": ["manual_label", "cross_subgraph_detection"]
        }
    ]
}
```

---

## 新增组件

### F1: Parent Tracker（core/parent_tracker.py）

**职责**: 探索时主动记录每个新 topic 的 parent

**触发时机**: 
- `add_exploration_result()` 被调用时，parent 是当前正在探索的 topic
- 在 `add_exploration_result` 里新增 `parent_topic` 参数

**逻辑**:
```python
def track_parent(child: str, parent: str, relation: str = "derived_from"):
    # 双向写入
    topics[child]["parents"].add(parent)
    topics[parent]["explains"].append({"target": child, "relation": relation})
```

### F2: Cross-Subgraph Detector（core/cross_subgraph_detector.py）

**职责**: 发现跨探索分支的连接

**触发时机**: 每次探索完成，新 topic 被添加到 KG 后

**逻辑**:
```python
def detect_cross_subgraph(new_topic: str, kg_state: dict) -> list:
    """
    检测 new_topic 是否与其他探索分支的 topic 共享关键词或概念。
    如果是，建立跨子图边。
    
    Returns: 跨子图连接列表 [{"connected_topic": "...", "shared_concept": "..."}]
    """
    # 1. 提取 new_topic 的关键词（从 summary/sources 里）
    # 2. 遍历已有 KG，找出共享概念的 topic（忽略直接父子关系）
    # 3. 如果 shared_concept 在不同探索分支里，标记为跨子图连接
    # 4. 更新 cross_domain_count
```

**根技术浮现规则**:
- 如果一个 topic 被 ≥3 个不同探索分支的 topic 引用 → 自动进入 root_technology_pool
- root_score = cross_domain_count × 0.4 + explains_count × 0.6

### F3: Root Tracer（core/root_tracer.py）

**职责**: 给 R1D3 提供根技术查询 API

**API 端点**（扩展 curious_api.py）:

```
GET /api/kg/trace/<topic_name>

Response:
{
    "topic": "metacognitive monitoring in LLM agents",
    "quality": 10.51,
    "trace": [
        {
            "level": 0,
            "topic": "metacognitive monitoring in LLM agents",
            "relation": "current"
        },
        {
            "level": 1,
            "topic": "self-reflection mechanisms", 
            "relation": "derived_from",
            "is_root": false
        },
        {
            "level": 2,
            "topic": "ReAct loop",
            "relation": "derived_from",
            "is_root": false
        },
        {
            "level": 3,
            "topic": "transformer attention",
            "relation": "derived_from",
            "is_root": true,
            "root_score": 9.2,
            "cross_domain_count": 7
        }
    ],
    "root_technologies": [
        {
            "name": "transformer attention",
            "root_score": 9.2,
            "confidence": 0.91
        }
    ],
    "cross_subgraph_connections": [
        {
            "connected_topic": "RLHF",
            "shared_concept": "reward signal based evaluation",
            "branch": "RL"
        }
    ]
}
```

```
GET /api/kg/roots

Response:
{
    "roots": [
        {
            "name": "transformer attention",
            "root_score": 9.2,
            "cross_domain_count": 7,
            "explains_count": 23,
            "domains": ["LLM", "CV", "NLP", "RL", "Speech", "Recommendation", "TimeSeries"]
        }
    ],
    "total": N
}
```

### F4: Root Technology Writer（core/root_technology_writer.py）

**职责**: 管理 root_technology_pool 的写入

**触发时机**:
- Cross-Subgraph Detector 发现跨分支连接时
- R1D3 主动标记某 topic 为根技术时（通过 API）
- 手动通过配置注入初始根技术列表

**初始根技术列表**（config.json 注入）:
```json
{
    "root_technologies": {
        "initial_seeds": [
            "transformer attention",
            "gradient descent",
            "backpropagation",
            "softmax",
            "RL reward signal",
            "uncertainty quantification"
        ]
    }
}
```

---

## R1D3 消费接口

### 同步脚本: sync_kg_to_r1d3.py

**路径**: `scripts/sync_kg_to_r1d3.py`

**功能**: 将 CA 的 KG 同步到 R1D3 可读的格式

```python
# 同步内容：
# 1. trace/<topic> 的完整因果链
# 2. roots 列表（所有根技术）
# 3. cross_subgraph 跨分支连接

# 同步目标：
# R1D3 的 memory/curious/kg/ 目录
```

**R1D3 调用方式**（心跳或按需）:
```bash
python3 scripts/sync_kg_to_r1d3.py --topic "metacognitive monitoring"
# → 输出到 memory/curious/kg/trace/metacognitive-monitoring.md

python3 scripts/sync_kg_to_r1d3.py --roots
# → 输出到 memory/curious/kg/roots.md
```

**R1D3 使用场景**:
```python
# 场景1: 用户问"metacognitive monitoring 是什么"
→ R1D3 调用 sync_kg_to_r1d3.py --topic "metacognitive monitoring"
→ 读取 memory/curious/kg/trace/metacognitive-monitoring.md
→ 得到完整因果链: metacognitive → self-reflection → ReAct → transformer attention
→ 用自然语言回答，并说明根技术

# 场景2: R1D3 好奇某个 topic 的根技术
→ 调用 sync_kg_to_r1d3.py --roots
→ 找到 root_score 最高的根技术
→ 作为自己好奇探索的起点
```

---

## 可视化设计（UI 层）

v0.2.5 的 KG 可视化是给人类理解和 R1D3 调试用的，不追求花哨，强调**信息密度**和**可操作性**。

### 1. Trace View（溯源视图）

**入口**: 点击任意 topic 节点，或 API 调用 `/api/kg/trace/<topic>`

**展示内容**:
- 从该 topic 到根技术的完整路径（纵向树状图）
- 根节点在最底部，层层向上汇聚
- 每条边上标注关系类型：`derived_from` | `shares_concept` | `parent_of`

**样式**:
- 根节点：实心圆，大小 = root_score，颜色 = gold
- 中间节点：实心圆，大小 = quality
- 叶子节点（当前 topic）：实心圆 + 脉冲动画
- 跨子图边：虚线（实线 = 域内，边线 = 跨分支）

### 2. KG Overview（全局视图）

**入口**: 默认首页，或点击"全图"tab

**展示内容**:
- 所有 topic 节点按探索分支聚类
- 不同分支用不同颜色：meta-cognitive=蓝、planning=绿、memory=紫、RL=橙
- 根技术节点用特殊边框（双圈）高亮
- 节点大小 = quality 或 root_score（可切换）

**交互**:
- 拖拽平移 + 滚轮缩放
- Hover 节点 → 显示 tooltip（topic name + quality + 简介摘要）
- Click 节点 → 弹出详情卡，或跳转到 Trace View
- 右键节点 → "展开 explains 链" / "查看 sources" / "标记为根技术"

### 3. Root Pool View（根技术池）

**入口**: 切换 tab 或 `/api/kg/roots` 对应的可视化

**展示内容**:
- 所有根技术候选节点（来自 root_technology_pool）
- 按 root_score 排序，横向柱状图 + 节点图双视图
- 显示 cross_domain_count（多少分支引用）和 explains_count（解释了多少 topic）

**样式**:
- 根节点大小 = root_score
- 连接线粗细 = explains_count
- 分支引用用分枝小圆点列表标注

### 4. Subgraph Filter（子图筛选）

**交互控件**:
- **Branch filter**: 下拉选择只看某个探索分支（meta-cognitive、planning、memory 等）
- **Time slider**: 按探索时间范围过滤
- **Quality threshold**: 滑块过滤 quality < X 的节点
- **Root only**: toggle，只显示根技术及其直接子节点

### 5. Anomaly Detection View（异常检测）

**展示内容**:
- 孤立节点（无任何连接的 topic）→ 红色虚线边框
- 高入度但低 quality 的节点 → 黄色警告图标
- 根候选（root_score 在阈值 ±0.5 波动）→ 绿色脉冲

**数据来源**:
```python
def detect_anomalies() -> dict:
    return {
        "orphans": [topic for topic in kg if no connections(topic)],
        "low_quality_hubs": [topic for topic in kg if indegree > 5 and quality < 4.0],
        "borderline_roots": [r for r in roots if 4.0 <= r.root_score < 5.0]
    }
```

### 6. 实现方式

**前端**: 复用现有 UI 框架（PyWebIO 或类 streamlit），逐步增强

**不做**: 3D 图、Force-directed animation、复杂粒子效果——v0.2.5 强调可操作性，不做炫技。

**API 补充**:
```
GET /api/kg/overview          # 全图数据（带分支聚类）
GET /api/kg/anomalies          # 异常节点列表
GET /api/kg/subgraph?branch=X&after=TS # 筛选子图
```

---

## 实现任务

| Task | 组件 | 描述 | 优先级 |
|------|------|------|--------|
| T-1 | KG schema | state.json topic 结构变更（parents, explains, root_score, cross_domain_count） | P0 |
| T-2 | Parent Tracker | 探索时记录 parent，写入双向关系 | P0 |
| T-3 | Cross-Subgraph Detector | 检测跨分支连接，触发根技术候选浮现 | P0 |
| T-4 | Root Tracer API | `/api/kg/trace/<topic>` + `/api/kg/roots` | P0 |
| T-5 | Root Technology Writer | 管理 root_technology_pool 写入 | P0 |
| T-6 | sync_kg_to_r1d3.py | R1D3 消费脚本 | P0 |
| T-7 | config.json | 注入初始根技术种子列表 | P1 |
| T-8 | 迁移脚本 | 将已有 KG 数据迁移到新 schema | P1 |
| T-9 | 测试验证 | 验证 trace 链路正确性 | P0 |
| T-10 | KG Overview API | `/api/kg/overview` 返回全图数据（带分支聚类）| P0 |
| T-11 | Anomaly Detection API | `/api/kg/anomalies` 返回异常节点列表 | P1 |
| T-12 | Subgraph Filter API | `/api/kg/subgraph` 支持分支/时间/quality 筛选 | P1 |
| T-13 | Trace View UI | 溯源视图（纵向树状图） | P0 |
| T-14 | KG Overview UI | 全局视图（分支聚类 + 根节点高亮） | P0 |
| T-15 | Anomaly View UI | 异常检测视图 | P2 |

---

## 不在 v0.2.5 范围内

- 3D 图、Force-directed animation、复杂粒子效果
- 新的探索策略
- 多 Provider 并行优化
- 其他非 KG 根技术追溯的功能

---

## 验收标准

1. R1D3 能通过 `sync_kg_to_r1d3.py` 获取任意 topic 的完整因果链
2. `/api/kg/trace/metacognitive%20monitoring` 返回从该 topic 到根技术的完整链路
3. `/api/kg/roots` 返回按 root_score 排序的根技术列表
4. 已有探索数据通过迁移脚本能显示父子关系（不要求完整，但要有边）
5. transformer attention 在 cross_domain_count ≥ 3 时自动进入 root_technology_pool

---

_Last updated: 2026-03-27 by R1D3_
