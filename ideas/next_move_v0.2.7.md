# v0.2.7: 修复系统死锁 + 修复 Parent Link + QualityV2

## 背景

### 系统死锁诊断（2026-03-30）

```
curiosity_queue: 453 pending, 2 exploring, 0 done（持续积压）
    ↓
SpiderAgent 不消费 queue → 0 exploring
    ↓
没有探索完成 → 没有新发现
    ↓
DreamAgent 无法生成创意洞察 → DreamInbox 空
    ↓
SpiderAgent 没有东西可消费 → idle
    ↓
死锁循环
```

### 代码全量分析发现的 5 个独立根因

| # | 根因 | 文件 | 症状 |
|---|------|------|------|
| G1 | `claim_pending_item()` 不存在 | `knowledge_graph.py` | Phase 0 spec 白写，函数体缺失 |
| G2 | `_explore_in_thread` 缺少 `mark_topic_done` | `async_explorer.py` line 33-91 | Bug 2 未修复 |
| G3 | `add_exploration_result` typo + 逻辑颠倒 | `knowledge_graph.py` line 747 | Bug 4 未修复 |
| G4 | `knowledge_graph=None` 传入 QualityV2 | `async_explorer.py` line 49 | 所有节点 quality=0 |
| G5 | `api_inject` 无 parent link 写入 | `curious_api.py` | R1D3 inject 的父子关系丢失 |

### 4 Bug 串联（原始问题）

```
inject(topic, parent="Agent Harness")
    ↓ Bug 1: api_inject() 没有写 parent link
add_curiosity(topic, reason, score, depth)
    ↓ queue item 没有 original_topic（除非通过 **extra 传入）
trigger_async_exploration(topic, score, depth)
    ↓ 没有传 parent（Phase 2 设计）
_explore_in_thread(topic)
    ↓ 没有 mark_topic_done（Bug 2）
add_exploration_result(topic, result, quality)
    ↓ Bug 3+4: queue_item.get("topic") 获取的是当前探索的 topic
                不是 original_parent_topic，逻辑完全颠倒
```

---

## Phase 0：SpiderAgent 消费 curiosity_queue（紧急）

### 问题

SpiderAgent 的 `_process_inbox_cycle()` 只消费 DreamInbox，curiosity_queue 无人消费。daemon_mode() 里的 G2-Fix 每 60s 才消费一次，且不改变队列状态（没有 atomically claim）。

### 精确代码改动

#### Step 1: `core/knowledge_graph.py` 新增 `claim_pending_item()`

**位置**：在 `list_pending()` 函数下方（约 line 234 后）

```python
def claim_pending_item() -> Optional[dict]:
    """
    原子地 claim 一个 pending 项。
    只有 status=pending 的项才能被 claim。
    已 claiming 的项（status=exploring）会被跳过。
    
    注意：本函数不修改 DreamInbox，只修改 curiosity_queue 的 status。

    Returns:
        被 claim 的 item dict（status 已改为 exploring），或 None（队列为空）
    """
    state = _load_state()
    queue = state.get("curiosity_queue", [])
    for i, item in enumerate(queue):
        if item.get("status") == "pending":
            item["status"] = "exploring"
            _save_state(state)
            return item.copy()  # 返回副本，避免引用悬浮
    _save_state(state)
    return None
```

#### Step 2: `core/spider_agent.py` 修改 `_process_inbox_cycle()`

**位置**：约 line 70-84

**找到这段代码**：
```python
if not inbox_items:
    self._consecutive_empty_inbox += 1
    if self._consecutive_empty_inbox >= 5:
        print(f"[SpiderAgent] Warning: DreamInbox empty for {self._consecutive_empty_inbox} consecutive cycles")
        self._consecutive_empty_inbox = 0
    return
```

**替换为**：
```python
if not inbox_items:
    # === Phase 0 核心改动: DreamInbox 为空时立即从 curiosity_queue claim ===
    pending_item = kg.claim_pending_item()
    if pending_item:
        topic = pending_item["topic"]
        inbox_items.append({
            "topic": topic,
            "source_insight": "curiosity_queue_fallback"
        })
        print(f"[SpiderAgent] DreamInbox empty, claimed '{topic}' from curiosity_queue (status=exploring)")
        self._consecutive_empty_inbox = 0
        # 注意：不 return，继续处理刚 claim 的 item
    else:
        self._consecutive_empty_inbox += 1
        if self._consecutive_empty_inbox >= 5:
            print(f"[SpiderAgent] Warning: DreamInbox and curiosity_queue both empty for {self._consecutive_empty_inbox} cycles")
            self._consecutive_empty_inbox = 0
        return
    # === Phase 0 核心改动结束 ===
```

