# v0.2.3 Bug List

> 2026-03-23 | 供 OpenCode 修改使用

---

## 🔴 Bug #1: Topic 注入后探索了完全不同的 topic

**现象**：
```bash
curl -X POST http://localhost:4848/api/curious/run \
  -d '{"topic": "OPENCODE测试xyz", "depth": "medium"}'
# 返回: status=success, topic=test_normalization（不是注入的 topic）
```

**根因**：`curious_api.py` 第 66-73 行，注入 topic 后用 `get_top_curiosities(k=1)` 取队列中评分最高的 pending 项，而非使用刚注入的 topic：

```python
add_curiosity(topic=topic, ...)
items = get_top_curiosities(k=1)           # ← 返回队列最高分项，不是注入的项
if items and items[0]["topic"] == topic:   # ← 几乎必然失败
    next_item = items[0]
else:
    return jsonify({"error": ...}), 500    # ← 或返回错误的 topic
```

注入 topic 评分通常低于队列已有项，所以 `items[0]` 几乎必然不是注入的 topic。

**修复方案**：删除 `get_top_curiosities` 逻辑，直接用注入 topic 构造 `next_item`：

```python
# 第 66-73 行替换为：
next_item = {
    "topic": topic,
    "reason": "API run injection",
    "score": final_score,
    "relevance": final_score,
    "depth": 7.0,
    "status": "pending"
}
```

**验证**：
```bash
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "OPENCODE测试专属topicXYZ", "depth": "medium"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'topic={d.get(\"topic\")}'); assert d.get('topic') == 'OPENCODE测试专属topicXYZ'"
# 期望：topic=OPENCODE测试专属topicXYZ
```

---

## 🔴 Bug #7: `completed_topics` 永远为空

**现象**：`/api/metacognitive/topics/completed` 返回 `[]`，但 exploration_log 中已有多个已探索 topic。

**根因**：`curious_agent.py` 第 192-197 行，`mark_topic_done()` 仅在 `continue_allowed=False` 时调用。但 `should_continue()` 在 marginal return >= 0.3 时几乎始终返回 True，导致 `mark_topic_done` 几乎永远不被触发。

```python
# curious_agent.py 第 192-197 行
continue_allowed, continue_reason = controller.should_continue(topic)

if continue_allowed:
    kg.add_curiosity(topic, ...)   # ← 继续探索，不标记完成
else:
    kg.mark_topic_done(topic, continue_reason)  # ← 几乎不会执行
```

**修复方案**：在 `explorer.explore()` 成功后，无论 `should_continue` 结果如何，都立即调用 `mark_topic_done()`：

```python
# curious_agent.py，在 explorer.explore() 成功后添加：
result = explorer.explore(next_curiosity)
# ... quality/marginal 计算 ...
kg.mark_topic_done(topic, f"Exploration done (Q={quality:.1f}, marginal={marginal:.2f})")
```

`curious_api.py` 第 81-82 行的调用已存在，确认未被删除。

**验证**：
```bash
curl -X POST http://localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "OPENCODE测试completed", "depth": "shallow"}'

curl http://localhost:4848/api/metacognitive/topics/completed \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'count={len(d.get(\"completed_topics\",[]))}'); assert len(d.get('completed_topics',[])) > 0"
# 期望：count >= 1
```

---

## 🟠 Bug #2: test shallow 分数 56.0（根因未知）

**现象**：历史队列中 `test shallow` 的 score=56.0，远超评分公式上限 ~8.0。

**根因**：未知。56.0 不可能由 `add_curiosity()` 的评分公式产生，疑似硬编码或直接写入 state.json 的测试数据。

**修复方案**：
1. 搜索代码中是否存在 `56.0` 硬编码
2. 检查 `knowledge/state.json` 中 `test shallow` 的来源记录
3. 如确认是测试遗留数据，直接从 state.json 中删除该项

**验证**：无明显分数异常的 topic 存在即可。

---

## 🟠 Bug #3: inject API 拒绝字符串 depth

