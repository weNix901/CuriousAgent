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
grep -n "add_child" /root/dev/curious-agent/core/async_explorer.py
# 期望: 有调用
# 实际: 无匹配
```

**修复要求**:

在 `core/async_explorer.py` 的 `_explore_in_thread()` 函数末尾（`add_exploration_result()` 调用之后）追加：

```python
def _explore_in_thread(topic: str, score: float, depth: float):
    # ... 现有代码 ...
    
    # === v0.2.5 追加: 建立父子关系 ===
    # 异步探索的 parent 是当前正在探索的 topic
    # 注意: 异步探索通常是自己被注入，不需要建立父子关系
    # 但如果是从某个 parent decomposed 出来的，需要记录
    # 此处暂时跳过，依赖 mark_topic_done() 中的逻辑处理
    pass
    # === v0.2.5 追加结束 ===
```

**说明**: 异步探索通常是外部注入，不一定有明确的 parent，暂时跳过。parent 关系主要通过 `mark_topic_done()` 从 `curiosity_queue` 中查找。

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

1. **Bug #1** — 修复 `_update_parent_relation()` 在 `add_child()` 和 `mark_topic_done()` 中的集成（P0）
2. **Bug #2** — 验证 `add_child()` 在 `curious_agent.py` 中是否被调用（P0）
3. **Bug #6** — 兼容 `children = None` 的情况（P1）
4. **Bug #3** — Bug #1 修复后自动解决
5. **Bug #4** — 确认异步路径是否需要 parent 写入（P1）
6. **Bug #5** — Bug #1 修复后重新验证

---

_Last updated: 2026-03-27 by R1D3_
