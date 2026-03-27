# Buglist v0.2.5 — KG 根技术追溯能力

> 发现时间: 2026-03-27 by R1D3
> 状态: 待修复
> 优先级: P0

---

## 概述

v0.2.5 的基础设施（schema、API、扩散激活算法）已正确实现，但**核心写入路径没有集成**——所有 Topic 的 `parents`、`explains`、`children` 全为空，导致 `get_spreading_activation_trace()` 的扩散激活实际上只有起点一个节点，无法真正发挥价值。

---

## Bug #1: `_update_parent_relation()` 未在任何地方被调用

**严重程度**: P0
**影响**: 所有探索结果的父子关系都未被写入，`get_spreading_activation_trace()` 无法形成链路

**根因**: spec 里要求在 `add_child()` 和 `mark_topic_done()` 内部追加 `_update_parent_relation()` 调用，但这个修改没有实际落地到代码里

**验证**:
```bash
cd /root/dev/curious-agent
grep -n "_update_parent_relation" core/knowledge_graph.py
# 期望: 至少 2 处（add_child 末尾 + mark_topic_done 末尾）
# 实际: 0 处
```

**修复要求**:

在 `core/knowledge_graph.py` 的 `add_child()` 函数**末尾**追加:
```python
def add_child(parent: str, child: str) -> None:
    # ... 现有代码 ...
    
    # === v0.2.5 追加: 双向写入父子关系 ===
    _update_parent_relation(parent, child)
    # === v0.2.5 追加结束 ===
```

在 `core/knowledge_graph.py` 的 `mark_topic_done()` 函数**末尾**追加:
```python
def mark_topic_done(topic: str, reason: str) -> None:
    # ... 现有代码 ...
    
    # === v0.2.5 追加: 从 curiosity_queue 查找 parent 并写入 ===
    state = _load_state()
    for queue_item in state.get("curiosity_queue", []):
        if queue_item.get("status") == "exploring":
            parent_topic = queue_item.get("topic")
            if parent_topic and parent_topic != topic:
                _update_parent_relation(parent_topic, topic)
                break
    # === v0.2.5 追加结束 ===
```

---

## Bug #2: `children` 字段写入路径未集成

**严重程度**: P0
**影响**: `add_child()` 函数存在但从未被调用，导致 KG 没有树状结构

**根因**: `curious_agent.py` 的 `run_one_cycle()` 里调用 `add_child()` 的逻辑缺失

**验证**:
```bash
cd /root/dev/curious-agent
grep -n "add_child" curious_agent.py
# 期望: 有调用
# 实际: 无匹配
```

**修复要求**:

在 `curious_agent.py` 的 `run_one_cycle()` 函数里，找到以下注释位置并追加代码：

找到这段代码（大约在 `kg.mark_topic_done()` 调用之后）：
```python
    # Record parent-child relationship if topic was decomposed
    if "original_topic" in next_curiosity:
        kg.add_child(next_curiosity["original_topic"], next_curiosity["topic"])
```

如果这段代码存在但没有执行（因为 `original_topic` 可能为空），需要另外确保每次探索完成后都有机会写入。

**备选方案**: 如果当前探索确实写入了 `children`，则此 bug 可以忽略。

---

## Bug #3: `explains` 字段完全为空

**严重程度**: P0
**影响**: 扩散激活只能向前追溯（parents），不能向后传播（explains），扩散效果减半

**根因**: `_update_parent_relation()` 存在但从未被调用，所以 `explains` 字段从未被写入

**验证**:
```bash
cd /root/dev/curious-agent
python3 -c "
from core.knowledge_graph import get_state
s = get_state()
topics = s['knowledge']['topics']
has_explains = sum(1 for t in topics.values() if t.get('explains'))
print(f'Topics with explains: {has_explains}/{len(topics)}')
"
# 期望: > 0
# 实际: 0
```

**修复**: 同 Bug #1，修复 `_update_parent_relation()` 的集成即可解决此问题。

---

## Bug #4: `async_explorer.py` 路径缺少 `add_child` 调用

**严重程度**: P1
**影响**: 异步探索路径（`async_explorer._explore_in_thread()`）不会建立父子关系

**根因**: 异步路径只调用了 `add_exploration_result()`，没有调用 `add_child()`

**验证**:
```bash
grep -n "add_child\|_update_parent_relation" /root/dev/curious-agent/core/async_explorer.py
# 期望: 有调用
# 实际: 无匹配
```