**注意**：原代码 `return` 前会执行 `self._consecutive_empty_inbox = 0`，但当从 queue claim 到 item 时，不应该 reset 计数器（一个周期内可能连续 claim 多个 item）。新代码在 `else` 分支才 +1，在 `if` 分支不 +1。

### 验收标准

- [ ] `python3 -c "from core import knowledge_graph as kg; print(kg.claim_pending_item())"` 能返回 pending 项且 status 变为 exploring
- [ ] 连续两次调用 `claim_pending_item()`，第二次返回 None（同一 item 不能被重复 claim）
- [ ] SpiderAgent DreamInbox 为空时，从 queue claim 到 item 并继续处理

---

## Phase 1：修复 QualityV2

### 问题

所有 KG 节点 quality=0 或 NONE，因为 `_explore_in_thread` 传了 `knowledge_graph=None` 给 QualityV2。

### 根因分析

`async_explorer.py` line 49:
```python
quality = quality_assessor.assess_quality(
    topic=topic,
    findings=findings_dict,
    knowledge_graph=None  # ← G4: 传入 None
)
```

QualityV2 的 `_get_previous_summary(topic, kg)` 内部：
```python
state = kg.get_state()  # ← kg 是 None，这里会抛 AttributeError
```

异常被 `except Exception: return ""` 吞掉，导致 `prev_summary` 永远是空字符串，语义新颖度永远是 1.0，信息增益评估也受影响。

### 精确代码改动

**文件**：`core/async_explorer.py`
**位置**：约 line 49

**找到这段代码**：
```python
quality = quality_assessor.assess_quality(
    topic=topic,
    findings=findings_dict,
    knowledge_graph=None
)
```

**替换为**：
```python
from core import knowledge_graph as kg_module
quality = quality_assessor.assess_quality(
    topic=topic,
    findings=findings_dict,
    knowledge_graph=kg_module  # G4-Fix: 传入 kg_module 实例，不是 None
)
```

### 诊断脚本（新建）

**文件**：`scripts/diagnose_quality_v2.py`

```python
#!/usr/bin/env python3
"""
诊断 QualityV2 评估器。

执行方式：
  cd /root/dev/curious-agent && python3 scripts/diagnose_quality_v2.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import knowledge_graph as kg
from core.quality_v2 import QualityV2Assessor
from core.llm_client import LLMClient

llm = LLMClient()
assessor = QualityV2Assessor(llm)

state = kg.get_state()
topics = state.get("knowledge", {}).get("topics", {})

# Step 1: 检查 KG 节点 content 分布
print("=== Step 1: KG 节点 content 分布 ===")
no_summary = [t for t, v in topics.items() if not v.get("summary")]
stub_kw = ["推理分析", "相关已有知识", "初步推断", "该领域"]
stub_topics = [t for t, v in topics.items() if any(kw in v.get("summary", "") for kw in stub_kw)]
with_content = [t for t, v in topics.items() if v.get("summary") and not any(kw in v.get("summary", "") for kw in stub_kw)]
print(f"  总节点: {len(topics)}")
print(f"  无 summary: {len(no_summary)}")
print(f"  Stub 节点: {len(stub_topics)}")
print(f"  有实质 content: {len(with_content)}")

# Step 2: 测试 QualityV2 对有 content 节点
print("\n=== Step 2: QualityV2 评估测试 ===")
if not with_content:
    print("  没有实质 content 的节点可测试（先跑一些探索）")
else:
    test_topic = with_content[0]
    v = topics[test_topic]
    findings = {"summary": v["summary"], "sources": v.get("sources", [])}
    print(f"  测试 topic: {test_topic}")
    print(f"  summary length: {len(findings['summary'])}")

    try:
        quality = assessor.assess_quality(test_topic, findings, kg)
        print(f"  QualityV2 返回: {quality}")
        if quality == 0:
            print("  ⚠️ 返回 0，评分逻辑有问题")
        elif quality > 0:
            print(f"  ✅ 正常，质量分 {quality}")
    except Exception as e:
        print(f"  ⚠️ QualityV2 异常: {e}")

# Step 3: quality 分布
print("\n=== Step 3: KG quality 分布 ===")
quality_buckets = {"0": 0, "0.1-5": 0, "5.1-8": 0, ">8": 0, "NONE": 0}
for t, v in topics.items():
    q = v.get("quality")
    if q is None or q == 0:
        quality_buckets["0"] += 1
    elif q <= 5:
        quality_buckets["0.1-5"] += 1
    elif q <= 8:
        quality_buckets["5.1-8"] += 1
    else:
        quality_buckets[">8"] += 1
for k, v in quality_buckets.items():
    print(f"  {k}: {v}")
```

