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

---

## 不在 v0.2.5 范围内

- UI 改动
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