**现象**：
```bash
curl -X POST http://localhost:4848/api/curious/inject \
  -d '{"topic": "测试", "depth": "medium"}'
# 返回: {"error": "could not convert string to float: 'medium'"}
```

**根因**：`curious_api.py` 第 154-159 行，已有字符串映射逻辑，但**运行的服务未加载最新代码**。

**修复方案**：确保 `curious_api.py` 第 154-159 行包含以下逻辑，并重启服务：

```python
depth = data.get("depth", 6.0)
if isinstance(depth, str):
    depth_map = {"shallow": 3.0, "medium": 6.0, "deep": 9.0}
    depth = depth_map.get(depth, 6.0)
else:
    depth = float(depth)
```

重启：
```bash
pkill -f curious_api.py; cd /root/dev/curious-agent && python3 curious_api.py &
```

**验证**：
```bash
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic": "OPENCODE测试depth", "depth": "medium"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status') == 'ok'"
# 期望：status=ok
```

---

## 🟠 Bug #4: DELETE queue 不接受 JSON body

**现象**：
```bash
curl -X DELETE http://localhost:4848/api/curious/queue \
  -H "Content-Type: application/json" \
  -d '{"topic": "test medium"}'
# 返回: {"error": "topic is required"}
```

**根因**：`curious_api.py` 第 227 行，`request.get_json()` 对 DELETE 方法可能返回 `{}`，导致 `topic` 取值永远为空。

**修复方案**：
```python
# 第 227 行替换为：
topic = request.args.get("topic", "") or (request.get_json() or {}).get("topic", "")
```

**验证**：
```bash
curl -X DELETE http://localhost:4848/api/curious/queue \
  -H "Content-Type: application/json" \
  -d '{"topic": "item1"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status') == 'success'"
# 期望：status=success
```

---

## 🟠 Bug #6: 中文 topic URL 参数乱码

**现象**：
```bash
curl "http://localhost:4848/api/metacognitive/check?topic=不存在的主题" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('topic'))"
# 返回: ä¸�å­å­£çä¸»é¢（乱码）
```

**根因**：`curious_api.py` 第 270 行，`request.args` 对 URL 参数使用 `latin-1` 解码，破坏 UTF-8 中文。

**修复方案**：
```python
# 第 270 行替换为：
topic = normalize_topic(request.values.get("topic", ""))
```

**验证**：
```bash
curl "http://localhost:4848/api/metacognitive/check?topic=测试中文topic" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); t=d.get('topic',''); assert '测试' in t or '中文' in t, f'BUG: {t}'"
# 期望：正确显示中文
```

---

## 🟡 Bug #8: KG topic 缺少 status 字段

**现象**：`/api/curious/state` 中部分 topic 的 `status` 字段不存在。

**根因**：`knowledge_graph.py` 的 `add_knowledge()` 新增 topic 时未初始化 `status` 字段。

**修复方案**：在 `add_knowledge()` 的 topic 初始化字典中添加 `"status": "partial"`。

**验证**：
```bash
curl -s http://localhost:4848/api/curious/state \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
for t, v in d.get('knowledge',{}).get('topics',{}).items():
    assert 'status' in v, f'BUG: {t} missing status'
print('All topics have status field')
"
```

---

## 📊 修复优先级

| 优先级 | Bug | 文件 | 验证断言 |
|--------|-----|------|---------|
| P0 | #1 Topic 注入错误 | `curious_api.py` | `topic == 'OPENCODE测试专属topicXYZ'` |
| P0 | #7 completed 为空 | `curious_agent.py` | `len(completed_topics) >= 1` |
| P1 | #2 分数 56.0 | 搜索代码 | 无异常分数 topic |
| P1 | #3 inject depth | `curious_api.py` + 重启 | `status == 'ok'` |
| P1 | #4 DELETE JSON body | `curious_api.py` | `status == 'success'` |
| P1 | #6 中文乱码 | `curious_api.py` | 中文正常显示 |
| P2 | #8 缺 status | `knowledge_graph.py` | 无 topic 缺字段 |