### 验收标准

- [ ] `python3 scripts/diagnose_quality_v2.py` 能正常执行并输出诊断结果
- [ ] QualityV2 对有 content 的节点返回 > 0 的质量分（修复后新探索的节点）

---

## Phase 2：parent link 在入口写入 KG

### 问题

`api_inject()` 收到 `parent` 参数时，只调用了 `add_curiosity()` 入队列，没有建立 KG 父子关系，导致 R1D3 inject 的树状结构丢失。

### KG 数据结构（当前实现）

节点结构（`knowledge.topics[topic]`）：
```python
{
    "children": list[str],    # 我分解出的子 topic
    "parents": list[str],     # 分解出我的父 topic
    "explains": list[dict],   # 我解释了谁（与 parents 反向）
    ...
}
```

`add_child(parent, child)` 操作：双向写入 `children` 和 `parents`。

### 精确代码改动

**文件**：`curious_api.py`
**位置**：约 line 168-175（`add_curiosity()` 调用之后，priority trigger 之前）

**找到这段代码**：
```python
        add_curiosity(
            topic=topic,
            reason=str(data.get("reason", "Web UI 注入")),
            relevance=final_score,
            depth=depth
        )

        # ===== T-9 集成点 开始 =====
```

**在 `add_curiosity()` 调用**之后、T-9 集成点**之前**，插入：

```python
        # === Phase 2: parent link 在入口处立即写入 KG ===
        parent = data.get("parent")
        if parent:
            # Step 1: 建占位 KG 节点（即使还没探索，KG 里也要有记录）
            kg.add_knowledge(topic=topic, depth=depth, summary="")
            # Step 2: 立即建立父子关系
            kg.add_child(parent, topic)
            print(f"[Phase2] Linked '{topic}' -> '{parent}' in KG")
        # === Phase 2 结束 ===

        add_curiosity(
            topic=topic,
            reason=str(data.get("reason", "Web UI 注入")),
            relevance=final_score,
            depth=depth
        )

        # ===== T-9 集成点 开始 =====
```

**完整 import**：文件顶部已有 `from core import knowledge_graph as kg_module`，curious_api.py 用的是 `from core.knowledge_graph import add_curiosity`。需要在文件顶部确认 `kg` alias 或用全称 `from core import knowledge_graph as kg_module`。实际上，文件顶部已有 `from core.knowledge_graph import add_curiosity`，但 `add_knowledge` 和 `add_child` 尚未 import。检查后发现 `from core import knowledge_graph as kg_module` 在 `api_inject` 函数内部也有。所以改动如下：

```python
        from core import knowledge_graph as kg_module  # 确保在函数内可用
        parent = data.get("parent")
        if parent:
            kg_module.add_knowledge(topic=topic, depth=depth, summary="")
            kg_module.add_child(parent, topic)
            print(f"[Phase2] Linked '{topic}' -> '{parent}' in KG")
```

### 验收标准

- [ ] `curl -X POST http://localhost:4848/api/curious/inject -H "Content-Type: application/json" -d '{"topic":"Guardrails schema enforcement","parent":"Agent Harness","source":"r1d3"}'` 后，KG 立即有 `Agent Harness` 节点的 `children` 包含 `"Guardrails schema enforcement"`
- [ ] 同时 `Guardrails schema enforcement` 节点的 `parents` 包含 `"Agent Harness"`
- [ ] 旧 inject（无 parent）仍正常工作

---

## Phase 3：Bug 2 修复 + async 路径 status 一致性

### 问题 1：Bug 2 — `_explore_in_thread` 没有调 `mark_topic_done`

**文件**：`core/async_explorer.py`
**位置**：约 line 91（在 `logger.info` 之后，`except` 之前）

实际上 `_explore_in_thread` 末尾已经有 `update_curiosity_status(topic, "done")`（line 90）。但问题是：**队列项的 status 从未来 "exploring" 变成 "done"**，因为 `trigger_async_exploration` 从未把队列项改为 "exploring"。

Phase 0 的 `claim_pending_item()` 会将队列项 status 从 `pending` 改为 `exploring`，所以当 SpiderAgent claim 了一个 item 后，该 item 的 status 已经是 `exploring`。但 `trigger_async_exploration` 是直接开线程，不走 `claim_pending_item()`，所以 async 路径的队列项 status 始终是 `pending`。