**修复要求**:

在 `core/async_explorer.py` 的 `_explore_in_thread()` 函数中，找到 `add_exploration_result()` 调用之后追加：

```python
    add_exploration_result(topic, result, quality)
    update_curiosity_status(topic, "done")

    # === v0.2.5 追加: 建立父子关系 ===
    # 异步探索：如果注入了 parent_topic 参数，需要建立关系
    # 由于异步探索通常是被外部注入，parent 关系由调用方保证
    # 此处暂时跳过，依赖 curious_agent 主流程保证
    # === v0.2.5 追加结束 ===
```

**说明**: 异步探索通常是外部注入（如 R1D3），parent 关系由 R1D3 注入时附带。如果有明确的 parent，需要在 `_explore_in_thread` 中记录。

---

## Bug #5: 扩散激活算法 `paths` 计算可能有问题

**严重程度**: P2
**影响**: `paths >= 2` 的根技术判断依赖路径数，但目前 KG 里所有 `paths` 都是 1

**验证**:
```bash
curl -s "http://localhost:4848/api/kg/trace/openclaw%20agent%20framework%20capabilities" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d['ordered_trace'])"
# 期望: 有节点的 paths > 1
# 实际: 所有节点的 paths = 1
```

**根因**: 在 `_update_parent_relation()` 被正确调用后，这个问题应该会自然解决。
如果同一个 child 被多个 parent 引用（多父节点），则该 child 的 `paths` 会大于 1。

**说明**: Bug #1 修复后重新验证。如果 Bug #1 修复后仍有问题，需要检查 `_update_parent_relation()` 中 `explains` 的写入逻辑。

---

## Bug #6: `children` 字段在 schema 里可能是 `None` 而不是 `[]`

**严重程度**: P1
**影响**: 如果 `children` 是 `None`，调用 `for child in node.get("children", [])` 会报错（None 无法迭代）

**验证**:
```bash
cd /root/dev/curious-agent
python3 -c "
from core.knowledge_graph import get_state
s = get_state()
topics = s['knowledge']['topics']
sample = list(topics.values())[0]
print('children type:', type(sample.get('children')))
print('children value:', sample.get('children'))
"
```

**修复**: 如果 `children` 为 `None`，在 `_update_parent_relation()` 和 `get_spreading_activation_trace()` 中需要做兼容处理：

```python
# 在 _update_parent_relation() 中
children_list = topics[parent].get("children") or []
for child in children_list:
    ...

# 在 get_spreading_activation_trace() 中
for child in (node.get("children") or []):
    ...
```

---

## 验证脚本

所有 bug 修复后，运行以下验证：

```bash
cd /root/dev/curious-agent

# 1. 验证 _update_parent_relation 已被调用
echo "=== 验证 _update_parent_relation ==="
grep -c "_update_parent_relation" core/knowledge_graph.py
# 期望: >= 2

# 2. 注入一个新话题并探索，观察父子关系
echo "=== 测试父子关系写入 ==="
curl -s -X POST "http://localhost:4848/api/curious/inject" \
  -H "Content-Type: application/json" \
  -d '{"topic":"test parent child bug","score":7.0,"depth":6.0}'
sleep 5
python3 -c "
import sys; sys.path.insert(0, '.')
from core.knowledge_graph import get_state
s = get_state()
topics = s['knowledge']['topics']
print('Topics with parents:', sum(1 for t in topics.values() if t.get('parents')))
print('Topics with explains:', sum(1 for t in topics.values() if t.get('explains')))
print('Topics with children:', sum(1 for t in topics.values() if t.get('children') or []))
"

# 3. 验证扩散激活
echo "=== 验证扩散激活 ==="
curl -s "http://localhost:4848/api/kg/trace/test%20parent%20child%20bug" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print('ordered_trace len:', len(d['ordered_trace'])); [print(' -', t['topic'], 'paths:', t['paths']) for t in d['ordered_trace'][:5]]"

# 4. 验证根技术浮现
echo "=== 验证根技术浮现 ==="
curl -s "http://localhost:4848/api/kg/roots" | python3 -c "import json,sys; d=json.load(sys.stdin); print('root count:', len(d['roots'])); [print(' -', r['name'], 'score:', r['root_score']) for r in d['roots'][:5]]"
```

---

## 修复顺序

