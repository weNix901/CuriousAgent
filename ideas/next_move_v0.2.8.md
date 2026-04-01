# v0.2.8: Quality 在 add_knowledge 时写入KG

## 背景

当前 KG 节点 quality 字段全为 0，因为 SpiderAgent 走同步路径 `explorer.explore()` 直接写 KG，绕过了 QualityV2 评分。QualityV2 只在 async 路径（`_explore_in_thread`）被调用，且调用方式分散（assess → update_topic_quality 两步）。

两个问题：
1. **SpiderAgent 不调 QualityV2**：90个节点 quality=0
2. **路径不一致**：async 路径评了分但同步路径没有，且评分分两步（assess + update）

---

## 目标

让 quality 评分在 `add_knowledge()` 写入 KG 的同一时刻发生，代码路径合一。

---

## 方案

### 方案 A（推荐）：`add_knowledge` 接受 `quality` 参数，调用方负责评估

改动点最小，不改变函数边界：

1. `add_knowledge(topic, depth, summary, sources, quality)` 新增 `quality` 参数
2. Explorer 探索完成后立即调用 QualityV2 评估，得到 quality 分数后传入 `add_knowledge`
3. `add_knowledge` 内部直接把 quality 写入节点，不再有独立的 `update_topic_quality` 调用

**SpiderAgent 路径**：
```python
# spider_agent.py - _explore_topic()
result = self.explorer.explore(curiosity_item)
if result:
    # 立即评估 quality
    quality = quality_assessor.assess_quality(topic, result, kg_module)
    kg.add_knowledge(
        topic=topic,
        depth=int(curiosity_item.get("depth", 5)),
        summary=findings[:300],
        sources=sources,
        quality=quality  # ← 同时写入
    )
```

**async 路径**（`async_explorer.py`）：
```python
# 现有: quality = assessor.assess_quality(...)
# 改为: add_knowledge(..., quality=quality)
# 删除: kg.update_topic_quality(topic, quality)  # 不再需要
```

**`add_knowledge` 签名变更**：
```python
def add_knowledge(
    topic: str,
    depth: int = 5,
    summary: str = "",
    sources: list = None,
    quality: float = None  # ← 新增，默认 None（向后兼容旧调用）
) -> None:
```

**QualityV2 调用**统一到两处：
- `core/explorer.py` 的 `explore()` 末尾（SpiderAgent 同步路径）
- `core/async_explorer.py` 的 `_explore_in_thread()`（async 路径）

### 方案 B：`add_knowledge` 内部自己调 QualityV2

更封装，但 `add_knowledge` 变成有副作用的函数，测试困难。**不推荐**。

---

## 文件变更清单

```
修改:
  core/knowledge_graph.py          # add_knowledge() 新增 quality 参数，直接写入
  core/explorer.py                # explore() 末尾调 QualityV2，add_knowledge 传 quality
  core/async_explorer.py          # _explore_in_thread: 删 update_topic_quality，改传 quality 参数
  curious_agent.py                 # 无变更（run_one_cycle 走的也是 explorer.explore）
  core/spider_agent.py            # _explore_topic: 调 QualityV2 + add_knowledge(quality=...)
```

---

## 精确改动

### Step 1: `core/knowledge_graph.py` - `add_knowledge` 签名

**位置**: 约 line 52

**找到**:
```python
def add_knowledge(topic: str, depth: int = 5, summary: str = "", sources: list = None, quality: float = None) -> None:
```

在 `if topic in topics:` 分支的 quality 写入逻辑：
```python
        if quality is not None:
            topics[topic]["quality"] = quality
        elif "quality" not in topics[topic]:
            topics[topic]["quality"] = 0
```

保持不变（`quality` 参数已存在，只是没被调用方传入）。

**在 `_save_state(state)` 前、`topics[topic]["known"] = True` 后**，确保 quality 字段被写入：
```python
        if quality is not None:
            topics[topic]["quality"] = quality
```

实际上现有代码已经支持 quality 写入，只是调用方没传。所以 Step 1 **只需确认签名正确，无需改代码**。

### Step 2: `core/explorer.py` - explore() 末尾调 QualityV2

**位置**: 约 line 150-155（在 `kg.add_knowledge` 调用前）

**找到这段**:
```python
        kg.add_knowledge(
            topic=topic,
            depth=int(curiosity_item.get("depth", 5)),
            summary=findings[:300],
            sources=sources
        )
        kg.update_curiosity_status(topic, "done")
```

**替换为**:
```python
        # === v0.2.8: 探索完成立即评估 quality ===
        quality = self._assess_quality(topic, findings, curiosity_item)
        # === v0.2.8 结束 ===

        kg.add_knowledge(
            topic=topic,
            depth=int(curiosity_item.get("depth", 5)),
            summary=findings[:300],
            sources=sources,
            quality=quality
        )
        kg.update_curiosity_status(topic, "done")
```