### 问题 2：async 路径没有 status 更新

`trigger_async_exploration` → `_explore_in_thread` → `explorer.explore()` → `add_exploration_result` → `update_curiosity_status(topic, "done")`

这个链条在**正常完成**时会调 `update_curiosity_status(topic, "done")`，但：
- 如果 `explorer.explore()` 抛出异常？会被 except 捕获，然后 `update_curiosity_status(topic, "paused")`
- 如果 `_explore_in_thread` 在 `explorer.explore()` 之前就失败了？队列项 status 仍是 `pending`

### 精确代码改动

**文件**：`core/async_explorer.py`
**位置**：在 `_explore_in_thread` 函数开头，`explorer, quality_assessor = _get_instances(depth)` 之前

```python
def _explore_in_thread(topic: str, score: float, depth: float):
    """在线程中执行探索，完成后更新状态"""
    # === Phase 3: async 路径也要正确更新队列 status ===
    from core.knowledge_graph import update_curiosity_status
    try:
        update_curiosity_status(topic, "exploring")
    except Exception:
        pass  # 不因为 status 更新失败而阻止探索
    # === Phase 3 结束 ===
    
    try:
        logger.info(f"[T-10] Async exploration started for {topic} (depth={depth})")
        explorer, quality_assessor = _get_instances(depth)
        # ... 后续不变 ...
```

### 验收标准

- [ ] R1D3 inject 后，队列项 status 正确经历 `pending → exploring → done`
- [ ] 如果 async 线程异常退出，status 变为 `paused`（不是 pending）

---

## Phase 4：Bug 3+4 修复 — `add_exploration_result` typo + 逻辑修复

### 问题

`add_exploration_result` 中的这段代码：
```python
for queue_item in state.get("curiosity_queue", []):
    if queue_item.get("status") == "exploring":
        parent_topic = queue_item.get("topic")  # ← Bug: 获取的是当前探索的 topic，不是 parent
```

当 `_explore_in_thread` 完成时：
- 如果是 SpiderAgent 通过 DreamInbox 触发的探索：curiosity_queue 里的 status 可能还是 `pending`（SpiderAgent 走的是 DreamInbox，没有 claim）
- 如果是 async trigger 触发的探索：status 可能是 `done`（最后调了 `update_curiosity_status(topic, "done")`）
- 无论如何，`queue_item.get("topic")` 在这里拿到的是**当前探索完成的 topic**，不是 parent

### 修复方案

Phase 2 已经把 parent link 在入口处写入了 KG（`add_child(parent, topic)`），所以这里**不需要再从队列推断 parent**。删除这段从队列找 parent 的逻辑：

**文件**：`core/knowledge_graph.py`
**位置**：约 line 746-750

**找到这段代码**：
```python
    # v0.2.5: parent 写入 - 从 curiosity_queue 获取正在探索的 parent
    state = _load_state()
    for queue_item in state.get("curiosity_queue", []):
        if queue_item.get("status") == "exploring":
            parent_topic = queue_item.get("topic")
            if parent_topic and parent_topic != topic:
                _update_parent_relation(parent_topic, topic)
                break
```

**替换为**：
```python
    # v0.2.7 Phase 4: parent link 已在 api_inject() 入口处通过 add_child() 写入 KG，
    # 不需要再从队列推断。此段逻辑删除以避免 Bug 3+4（queue_item.get("topic")
    # 拿到的是当前探索完成的 topic，不是 parent，逻辑颠倒）。
    pass
```

### 验收标准

- [ ] `grep -n "parent_topic = queue_item" core/knowledge_graph.py` 不再找到该行
- [ ] `grep -n "v0.2.5: parent 写入" core/knowledge_graph.py` 找到 Phase 4 的 pass 和注释

---

## Phase 5：backfill 历史数据（依赖 Phase 1）

### 问题

修复 QualityV2（G4）后，历史节点 quality 仍为 0，需要重新评估。

### 脚本（新建）

**文件**：`scripts/backfill_quality.py`