1. **Bug #7（P0）** — 在 `curious_agent.py` 第 155 行附近，`update_curiosity_status(topic, "exploring")` 之后立即调用 `_update_parent_relation(parent, topic)`（仅当 `original_topic` 存在时）
2. **Bug #6（P1）** — 兼容 `children = None` 的情况
3. **Bug #4（P1）** — 异步路径确认是否需要 parent 写入
4. **Bug #1-5** — 已修复或随 Bug #7 自动解决

---

## Bug #7: `mark_topic_done` 的 parent 查找逻辑根本性缺陷（P0）

**严重程度**: P0
**发现时间**: 2026-03-27 by R1D3
**状态**: 未修复

**问题描述**:

`mark_topic_done(topic)` 中的 parent 查找逻辑是：
```python
for queue_item in state.get("curiosity_queue", []):
    if queue_item.get("status") == "exploring":
        parent_topic = queue_item.get("topic")
        if parent_topic and parent_topic != topic:
            _update_parent_relation(parent_topic, topic)
            break
```

但当前队列中**没有任何 `status=exploring` 的条目**——所有条目都是 `done` 或 `pending`。

验证：
```bash
curl -s http://localhost:4848/api/curious/state | python3 -c "
import json,sys; d=json.load(sys.stdin)
for item in d['curiosity_queue']:
    print(item['topic'], item['status'])
"
# 结果：全部是 done 或 pending，没有 exploring
```

**根因分析**：

curious_agent 的执行流程：
1. `next_curiosity = engine.select_next()` — 选出一个 topic 作为 child
2. `kg.update_curiosity_status(child, "exploring")` — child 标记为 exploring
3. 探索 child
4. `kg.mark_topic_done(child)` — 在这里查找时，child 已变成 done

问题在于：curious_agent 的 `select_next()` 选出的 topic 可能根本没有 parent 在队列里。如果有 parent，parent 已经在队列里以 `pending` 状态存在，从未被标记为 `exploring`。

**修复方案**：

在 `curious_agent.py` 中，当 child topic 被选出来之后、开始探索之前，**把 parent_topic 写入 child 的 queue item 里**：

在 `curious_agent.py` 的 `run_one_cycle()` 函数中，找到以下位置：

```python
# 大约在第 88 行
# Bug #26 fix: Explore parent topic first before decomposition
parent_state = state.get("knowledge", {}).get("topics", {}).get(topic, {})
if not parent_state.get("known"):
    ...
```

在这个逻辑之后，当 decomposition 发生时，child topic 被选中时，应该把 parent 信息写入队列。

**最简单的修复**：在 `curious_agent.py` 第 155 行附近添加 parent 追踪：

```python
# v0.2.5: 设置 exploring 状态以便 parent 追踪
kg.update_curiosity_status(topic, "exploring")

# === v0.2.5 追加: 如果有 original_topic（decomposed 出的 child），立即写入父子关系 ===
if "original_topic" in next_curiosity:
    parent = next_curiosity["original_topic"]
    if parent != topic:
        kg._update_parent_relation(parent, topic)
        print(f"[v0.2.5] Parent tracked: {parent} -> {topic}")
# === v0.2.5 追加结束 ===
```

这样，在 `mark_topic_done` 被调用之前，父子关系就已经写入了，`mark_topic_done` 里的查找逻辑即使失败也没关系。

**验证命令**：
```bash
curl -X POST "http://localhost:4848/api/curious/inject" \
  -H "Content-Type: application/json" \
  -d '{"topic":"test parent relation fix","score":7.0,"depth":6.0}'
sleep 2
curl -s -X POST "http://localhost:4848/api/curious/run" -H "Content-Type: application/json" -d '{"depth":"medium"}' > /dev/null
sleep 10
python3 -c "
import sys; sys.path.insert(0, '.')
from core.knowledge_graph import get_state
s = get_state()
topics = s['knowledge']['topics']
has_parents = sum(1 for t in topics.values() if t.get('parents'))
has_explains = sum(1 for t in topics.values() if t.get('explains'))
print(f'Topics with parents: {has_parents}/{len(topics)}')
print(f'Topics with explains: {has_explains}/{len(topics)}')
for name, t in topics.items():
    if t.get('parents'):
        print(f'  {name} -> parents: {t[\"parents\"]}')
"
```

---


---

## Bug #7 诊断更新（2026-03-27 晚）

