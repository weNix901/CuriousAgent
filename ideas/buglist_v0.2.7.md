# Buglist v0.2.7 - 2026-03-30/31

## 背景：系统死锁

curious-agent 自 2026-03-30 陷入死锁状态：

```
curiosity_queue: 453+ pending, 持续积压
    ↓
SpiderAgent 从不消费 queue → 0 exploring
    ↓
没有探索完成 → 没有新发现
    ↓
DreamAgent 无法生成创意洞察 → DreamInbox 空
    ↓
SpiderAgent 没有东西可消费 → idle
    ↓
死锁循环
```

**系统现状**：
- curiosity_queue 持续积压（453 → 436 → 354，仍在增长）
- SpiderAgent idle（0 exploring, 0 done，从不消费 curiosity_queue）
- KG quality 字段全为 0 或 NONE（QualityV2 损坏）
- R1D3 inject 的树状结构丢失（parent link 未写入 KG）

---

## 诊断：5 个独立根因

通过代码全量分析发现的 5 个独立 Bug：

| Bug | 根因 | 文件 | 症状 |
|-----|------|------|------|
| G1 | `claim_pending_item()` 不存在 | `core/knowledge_graph.py` | SpiderAgent 无法消费 curiosity_queue |
| G2 | `_explore_in_thread` 没有 `mark_topic_done` | `core/async_explorer.py` | async 路径队列状态永远是 pending |
| G3 | `add_exploration_result` parent 推断逻辑颠倒 | `core/knowledge_graph.py` line 747 | queue_item.get("topic") 是当前 topic 不是 parent |
| G4 | `QualityV2` 收到 `knowledge_graph=None` | `core/async_explorer.py` line 55 | 所有 KG 节点 quality=0 |
| G5 | `api_inject` 无 parent link 写入 | `curious_api.py` | R1D3 inject 的父子关系丢失 |

### Bug 串联分析

```
inject(topic, parent="Agent Harness")
    ↓ Bug 5: api_inject() 没有写 parent link
add_curiosity(topic, reason, score, depth)
    ↓ queue item 没有 original_topic（除非通过 **extra 传入）
trigger_async_exploration(topic, score, depth)
    ↓ 没有传 parent（Phase 2 设计）
_explore_in_thread(topic)
    ↓ Bug 2: 没有 mark_topic_done
explorer.explore(topic)
    ↓ Bug 4: knowledge_graph=None → QualityV2 返回 0
add_exploration_result(topic, result, quality)
    ↓ Bug 3: queue_item.get("topic") 获取的是当前探索的 topic，
              不是 original_parent_topic，逻辑完全颠倒
```

---

## G1: `claim_pending_item()` 不存在

**严重程度**: P0

**症状**:
- SpiderAgent 的 `_process_inbox_cycle()` 只消费 DreamInbox，curiosity_queue 无人消费
- `curiosity_queue` 持续积压（453+ 项），队列项 status 永远是 "pending"

**根因**: `knowledge_graph.py` 从未实现 `claim_pending_item()` 函数，Phase 0 spec 白写了

**修复**: 在 `core/knowledge_graph.py` 的 `list_pending()` 函数下方（约 line 234 后）新增：

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

---

## G2: `_explore_in_thread` 没有调 `mark_topic_done`

**严重程度**: P1

**症状**:
- async trigger 路径的队列项 status 永远是 "pending"（不会变成 "done"）
- `trigger_async_exploration` → `_explore_in_thread` → `explorer.explore()` → `add_exploration_result` → `update_curiosity_status(topic, "done")` 这个链条在正常完成时会调，但 async trigger 的队列项 status 始终是 pending

**根因**: `_explore_in_thread` 函数开头没有 `update_curiosity_status(topic, "exploring")`，导致队列状态不同步

**修复**: 在 `core/async_explorer.py` 的 `_explore_in_thread()` 函数开头（`logger.info` 之前）插入：

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

---

## G3: `add_exploration_result` parent 推断逻辑颠倒

**严重程度**: P1

**症状**:
- KG 节点的 parent 关系错误（子 topic 被错误地指向了自己）

**根因**: `core/knowledge_graph.py` 约 line 743-750 的逻辑：