```python
#!/usr/bin/env python3
"""
Backfill quality scores for KG nodes with quality=0 or quality=NONE.

运行方式：
  cd /root/dev/curious-agent && python3 scripts/backfill_quality.py

依赖：Phase 1 修复后（QualityV2 能返回 > 0 的分）
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import knowledge_graph as kg
from core.quality_v2 import QualityV2Assessor
from core.llm_client import LLMClient

llm = LLMClient()
assessor = QualityV2Assessor(llm)

state = kg.get_state()
topics = state.get("knowledge", {}).get("topics", {})

stub_kw = ["推理分析", "相关已有知识", "初步推断", "该领域"]

need_backfill = []
skipped_stub = []
skipped_no_content = []

for topic, node in topics.items():
    q = node.get("quality")
    summary = node.get("summary", "")

    if not summary or len(summary) < 50:
        skipped_no_content.append(topic)
        continue

    if any(kw in summary for kw in stub_kw):
        skipped_stub.append(topic)
        continue

    if q is None or q == 0:
        need_backfill.append(topic)

print(f"需要 backfill: {len(need_backfill)} 个节点")
print(f"跳过（无 content）: {len(skipped_no_content)} 个节点")
print(f"跳过（stub）: {len(skipped_stub)} 个节点")

updated = 0
errors = 0
for topic in need_backfill:
    node = topics[topic]
    summary = node.get("summary", "")
    findings = {"summary": summary, "sources": node.get("sources", [])}

    try:
        quality = assessor.assess_quality(topic, findings, kg)
        if quality > 0:
            kg.update_topic_quality(topic, quality)
            updated += 1
            print(f"  [OK] {topic[:50]}: Q={quality:.1f}")
        else:
            print(f"  [WARN] {topic[:50]}: Q={quality} (still 0)")
    except Exception as e:
        errors += 1
        print(f"  [ERROR] {topic[:50]}: {e}")

print(f"\n完成: {updated}/{len(need_backfill)} 节点更新了正质量分，{errors} 个错误")
```

### 验收标准

- [ ] `python3 scripts/backfill_quality.py` 执行后，KG 中 quality > 0 的节点数增加
- [ ] stub 节点没有被错误 backfill

---

## 回归验收（所有 Phase 完成后）

- [ ] DAEMON 重启后 SpiderAgent + DreamAgent + SleepPruner 全部运行
- [ ] `python3 -u curious_agent.py --daemon` 运行 5 分钟无报错
- [ ] 旧 inject 和 queue 操作（`--inject`, `--list-pending`, `--delete`）正常工作
- [ ] `python3 -c "from core import knowledge_graph as kg; print(kg.claim_pending_item())"` 能返回 pending 项
- [ ] R1D3 inject 带 parent 参数后，KG 树状结构正确建立

---

## 文件变更清单

```
新增:
  scripts/diagnose_quality_v2.py    # Phase 1 诊断工具
  scripts/backfill_quality.py       # Phase 5 backfill 工具

修改:
  core/knowledge_graph.py           # Phase 0: claim_pending_item() + Phase 4: 删除 parent 推断逻辑
  core/spider_agent.py              # Phase 0: _process_inbox_cycle() 改 DreamInbox 空时消费 queue
  core/async_explorer.py            # Phase 1: knowledge_graph=None → kg_module + Phase 3: status 更新
  curious_api.py                    # Phase 2: api_inject() 加 add_child + add_knowledge

无变更:
  core/explorer.py                  # explore() 签名不变
  core/dream_agent.py              # 独立
  core/sleep_pruner.py             # 独立
  curious_agent.py                  # daemon_mode 的 G2-Fix 冗余但无害（Phase 0 后 SpiderAgent 自己吃 queue）
  three_phase_explorer.py          # 独立包装器
  core/quality_v2.py               # 无需改动（bug 在调用方）
```

---

## 部署步骤

1. 停止 DAEMON 和 API
2. 备份 `knowledge/state.json`
3. 替换代码文件
4. 启动 API: `python3 -u curious_api.py &`
5. 验证 Phase 0: `python3 -c "from core import knowledge_graph as kg; print(kg.claim_pending_item())"`
6. 启动 DAEMON: `python3 -u curious_agent.py --daemon`
7. 运行 Phase 1 诊断: `python3 scripts/diagnose_quality_v2.py`
8. 运行 Phase 5 backfill（如果诊断显示大量节点需要）: `python3 scripts/backfill_quality.py`

---

## 风险清单

| 风险 | 严重程度 | 缓解方案 |
|------|----------|---------|
| Phase 0 `claim_pending_item` 和 `fetch_and_clear_dream_inbox` 并发写 state.json | 🟡 | JSON 文件级竞争，接受（两条路径不会同时写同一个字段） |
| Phase 5 backfill 耗尽 API quota | 🟡 | stub 节点不重评，有实质 content 的才重评 |
| `api_inject` 里 `add_knowledge` 建占位节点但探索失败，留下孤岛节点 | 🟡 | Phase 5 backfill 时这些节点 quality=0，可识别 |
| Phase 2 `add_child` parent 不存在时，`add_child` 内部会创建 stub parent | ✅ 已知行为 | 可接受 |