**关键验证**：运行一轮新探索（"OMO multi-agent orchestration"）后，数据仍然是 parents=0, explains=0, children=0。

**根本原因（精确）**：

curious_agent.py 的主流程：
1. `select_next()` → 选出一个 pending topic
2. `update_curiosity_status(topic, "exploring")` → 该 topic 变为 exploring
3. decomposition 尝试 → 如果没有子话题，直接探索原 topic
4. `add_child(topic, explore_topic)` → **只在 decomposition 有结果时才调用**
5. `mark_topic_done(topic)` → 查找 `status == "exploring"` 的父 topic → **永远找不到**（exploring item 就是 topic 自己）

**mark_topic_done 里的逻辑错误**：
```python
for queue_item in state.get("curiosity_queue", []):
    if queue_item.get("status") == "exploring":
        parent_topic = queue_item.get("topic")  # ← 这就是 topic 自己！
        if parent_topic and parent_topic != topic:  # ← 永远 False
```

**方案A（推荐）**：在 curious_agent.py decomposition 之后，直接写入父子关系：
```python
# 在第 132 行 add_child 之后追加：
else:
    # decomposition 为空，直接探索原 topic
    if "original_topic" in next_curiosity:
        kg.add_child(next_curiosity["original_topic"], topic)
        kg._update_parent_relation(next_curiosity["original_topic"], topic)
```

**方案B**：修改 mark_topic_done 接收 parent_topic 参数。

_Last updated: 2026-03-27 by R1D3_
_v0.2.5: bug #7 diagnosis refined — mark_topic_done logic always fails_

---

## Bug #8: `_update_parent_relation` 创建不完整的 topic 结构（P1）

**严重程度**: P1
**发现时间**: 2026-03-27 by R1D3
**状态**: 未修复

**问题描述**:

`_update_parent_relation` 用 `setdefault(child, {})` 创建子 topic 时，只创建了包含 `parents` 字段的空 dict，没有初始化 `known`、`status`、`depth` 等必填字段：

```python
# 当前代码（错误）：
if "parents" not in topics.setdefault(child, {}):
    topics[child]["parents"] = []
```

`setdefault(child, {})` 创建的 dict 只有 `parents` 字段，导致：

**验证**：
```bash
cd /root/dev/curious-agent
python3 -c "
from core.knowledge_graph import get_state
s = get_state()
topics = s['knowledge']['topics']
for name, t in topics.items():
    if t.get('known') is None:
        print(f'{name}: known={t.get("known")}, status={t.get("status")}, fields={list(t.keys())}')
"
# 输出：child_test known=None, status=None
```

**根因**:

`add_child` 中创建新 topic 时会初始化完整结构：
```python
topics[parent] = {
    "known": False,
    "depth": 0,
    "children": [],
    ...
    "status": "partial"
}
```

但 `_update_parent_relation` 用的是裸 `setdefault`，缺少这些字段。

**修复方案**:

在 `_update_parent_relation` 里，如果 child 不存在，需要初始化完整结构：

```python
if child not in topics:
    topics[child] = {
        "known": False,
        "depth": 0,
        "parents": [],
        "explains": [],
        "children": [],
        "explored_children": [],
        "cross_domain_count": 0,
        "is_root_candidate": False,
        "root_score": 0.0,
        "first_observed": now,
        "last_updated": now,
        "status": "partial"
    }
else:
    # 只补全缺失的字段
    if "parents" not in topics[child]:
        topics[child]["parents"] = []
    if "explains" not in topics[child]:
        topics[child]["explains"] = []

# 对 parent 也做同样的处理
if parent not in topics:
    topics[parent] = {
        "known": False,
        "depth": 0,
        "parents": [],
        "explains": [],
        "children": [],
        "explored_children": [],
        "cross_domain_count": 0,
        "is_root_candidate": False,
        "root_score": 0.0,
        "first_observed": now,
        "last_updated": now,
        "status": "partial"
    }
else:
    if "explains" not in topics[parent]:
        topics[parent]["explains"] = []
```

**验证命令**：
```bash
python3 -c "
from core.knowledge_graph import get_state
s = get_state()
topics = s['knowledge']['topics']
incomplete = [n for n, t in topics.items() if t.get('known') is None]
print(f'Incomplete topics: {incomplete}')
# 期望：无输出（所有 topic 都有 known 字段）
```