```python
for queue_item in state.get("curiosity_queue", []):
    if queue_item.get("status") == "exploring":
        parent_topic = queue_item.get("topic")  # ← Bug: 获取的是当前探索的 topic，不是 parent
```

当 `_explore_in_thread` 完成时，`queue_item.get("topic")` 拿到的是**当前探索完成的 topic**，不是 parent，逻辑完全颠倒。

**修复**: Phase 2 已经把 parent link 在入口处写入了 KG（`add_child(parent, topic)`），所以这里**不需要再从队列推断 parent**。删除这段逻辑，替换为注释：

```python
    # v0.2.7 Phase 4: parent link 已在 api_inject() 入口处通过 add_child() 写入 KG，
    # 不需要再从队列推断。此段逻辑删除以避免 Bug 3+4（queue_item.get("topic")
    # 拿到的是当前探索完成的 topic，不是 parent，逻辑颠倒）。
    pass
```

---

## G4: `QualityV2` 收到 `knowledge_graph=None`

**严重程度**: P0

**症状**:
- 所有 KG 节点 quality=0 或 NONE
- `python3 scripts/diagnose_quality_v2.py` 输出全是 0

**根因**: `core/async_explorer.py` line 55:

```python
quality = quality_assessor.assess_quality(
    topic=topic,
    findings=findings_dict,
    knowledge_graph=None  # ← G4: 传入 None
)
```

QualityV2 的 `_get_previous_summary(topic, kg)` 内部 `kg.get_state()` 在 `kg=None` 时抛出 `AttributeError`，被 `except Exception: return ""` 吞掉，导致 `prev_summary` 永远是空字符串，语义新颖度永远是 1.0，信息增益评估受影响。

**修复**: `core/async_explorer.py` line 55 改为：

```python
quality = quality_assessor.assess_quality(
    topic=topic,
    findings=findings_dict,
    knowledge_graph=kg_module  # G4-Fix: 传入 kg_module 实例，不是 None
)
```

---

## G5: `api_inject` 无 parent link 写入

**严重程度**: P1

**症状**:
- R1D3 inject 带 parent 参数后，KG 里没有父子关系
- `Agent Harness` 节点的 `children` 为空

**根因**: `curious_api.py` 的 `api_inject()` 函数收到 `parent` 参数时只调用了 `add_curiosity()` 入队列，没有建立 KG 父子关系

**修复**: 在 `curious_api.py` 的 `api_inject()` 函数中，`add_curiosity()` 调用之后、T-9 集成点之前插入：

```python
        from core import knowledge_graph as kg_module  # 确保在函数内可用
        parent = data.get("parent")
        if parent:
            kg_module.add_knowledge(topic=topic, depth=depth, summary="")
            kg_module.add_child(parent, topic)
            print(f"[Phase2] Linked '{topic}' -> '{parent}' in KG")
```

**验收**: inject 后立即检查：
```bash
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"Guardrails schema enforcement","parent":"Agent Harness","source":"r1d3"}'

# 然后检查 KG：
python3 -c "
from core import knowledge_graph as kg
state = kg.get_state()
children = state['knowledge']['topics'].get('Agent Harness', {}).get('children', [])
parents = state['knowledge']['topics'].get('Guardrails schema enforcement', {}).get('parents', [])
print('Agent Harness children:', children)
print('Guardrails parents:', parents)
"
# 期望: children=['Guardrails schema enforcement'], parents=['Agent Harness']
```

---

## 诊断脚本（新建）

**文件**: `scripts/diagnose_quality_v2.py`

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

---

## Backfill 脚本（Phase 5）

**文件**: `scripts/backfill_quality.py`（已存在，需验证可用）

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

---

## SpiderAgent Phase 0 核心改动

**文件**: `core/spider_agent.py`
**位置**: `_process_inbox_cycle()` 约 line 70-84

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

---

## 文件变更清单

