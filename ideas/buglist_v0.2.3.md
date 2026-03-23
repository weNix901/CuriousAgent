# v0.2.3 Bug List（最终版）

> 2026-03-23 全面核查 | 验证时间：2026-03-23 17:44

---

## 🔴 Bug #1: Topic 注入后探索了完全不同的 topic

**现象**：
```bash
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "OPENCODE测试xyz", "depth": "medium"}'
# 返回: status=success, topic=test_normalization（不是注入的 topic）
```

**根因**：`curious_api.py` 第 175-193 行，注入 topic 后用 `get_top_curiosities(k=1)` 取队列中评分最高的 pending 项，而非使用刚注入的 topic：

```python
# curious_api.py 第 175-193 行（当前代码）
add_curiosity(topic=topic, reason="API trigger", relevance=8.0, depth=7.0)
time_module.sleep(0.5)
items = get_top_curiosities(k=1)           # ← 返回队列最高分项，不是注入的项
if items and items[0]["topic"] == topic:   # ← 注入 topic 评分通常低于队列已有项，几乎必然失败
    engine = CuriosityEngine()
    explorer = Explorer(exploration_depth=depth)
    result = explorer.explore(items[0])
```

注入 topic 的 relevance=8.0，但仍可能低于队列已有项，所以 `items[0]` 几乎必然不是注入的 topic，导致分支走向错误路径或返回错误的 topic。

**✅ 期望的正确结果**：
- 注入 topic="OPENCODE测试xyz" → 实际探索的 topic 必须等于 "OPENCODE测试xyz"
- API 返回的 `topic` 字段与注入的 topic 完全一致
- 不受队列中已有 topic 评分高低的影响

**✅ 建议的修复方式**：
删除 `get_top_curiosities` 逻辑，直接用注入 topic 构造探索项并执行：

```python
# 第 175-193 行替换为：
engine = CuriosityEngine()
explorer = Explorer(exploration_depth=depth)
next_item = {
    "topic": topic,
    "reason": "API run injection",
    "score": 8.0,
    "relevance": 8.0,
    "depth": 7.0,
    "status": "pending"
}
result = explorer.explore(next_item)
print(f"[Async] Exploration completed: {topic}, notified: {result.get('notified', False)}")
```

**验证**：
```bash
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "OPENCODE测试专属topicXYZ", "depth": "medium"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'topic={d.get(\"topic\")}'); assert d.get('topic') == 'OPENCODE测试专属topicXYZ'"
# 期望：topic=OPENCODE测试专属topicXYZ
```

**移交 OpenCode**：✅ 可移交

---

## 🔴 Bug #9: CLI `--run` 访问 blocked 状态的 `result["formatted"]` 键导致 KeyError

**现象**：
```bash
python3 curious_agent.py --run --pure-curious
# 输出: KeyError: 'formatted'（当队列中只有已 blocked 的 topic 时）
```

**根因**：`curious_agent.py` 第 381-383 行，CLI 处理 `--run` 时只处理了 `idle` 状态，其他状态无条件访问 `"formatted"` 键，但 `blocked` 状态的返回结果中没有此键：

```python
# curious_agent.py 第 381-383 行（当前代码）
if result["status"] == "idle":
    print(f"💤 {result['message']}")
else:
    print(result["formatted"])   # ← blocked 状态没有 "formatted" 键，KeyError
```

**✅ 期望的正确结果**：
- `status=idle` → 打印 `"💤 {message}"`（当前已支持）
- `status=blocked` → 打印 `"🚫 {topic} blocked: {reason}"`（不崩溃）
- `status=clarification_needed` → 打印 `"🤔 需要澄清: {topic} — {reason}"`
- `status=success` → 打印探索结果 formatted 内容
- **任何状态都不应该抛出 KeyError**

**✅ 建议的修复方式**：
在 CLI main 函数中完整处理各状态，对 `blocked` 和 `clarification_needed` 使用 `result.get()` 安全读取：

```python
# 第 381-383 行替换为：
if result["status"] == "idle":
    print(f"💤 {result['message']}")
elif result["status"] == "blocked":
    print(f"🚫 {result['topic']} blocked: {result.get('reason', 'unknown')}")
elif result["status"] == "clarification_needed":
    print(f"🤔 需要澄清: {result.get('topic')} — {result.get('reason', '')}")
else:
    print(result.get("formatted", ""))
```

**验证**：
```bash
# 手动将一个 topic 设为 blocked 状态后运行
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic": "test_blocked_topic", "depth": "shallow"}'

# 将该 topic 在 state.json 中手动改为 blocked（模拟场景）
# 然后运行
python3 curious_agent.py --run --pure-curious 2>&1 | grep -i "keyerror\|blocked\|formatted"
# 期望：无 KeyError，出现 blocked 提示或正常输出
```

**移交 OpenCode**：✅ 可移交

---

## 🔴 Bug #10: 分解后父 topic 未标记完成导致下一轮重复被选（死循环）

**现象**：`--pure-curious` 模式下，连续两轮选择相同的父 topic，产生相同的子 topic，已探索过的子 topic 被再次选中后 blocked，形成死循环：

