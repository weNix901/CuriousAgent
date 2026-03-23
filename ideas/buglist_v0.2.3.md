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

---

## 🔴 Bug #11: Agent-Behavior-Writer._classify_discovery 只支持英文关键词，中文 topic 全部跳过写入

**现象**：
```python
# 测试发现
writer = AgentBehaviorWriter()
findings = {'summary': '大语言模型具备自主规划和推理能力'}
result = writer.process('大语言模型推理规划', findings, quality=8.0, sources=[])
# 返回: {'applied': False, 'reason': 'discovery type not actionable'}
```

所有中文 topic 的探索结果都无法被写入 `curious-agent-behaviors.md`，Phase 1 行为闭环完全失效。

**根因**：`agent_behavior_writer.py` 第 90-110 行，`_classify_discovery` 方法使用硬编码的英文关键词列表做匹配：

```python
# agent_behavior_writer.py 第 90-110 行（当前代码）
def _classify_discovery(self, topic: str, findings: dict) -> str:
    topic_lower = topic.lower()
    if any(k in topic_lower for k in [
        "metacognition", "self-monitoring", "self-reflection",
        "self-assessment", "monitor-generate", "self-verification"
    ]):
        return "metacognition_strategy"
    if any(k in topic_lower for k in [
        "reasoning", "planning", "chain-of-thought", "cot", "reflexion"
    ]):
        return "reasoning_strategy"
    # ... 其他分类全部是英文关键词
    return None  # ← 中文 topic 全部返回 None
```

Curious Agent 的 topic 全是中文（如"大语言模型推理规划"、"自主意识型 Agent"），匹配不到任何英文关键词 → 返回 `None` → `process()` 返回 `"discovery type not actionable"` → behavior 文件永不写入。

**✅ 期望的正确结果**：
- 中文 topic 能被正确分类为对应类型
- 分类应基于**语义**而非关键词匹配
- 质量 ≥ 7.0 的探索结果应该被写入 behavior 文件（不只是英文 topic）

**✅ 建议的修复方式**：

**方案 A（推荐）：LLM Zero-Shot 分类**

不依赖关键词，在 `_classify_discovery` 中调用 LLM 做 zero-shot 分类：

```python
def _classify_discovery(self, topic: str, findings: dict) -> str | None:
    """
    用 LLM 做 zero-shot 分类，基于 topic + summary 语义判断发现类型。
    避免依赖特定语言或关键词。
    """
    # 候选类型
    TYPES = [
        "metacognition_strategy",   # 元认知：自我监控、反思、self-assessment
        "reasoning_strategy",      # 推理策略：chain-of-thought、planning、reflexion
        "confidence_rule",          # 置信度规则
        "self_check_rule",         # 自我检查/验证规则
        "proactive_behavior",      # 主动行为：好奇心驱动、探索
        "tool_discovery",          # 工具发现：framework、library、sdk
    ]

    prompt = f"""请判断以下探索发现属于哪种类型：

Topic: {topic}
Summary: {findings.get('summary', '')[:200]}

可选类型：{', '.join(TYPES)}

请直接输出最匹配的类型名称（只输出类型名，不要解释）。如果无法判断，输出 "unknown"。
"""

    response = self._llm_client.chat(prompt).strip()
    if response in TYPES:
        return response
    return None  # 无法分类时不写入，不阻塞探索
```

**方案 B：中文关键词补充**

在现有英文关键词基础上增加中文映射表：

```python
TYPE_KEYWORDS = {
    "metacognition_strategy": ["元认知", "自我监控", "自我反思", "self-reflection", "metacognition"],
    "reasoning_strategy": ["推理", "规划", "思维链", "chain-of-thought", "reasoning"],
    "tool_discovery": ["框架", "工具", "framework", "library", "sdk"],
    "proactive_behavior": ["好奇心", "主动", "探索", "curiosity", "proactive"],
}
```

**✅ 额外建议：评估信息完整性**

在分类后，可增加一步 LLM 评估，确保 findings 信息完整无歧义再写入：

```python
def _evaluate_findings_quality(self, topic: str, findings: dict) -> tuple[bool, str]:
    """
    评估发现信息是否完整、无歧义。
    返回 (can_write, reason)
    """
    prompt = f"""评估以下探索发现的信息质量：

Topic: {topic}
Summary: {findings.get('summary', '')}

请判断：
1. 信息是否完整（不是碎片）？
2. 是否有歧义或模糊表述？
3. 是否可以直接转化为行为规则？

回答格式：PASS - 信息完整 / FAIL - 原因
"""
    response = self._llm_client.chat(prompt).strip()
    if response.startswith("PASS"):
        return True, "信息完整"
    return False, response
```

**验证**：
```python
from core.agent_behavior_writer import AgentBehaviorWriter

writer = AgentBehaviorWriter()
findings = {'summary': '大语言模型具备自主规划和推理能力，可以作为Agent的核心认知引擎'}
result = writer.process('大语言模型推理规划', findings, quality=8.0, sources=['https://example.com'])
print(result)
# 期望: {'applied': True, 'section': '## 🧠 推理策略', ...}
# 检查 curious-agent-behaviors.md 是否有新内容写入
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
| 🆕 待修复 | #11 | 中文 topic 无法写入 behavior 文件（分类器只认英文关键词） | `agent_behavior_writer.py` L90-110 |

---

## 🆕 v0.2.4 计划修复（待确认）

| 优先级 | 方向 | 说明 |
|--------|------|------|
| P0 | Bug #1/#9/#10 | 本文档所列三个 Bug |
| P1 | 队列清理机制 | 定期清理 old + blocked topic，防止队列污染 |
| P2 | 并行探索 | 支持多 topic 同时探索 |