```
新增:
  scripts/diagnose_quality_v2.py    # Phase 1 诊断工具
  scripts/backfill_quality.py       # Phase 5 backfill 工具（已存在）

修改:
  core/knowledge_graph.py           # Phase 0: claim_pending_item() + Phase 4: 删除 parent 推断逻辑
  core/spider_agent.py              # Phase 0: _process_inbox_cycle() 改 DreamInbox 空时消费 queue
  core/async_explorer.py            # Phase 1: knowledge_graph=None → kg_module + Phase 3: status 更新
  curious_api.py                    # Phase 2: api_inject() 加 add_child + add_knowledge

无变更:
  core/explorer.py                  # explore() 签名不变
  core/dream_agent.py               # 独立
  core/sleep_pruner.py              # 独立
  core/quality_v2.py                # 无需改动（bug 在调用方）
```

---

## 部署步骤

1. 停止 DAEMON 和 API
2. 备份 `knowledge/state.json`
3. 替换代码文件（按 Phase 顺序）
4. 启动 API: `python3 -u curious_api.py &`
5. 验证 Phase 0: `python3 -c "from core import knowledge_graph as kg; print(kg.claim_pending_item())"`
6. 启动 DAEMON: `python3 -u curious_agent.py --daemon`
7. 运行 Phase 1 诊断: `python3 scripts/diagnose_quality_v2.py`
8. 运行 Phase 5 backfill（如诊断显示大量节点需要）: `python3 scripts/backfill_quality.py`

---

## 风险清单

| 风险 | 严重程度 | 缓解方案 |
|------|----------|---------|
| Phase 0 `claim_pending_item` 和 `fetch_and_clear_dream_inbox` 并发写 state.json | 🟡 | JSON 文件级竞争，接受（两条路径不会同时写同一个字段） |
| Phase 5 backfill 耗尽 API quota | 🟡 | stub 节点不重评，有实质 content 的才重评 |
| `api_inject` 里 `add_knowledge` 建占位节点但探索失败，留下孤岛节点 | 🟡 | Phase 5 backfill 时这些节点 quality=0，可识别 |
| Phase 2 `add_child` parent 不存在时，`add_child` 内部会创建 stub parent | ✅ 已知行为 | 可接受 |

---

## 验收标准

- [ ] `python3 -c "from core import knowledge_graph as kg; print(kg.claim_pending_item())"` 能返回 pending 项且 status 变为 exploring
- [ ] 连续两次调用 `claim_pending_item()`，第二次返回 None（同一 item 不能被重复 claim）
- [ ] SpiderAgent DreamInbox 为空时，从 queue claim 到 item 并继续处理
- [ ] `curl -X POST http://localhost:4848/api/curious/inject -d '{"topic":"Test","parent":"TestParent","source":"r1d3"}'` 后 KG 立即有父子关系
- [ ] `python3 scripts/diagnose_quality_v2.py` 执行无报错
- [ ] QualityV2 对有 content 的节点返回 > 0 的质量分
- [ ] R1D3 inject 后，队列项 status 正确经历 `pending → exploring → done`
- [ ] async 线程异常退出时，status 变为 `paused`
- [ ] `grep -n "parent_topic = queue_item" core/knowledge_graph.py` 不再找到该行

---

## 补充：v0.2.7 修复后遗留问题（2026-03-31 21:45）

### G6: SpiderAgent 同步路径不调用 QualityV2

**严重程度**: P1

**症状**:
- v0.2.7 Phase 1 修复了 `async_explorer.py` 的 `knowledge_graph=None` → `kg_module`
- 但 SpiderAgent 的 `_explore_topic()` 走的是同步路径 `explorer.explore()`，完全绕过了 QualityV2
- KG 所有节点 quality=0（107个节点全部为0）

**根因**: `core/explorer.py` 的 `explore()` 函数末尾只调用了 `kg.add_knowledge()`，没有调用 QualityV2 评估质量。QualityV2 只在 `async_explorer.py` 的异步路径被调用。

**修复方案**: v0.2.8 spec（`ideas/next_move_v0.2.8.md`）——在 `explorer.explore()` 末尾调 QualityV2，然后把 quality 分数作为参数传入 `add_knowledge()`，一步写入 KG。

**当前状态**:
- KG: 107 nodes, 全部 quality=0
- Queue: 532 pending, 4 exploring, 0 done
- 系统运行正常，但质量评估脱节

**修复后验收**: KG 节点 quality > 0，且和 content 实质程度正相关