**在 `explorer.py` 开头或 `__init__` 后新增** `_assess_quality` 方法：
```python
    def _assess_quality(self, topic: str, findings: str, curiosity_item: dict) -> float:
        """评估探索结果质量"""
        try:
            from core.quality_v2 import QualityV2Assessor
            from core import knowledge_graph as kg_module
            assessor = QualityV2Assessor(self.llm_client)
            findings_dict = {
                "summary": findings[:300],
                "sources": curiosity_item.get("sources", [])
            }
            quality = assessor.assess_quality(topic, findings_dict, kg_module)
            return quality if quality is not None else 0.0
        except Exception as e:
            print(f"[Explorer] Quality assessment failed for '{topic}': {e}")
            return 0.0
```

**在 `explorer.py` 的 `__init__` 确保有 `self.llm_client`**（如果没有则传入）：
```python
    def __init__(self, ...):
        # 已有 llm_client 的初始化
        self.llm_client = llm_client  # 确保存在
```

### Step 3: `core/async_explorer.py` - 删除 update_topic_quality

**位置**: 约 line 55-75

**找到**:
```python
            quality = quality_assessor.assess_quality(
                topic=topic,
                findings=findings_dict,
                knowledge_graph=kg_module
            )
            # ... later ...
            kg_module.update_topic_quality(topic, quality)
```

**替换** `kg_module.update_topic_quality(topic, quality)` 为在 `add_exploration_result` 调用时传 quality（见 Step 4）。

### Step 4: `core/async_explorer.py` - add_exploration_result 传 quality

**位置**: 约 line 100

**找到**:
```python
            kg_module.add_exploration_result(topic, result, quality)
```

**确认** `add_exploration_result` 签名支持 quality 参数：
```python
def add_exploration_result(topic: str, result: dict, quality: float = None) -> None:
```

如果 `add_exploration_result` 内部调用 `add_knowledge`，需要确保 quality 传递下去。具体需要检查 `add_exploration_result` 的实现——如果它内部调 `add_knowledge`，改动在 Step 5。

### Step 5: 确认 `add_exploration_result` 传递 quality

**位置**: `core/knowledge_graph.py` 约 line 300-360

检查 `add_exploration_result` 是否直接调用 `add_knowledge`。如果是，需要确保 quality 参数透传：
```python
def add_exploration_result(topic: str, result: dict, quality: float = None) -> None:
    # ...
    kg.add_knowledge(
        topic=topic,
        depth=depth,
        summary=summary,
        sources=sources,
        quality=quality  # ← 透传
    )
```

### Step 6: `core/spider_agent.py` - _explore_topic 调 QualityV2

**位置**: 约 line 130-145（`self.explorer.explore()` 调用后）

**找到**:
```python
        try:
            with NodeLockRegistry.global_write_lock():
                lock = NodeLockRegistry.get_lock(topic)
                with lock:
                    result = self.explorer.explore(curiosity_item)
                    if result:
                        self._last_explored_timestamp = time.time()
                    self._notify_dream_agent(topic, result)
                    return result
        except Exception as e:
            print(f"[SpiderAgent] Exploration failed for '{topic}': {e}")
```

**替换为**:
```python
        try:
            with NodeLockRegistry.global_write_lock():
                lock = NodeLockRegistry.get_lock(topic)
                with lock:
                    result = self.explorer.explore(curiosity_item)
                    if result:
                        self._last_explored_timestamp = time.time()
                    self._notify_dream_agent(topic, result)
                    return result
        except Exception as e:
            print(f"[SpiderAgent] Exploration failed for '{topic}': {e}")
            return None

        # === v0.2.8: SpiderAgent 不在这里评估质量 ===
        # 质量评估已在 explorer.explore() 内部通过 _assess_quality 完成（Step 2）
        # add_knowledge(quality=...) 也已在 explorer.explore() 内部调用
        # 所以 SpiderAgent 无需额外操作
```

**实际上 Step 2 已经在 `explorer.explore()` 内部处理了质量评估和 `add_knowledge` 调用，所以 Step 6 只需要确认 SpiderAgent 不重复调用即可。**

---

## 验收标准

- [ ] `python3 -c "from core.explorer import Explorer; print('OK')"` 无报错
- [ ] 跑一轮探索后，KG 节点有 `quality` 字段且 > 0
- [ ] `python3 scripts/diagnose_quality_v2.py` 输出 `quality>0 节点数` > 0
- [ ] SpiderAgent 和 async 路径都能产生有质量分的 KG 节点
- [ ] `add_knowledge` 的旧调用（不传 quality）仍正常工作（quality 默认为 0）

---

## 风险

- `add_knowledge` 内部已经有 quality 写入逻辑，调用方如果不传 quality，节点 quality 仍为 0。需要确认所有调用方都传入 quality。
- 检查所有调用 `add_knowledge` 的地方（`grep -rn "add_knowledge"`）确保都传了 quality 或不需要质量评估的临时调用（如 Phase 2 的占位节点）不受影响。