```
[Decomposer] 'AI Agent' -> '大语言模型推理与规划' (medium)
✅ 完成: 大语言模型推理与规划
[Decomposer] 'AI Agent' -> '大语言模型推理与规划' (medium)   ← 再次选中同一个父 topic！
✅ 完成: 大语言模型推理与规划
[Decomposer] 'AI Agent' -> '大语言模型推理与规划' (medium)   ← 循环继续
```

**根因**：`curious_agent.py` 第 85-95 行，Decomposer 将父 topic 分解为子 topic 后：

1. 设置 `next_curiosity["original_topic"] = topic`（记录父 topic）
2. 将子 topic 作为 `next_curiosity["topic"]` 进行探索
3. **但从未调用 `kg.mark_topic_done(topic, ...)` 标记父 topic 为已完成**

下一轮 `select_next()` 再次选择同一个父 topic，再次分解，产生相同子 topic，无限循环。

```python
# curious_agent.py 第 85-95 行（当前代码）
if subtopics:
    best = max(subtopics, key=lambda x: x.get("total_count", 0))
    explore_topic = best["sub_topic"]
    print(f"[Decomposer] '{topic}' -> '{explore_topic}' ...")
    next_curiosity["original_topic"] = topic   # ← 记录了父 topic
    next_curiosity["topic"] = explore_topic   # ← 但没有标记父 topic 已完成
    next_curiosity["decomposition"] = best
```

**✅ 期望的正确结果**：
- 父 topic 被 Decomposer 分解后，该父 topic 立即被标记为 `status=done` 或 `status=exploring`
- 父 topic 不再出现在 `get_top_curiosities(k=N)` 的返回结果中（即 `select_next()` 不会再次选中它）
- 每轮探索产生的是**不同的**父 topic 或**不同的**子 topic，不会重复处理同一父 topic

**✅ 建议的修复方式**：
在分解成功且有子 topic 时，调用 `kg.mark_topic_done()` 将父 topic 标记为已完成，防止下一轮被再次选中：

```python
# 第 85-95 行中，在设置 next_curiosity 后添加一行：
if subtopics:
    best = max(subtopics, key=lambda x: x.get("total_count", 0))
    explore_topic = best["sub_topic"]
    print(f"[Decomposer] '{topic}' -> '{explore_topic}' ...")
    next_curiosity["original_topic"] = topic
    next_curiosity["topic"] = explore_topic
    next_curiosity["decomposition"] = best
    # 👇 新增：标记父 topic 已完成，防止下一轮重复选择
    kg.mark_topic_done(topic, f"Decomposed into: {explore_topic}")
```

**验证**：
```bash
# 运行 --pure-curious 两轮，检查父 topic 是否只被选一次
python3 curious_agent.py --run --pure-curious 2>&1 | grep "Decomposer"
# 第一轮应该看到：[Decomposer] 'XXX' -> '子topic'
# 第二轮应该看到不同的父 topic，或看到 Decomposer 针对不同父 topic

# 或者直接检查 KG state
python3 -c "
import sys; sys.path.insert(0, '.')
from core.knowledge_graph import KnowledgeGraph
kg = KnowledgeGraph()
state = kg.get_state()
# 找所有带 original_topic 的项（子 topic）
for item in state.get('curiosity_queue', []):
    if item.get('original_topic'):
        print(f'Child: {item[\"topic\"]}, Parent: {item[\"original_topic\"]}, status: {item.get(\"status\")}')
# 期望：同一个父 topic 最多只产生一个带 original_topic 的子 topic
" 2>/dev/null
```

**移交 OpenCode**：✅ 可移交

---

## 📊 Bug 状态总览

| 状态 | Bug | 描述 | 文件 |
|------|-----|------|------|
| ✅ 已修复（2026-03-23 核查） | #2 | test shallow 分数 56.0（脏数据已清理） | - |
| ✅ 已修复（2026-03-23 核查） | #3 | inject API 拒绝字符串 depth | `curious_api.py` L126-128 |
| ✅ 已修复（2026-03-23 核查） | #4 | DELETE queue 不接受 JSON body | `curious_api.py` L228-229 |
| ✅ 已修复（2026-03-23 核查） | #6 | 中文 topic URL 参数乱码 | `curious_api.py` L282 `normalize_topic` |
| ✅ 已修复（2026-03-23 核查） | #7 | `completed_topics` 永远为空 | `curious_agent.py` L131 |
| ✅ 已修复（2026-03-23 核查） | #8 | KG topic 缺少 status 字段 | `knowledge_graph.py` L351 |
| ✅ 已修复（OpenCode 2026-03-23） | #1 | Topic 注入后探索了完全不同的 topic | `curious_api.py` L189-197 |
| ✅ 已修复（OpenCode 2026-03-23） | #9 | CLI `--run` blocked 状态 KeyError | `curious_agent.py` L383-388 |
| ✅ 已修复（OpenCode 2026-03-23） | #10 | 分解后父 topic 重复被选导致死循环 | `curious_agent.py` L95 |

---

## 🆕 v0.2.4 计划修复（待确认）

| 优先级 | 方向 | 说明 |
|--------|------|------|
| P0 | Bug #1/#9/#10 | 本文档所列三个 Bug |
| P1 | 队列清理机制 | 定期清理 old + blocked topic，防止队列污染 |
| P2 | 并行探索 | 支持多 topic 同时探索 |
