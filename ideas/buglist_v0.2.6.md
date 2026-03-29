# Buglist v0.2.6 — 分解能力缺失 & 探索闭环未形成

> 发现时间: 2026-03-29 by R1D3
> 状态: ✅ **全部修复完成**（2026-03-29 13:55 by weNix/OpenCode）
> 优先级: P0

---

## 概述

v0.2.6 三代理架构（SpiderAgent、DreamAgent、SleepPruner）已上线，但存在两个根本性缺陷：

1. **SpiderAgent 没有 decomposition 能力** — 探索完 topic 后不会拆解子 topic，KG 永远无法形成树状结构
2. **DreamAgent 的洞察没有触发新探索** — insights 写入文件后没有形成探索闭环
3. **论文/网页引用没有变成子节点** — 探索结果里的引用来源白白浪费了

---

## Bug #1: SpiderAgent 没有集成 decomposition 逻辑（P0）

**严重程度**: P0
**影响**: 所有探索都是"平铺式"，KG 无法形成树状结构，父子关系永远为零

**根因**:

SpiderAgent 的 `_explore_topic()` 只调用了 `self.explorer.explore(curiosity_item)`，没有任何 decomposition 逻辑：

```python
# core/spider_agent.py - _explore_topic() 现状
def _explore_topic(self, topic: str, source_insight: str) -> Optional[dict]:
    curiosity_item = {...}
    result = self.explorer.explore(curiosity_item)  # ← 只探索，不分解
    self._notify_dream_agent(topic, result)          # ← 直接通知 DreamAgent
    return result
```

decomposition 逻辑只存在于 `curious_agent.py` 的 `run_one_cycle()` 里，是 legacy 单线程模式专用的。

**验证**:
```bash
curl -s "http://localhost:4848/api/curious/state" | python3 -c "
import json,sys; d=json.load(sys.stdin)
topics = d.get('knowledge',{}).get('topics',{})
has_children = sum(1 for t in topics.values() if t.get('children'))
print(f'Topics with children: {has_children}/{len(topics)}')
"
# 结果: 0 — 证实没有树状结构
```

---

## Bug #2: DreamAgent insights 没有触发 SpiderAgent 探索闭环（P0）

**严重程度**: P0
**影响**: DreamAgent 生成的 insights 只存在文件里，没有形成"探索→洞察→新探索"的闭环

**根因**:

DreamAgent 的 `_notify_spider_agent()` 写入 SharedInbox：

```python
# core/dream_agent.py
def _notify_spider_agent(self, topic_a: str, topic_b: str, insight: dict):
    kg.add_to_dream_inbox(topic_a, f"Dream insight: {insight_summary}")   # ← 写 inbox
    kg.add_to_dream_inbox(topic_b, f"Dream insight: {insight_summary}")
```

SpiderAgent 的 `_process_inbox_cycle()` 读 SharedInbox：

```python
# core/spider_agent.py
def _process_inbox_cycle(self):
    inbox_items = kg.fetch_and_clear_dream_inbox()  # ← 读 inbox
    for item in inbox_items:
        topic = item.get("topic")
        result = self._explore_topic(topic, ...)     # ← 探索 topic
```

**关键问题**：SpiderAgent 在三代理模式下，`fetch_and_clear_dream_inbox()` 读到的 inbox 里确实有 topic，但 SpiderAgent 只探索这个 topic，**不触发 decomposition**，也没有把 DreamAgent 洞察里提到的 `trigger_topic` 加入探索队列。

**验证**:
```bash
# DreamAgent 写入了 inbox
cat /root/dev/curious-agent/knowledge/dream_topic_inbox.json
# 但 SpiderAgent 探索后，KG 里没有 trigger_topic 的子节点
```

---

## Bug #3: 论文核心引用没有变成子节点（P1）

**严重程度**: P1
**影响**: Layer2 的 arxiv 分析找到了相关论文，但论文的"核心引用"（related work 中的关键技术）没有被提取为子 topic

**根因**:

Explorer 的 `_layer2_arxiv()` 只分析论文元数据和摘要，没有提取论文的引用链路：

```python
# core/explorer.py
def _layer2_arxiv(self, topic: str, arxiv_links: list = None) -> dict:
    result = analyzer.analyze_papers(topic, arxiv_links)
    papers = result.get("papers", [])
    # ← 没有提取 paper.citations / related_work
```

**期望行为**:

```
探索 "transformer attention mechanism"
  → Layer2 找到论文 "Attention is All You Need"
  → 提取核心引用:
       - Residual Learning (He et al., 2015)
       - Layer Normalization (Ba et al., 2016)
       - Scaled Dot-Product Attention
  → 这三个变成 transformer attention mechanism 的 children
  → SpiderAgent 继续探索每个 child
```

---

## Bug #4: 网页来源的引用没有变成子节点（P1）

**严重程度**: P1
**影响**: Layer1 搜索结果里的来源网页，如果本身有外部引用，没有被提取为子节点

**根因**: Layer1 只提取搜索结果的标题和摘要，没有追踪来源页面的外部链接。

**期望行为**:

```
探索 "agent state management"
  → Layer1 找到博客文章 "Agent Memory Architecture"
  → 提取该页面的外部引用:
       - Smith et al. "Memory-Augmented Agents" (引用来源)
       - Cognitive Psychology Working Memory Theory
  → 引用来源变成 agent state management 的 children
```

---

## Bug #5: API `/api/curious/run` 没有 decomposition 能力（P1）

**严重程度**: P1
**影响**: 通过 API 触发探索时，无法产生树状结构

**根因**:

`curious_api.py` 的 `api_run()` 直接调用 `explorer.explore()`，不经过 `run_one_cycle()` 的完整流程：

```python
# curious_api.py - api_run()
result = explorer.explore(next_item)  # ← 没有 decomposition
```

---

## 修复方案

### 修复 #1: SpiderAgent 集成 decomposition 逻辑

**策略**: 在 SpiderAgent 的 `_explore_topic()` 末尾，探索完成后调用 `CuriosityDecomposer`，把 subtopics 加入 curiosity_queue。

**修改文件**: `core/spider_agent.py`

**新增导入**:
```python
from core.curiosity_decomposer import CuriosityDecomposer
from core.llm_manager import LLMManager
from core.provider_registry import init_default_providers
```

**新增方法**:
```python
def _decompose_and_enqueue(self, topic: str):
    """
    探索完成后调用 decomposition，把 subtopics 加入 KG 和 curiosity_queue。
    """
    try:
        # 初始化 decomposer（与 run_one_cycle() 相同的初始化逻辑）
        from core.curiosity_decomposer import CuriosityDecomposer
        from core.llm_manager import LLMManager
        from core.provider_registry import init_default_providers

        llm_config = {...}  # 从 config 获取
        llm_manager = LLMManager.get_instance(llm_config)
        registry = init_default_providers()
        state = kg.get_state()

        decomposer = CuriosityDecomposer(
            llm_client=llm_manager,
            provider_registry=registry,
            kg=state
        )

        # 调用 decomposition
        subtopics = asyncio.run(decomposer.decompose(topic))

        if subtopics:
            subtopics_sorted = sorted(subtopics, key=lambda x: (
                x.get("signal_strength") != "strong",
                -x.get("total_count", 0)
            ))
            best = subtopics_sorted[0]

            print(f"[SpiderAgent] Decomposed '{topic}' into {len(subtopics)} subtopics")

            for sibling in subtopics_sorted:
                s_topic = sibling["sub_topic"]
                s_strength = sibling.get("signal_strength", "unknown")
                s_relevance = 7.0 if s_strength == "strong" else (6.0 if s_strength == "medium" else 5.0)
                s_depth = 6.0 if s_strength == "strong" else (5.5 if s_strength == "medium" else 5.0)

                kg.add_curiosity(
                    topic=s_topic,
                    reason=f"Decomposed from: {topic}",
                    relevance=float(s_relevance),
                    depth=float(s_depth),
                    original_topic=topic
                )
                kg.add_child(topic, s_topic)
                print(f"[SpiderAgent]   + Child: '{s_topic}' ({s_strength})")
        else:
            print(f"[SpiderAgent] No decomposition for '{topic}'")

    except Exception as e:
        print(f"[SpiderAgent] Decomposition failed for '{topic}': {e}")
```

**修改 `_explore_topic()`**:
在 `self._notify_dream_agent(topic, result)` 之后追加：
```python
# === v0.2.6: 探索完成后触发 decomposition ===
self._decompose_and_enqueue(topic)
# === v0.2.6 结束 ===
```

**与 legacy 路径的兼容性**: `run_one_cycle()` 继续使用自己的 decomposition 逻辑（直接调用 `decomposer.decompose()`），SpiderAgent 的 decomposition 是独立路径，不会冲突。

---

### 修复 #2: DreamAgent 洞察触发 SpiderAgent 新探索（闭环）

**策略**: DreamAgent 生成 insights 后，把 `trigger_topic` 写入 SharedInbox。SpiderAgent 探索 inbox topic 时，如果 topic 有对应的 insight，读取该 insight 并基于它进行有针对性的探索。

**修改文件**: `core/dream_agent.py`（已有逻辑，基本正确）

**关键确认**: `_notify_spider_agent()` 已经正确写入 `dream_topic_inbox.json`：

```python
def _notify_spider_agent(self, topic_a: str, topic_b: str, insight: dict):
    insight_summary = insight.get("content", "")[:100]
    kg.add_to_dream_inbox(topic_a, f"Dream insight: {insight_summary}")
    kg.add_to_dream_inbox(topic_b, f"Dream insight: {insight_summary}")
```

**修改 SpiderAgent**: `_process_inbox_cycle()` 在探索 inbox topic 时，读取对应的 insight 内容并传递给 `_explore_topic()`：

```python
def _process_inbox_cycle(self):
    inbox_items = kg.fetch_and_clear_dream_inbox()  # 读并清空

    for item in inbox_items:
        topic = item.get("topic")
        source_insight = item.get("source_insight", "")

        if not topic or kg.is_topic_completed(topic):
            continue

        result = self._explore_topic(topic, source_insight)  # 传入 insight context

        if result:
            cycle_topics.append(topic)
            self._explored_topics.append(topic)
            # === v0.2.6: 探索完成 → decomposition → DreamAgent 收到通知 ===
            self._decompose_and_enqueue(topic)
            # === v0.2.6 结束 ===
```

**注意**: 这里的关键改进是 inbox 里的 topic 被探索后会触发 decomposition，decomposition 产生的 children 会通过 `kg.add_child()` 写入 KG。DreamAgent 下次看到这些新 children 时，可以对它们进行跨域联想。

**DreamAgent → SpiderAgent → DreamAgent 完整闭环**:
```
DreamAgent 生成 insight
  → add_to_dream_inbox(trigger_topic)
  → SpiderAgent 消费 inbox，探索 trigger_topic
  → SpiderAgent decomposition，产生 children
  → SpiderAgent 通知 DreamAgent（via notification_queue）
  → DreamAgent 对新 children 做远距离联想
  → 新 insight → 新 inbox → 新探索 ...
```

---

### 修复 #3: 论文核心引用提取（PaperCitationExtractor）

**策略**: 新增 `PaperCitationExtractor` 模块，在 `_layer2_arxiv()` 之后调用，提取论文的核心引用并加入 KG。

**新增文件**: `core/paper_citation_extractor.py`

**核心逻辑**:
```python
class PaperCitationExtractor:
    """
    从论文中提取核心引用，转变为 KG 子节点

    提取策略:
    1. 分析论文的 Related Work 段落
    2. LLM 提取关键技术名称和作者年份
    3. 将提取结果作为子 topic 加入 KG
    """

    def extract_citations(self, topic: str, papers: list[dict]) -> list[str]:
        """
        从论文列表中提取核心引用

        Args:
            topic: 父 topic 名称
            papers: arxiv_analyzer 返回的论文列表

        Returns:
            提取到的引用 topic 列表
        """
        if not papers:
            return []

        # 构建 prompt：让 LLM 从 Related Work 提取关键技术
        paper_summaries = "\n".join([
            f"- {p.get('title','')}: {p.get('abstract','')[:200]}"
            for p in papers[:5]
        ])

        prompt = f"""从以下论文的 Related Work 中提取核心技术引用。

        父主题: {topic}

        论文:
        {paper_summaries}

        要求：找出每篇论文 Related Work 中提到的关键技术/方法/框架，
        用"技术名称 (作者, 年份)"格式返回。
        例如：
        - Attention Is All You Need (Vaswani et al., 2017)
        - Residual Learning (He et al., 2016)
        - BERT (Devlin et al., 2018)

        返回 JSON 格式：
        {{
            "citations": [
                {{"name": "技术名称", "paper": "来源论文", "reason": "为什么重要"}},
                ...
            ]
        }}
        """

        client = LLMClient()
        response = client.chat(prompt, temperature=0.3)

        # 解析 JSON，提取 citations
        # 每个 citation → kg.add_child(topic, citation_name)
        # 每个 citation → kg.add_curiosity(citation_name, ...)
```

**集成到 Explorer**: 在 `explorer.py` 的 `_layer2_arxiv()` 之后追加：

```python
# core/explorer.py
from core.paper_citation_extractor import PaperCitationExtractor

def _layer2_arxiv(self, topic: str, arxiv_links: list = None) -> dict:
    # ...现有代码...
    papers = result.get("papers", [])

    # === v0.2.6 新增: 提取论文核心引用 ===
    if papers:
        extractor = PaperCitationExtractor()
        citations = extractor.extract_citations(topic, papers)
        for citation in citations:
            kg.add_child(topic, citation["name"])
            kg.add_curiosity(
                topic=citation["name"],
                reason=f"Paper citation from: {topic}",
                relevance=7.0,
                depth=5.0,
                original_topic=topic
            )
    # === v0.2.6 结束 ===

    sources = [f"https://arxiv.org/abs/{p['arxiv_id']}" for p in papers if p.get("arxiv_id")]
    return {...}
```

**与现有代码的关系**: `_layer2_arxiv()` 原本就有 `papers` 数据，只是没有提取 citations。添加这段逻辑不破坏现有功能。

---

### 修复 #4: 网页来源引用提取

**策略**: Layer1 搜索结果返回时，每个结果条目里包含来源 URL。扩展 `_parse_bocha_results()` 或新增 `WebCitationExtractor`，从高权重来源 URL 提取外部引用。

**实现优先级**: P2（相对于论文引用，网页引用的优先级更低）

**初步方案**:

```python
class WebCitationExtractor:
    """从网页来源中提取外部引用"""

    def extract_from_sources(self, topic: str, sources: list[str]) -> list[str]:
        """
        从 sources 列表中提取外部引用
        策略：分析来源页面的 meta keywords / related links / citations
        """
        citations = []
        for url in sources[:3]:  # 只分析前 3 个高权重来源
            try:
                # 调用 LLM 分析页面引用的关键技术
                citations.extend(self._extract_from_page(topic, url))
            except Exception:
                pass
        return citations

    def _extract_from_page(self, topic: str, url: str) -> list[str]:
        # 获取页面内容（有限抓取）
        # LLM 提取"该页面引用的关键技术"
        # 返回 citation 名称列表
```

**集成方式**: 在 `_explore_layers()` 的 Layer1 完成后调用：

```python
# explorer.py
def _explore_layers(self, topic: str) -> dict:
    layer_results = {}

    # Layer 1: Web Search
    l1_result = self._layer1_search(topic)
    layer_results["layer1"] = l1_result

    # === v0.2.6 新增: 提取网页引用 ===
    if l1_result.get("sources"):
        web_extractor = WebCitationExtractor()
        web_citations = web_extractor.extract_from_sources(topic, l1_result["sources"])
        for citation in web_citations:
            kg.add_child(topic, citation)
            kg.add_curiosity(topic=citation, reason=f"Web citation from: {topic}", ...)
    # === v0.2.6 结束 ===

    # Layer 2: ArXiv
    ...
```

---

### 修复 #5: API `/api/curious/run` 支持 decomposition

**策略**: 在 `api_run()` 探索完成后，追加调用 decomposition 逻辑（复用 SpiderAgent 的 `_decompose_and_enqueue` 逻辑）。

**修改文件**: `curious_api.py`

```python
# curious_api.py - api_run() 末尾
# 现有代码:
result = explorer.explore(next_item)
mark_topic_done(result["topic"], "API exploration completed")
monitor.record_exploration(...)

# === v0.2.6 新增: 触发 decomposition ===
decomposer = CuriosityDecomposer(llm_client=llm_manager, provider_registry=registry, kg=state)
subtopics = asyncio.run(decomposer.decompose(result["topic"]))
if subtopics:
    for sibling in subtopics:
        kg.add_child(result["topic"], sibling["sub_topic"])
        kg.add_curiosity(topic=sibling["sub_topic"], ...)
# === v0.2.6 结束 ===
```

---

## 修复顺序

| 顺序 | 修复 | 优先级 | 理由 |
|------|------|--------|------|
| **1st** | #1 SpiderAgent 集成 decomposition | P0 | 基础能力，阻塞其他功能 |
| **2nd** | #2 DreamAgent 闭环 | P0 | 依赖 #1 完成 |
| **3rd** | #3 论文引用提取 | P1 | 独立模块，可并行 |
| **4th** | #5 API decomposition | P1 | 依赖 #1 的逻辑 |
| **5th** | #4 网页引用提取 | P2 | 优先级低 |

---

## 代码复用策略（避免与 legacy 冲突）

**核心原则**: decomposition 逻辑只存在于 `CuriosityDecomposer.decompose()` 一个地方，SpiderAgent 和 `run_one_cycle()` 都调用同一个方法。

```
CuriosityDecomposer.decompose(topic)
    │
    ├── SpiderAgent._decompose_and_enqueue()  ← 新增
    │       ├── kg.add_child()               ← 写 KG
    │       └── kg.add_curiosity()            ← 写队列
    │
    └── curious_agent.run_one_cycle()        ← 现有
            ├── kg.add_child()               ← 写 KG（已存在）
            └── kg.add_curiosity()            ← 写队列（已存在）
```

两者调用同一个 `decomposer.decompose()`，写入同一个 KG，不冲突。

---

## 验证标准

```bash
# 1. KG 有树状结构
curl -s "http://localhost:4848/api/curious/state" | python3 -c "
import json,sys; d=json.load(sys.stdin)
topics = d.get('knowledge',{}).get('topics',{})
has_children = sum(1 for t in topics.values() if t.get('children'))
has_parents = sum(1 for t in topics.values() if t.get('parents'))
print(f'Topics with children: {has_children}')
print(f'Topics with parents: {has_parents}')
"

# 2. DreamAgent insights 触发新探索（闭环）
# 观察：dream_topic_inbox.json 有内容 → SpiderAgent 消费 → KG 出现新子节点

# 3. 论文引用变成子节点
# 探索有 arxiv 论文的 topic → KG 里出现 paper citation 作为 children

# 4. API 探索产生树状结构
curl -X POST "http://localhost:4848/api/curious/run" \
  -H "Content-Type: application/json" \
  -d '{"topic":"transformer attention mechanism","depth":"deep"}'
# → KG 里 transformer attention mechanism 有 children
```

---

_Last updated: 2026-03-29 by R1D3_
_v0.2.6: SpiderAgent decomposition + DreamAgent闭环 + 引用提取_

---

## Fix #6: 知识点分解逻辑集中化（统一 KG 写入路径）

**提出时间**: 2026-03-29 by R1D3
**状态**: 待实现

### 当前问题

知识点分解逻辑分散在两处，KG 写入逻辑（`add_child` / `add_curiosity`）也分散在两处：

| 位置 | 作用 |
|------|------|
| `curious_agent.py` 的 `run_one_cycle()` | 调用 `CuriosityDecomposer.decompose()` + 写 KG |
| `core/curious_decomposer.py` | 只做 decomposition，不写 KG |
| `core/spider_agent.py` | 完全不知道 decomposition，不写 KG |
| `curious_api.py` 的 `api_run()` | 只调 `explorer.explore()`，不写 KG |

**根本问题**：decomposition 和 KG 写入没有绑定在一起，导致 SpiderAgent 和 API 路径都绕过了 decomposition。

### 修复方案：单一职责原则

**核心思路**：让 `CuriosityDecomposer.decompose()` 自己写 KG，调用方零逻辑。

**新增方法**：`decompose_and_write()`

```python
# core/curiosity_decomposer.py

def decompose_and_write(self, topic: str) -> list[dict]:
    """
    完整流程：decompose + 写 KG（单一入口）
    
    所有调用方（SpiderAgent / run_one_cycle / api_run）都调这个方法。
    decomposition 结果自动写入 KG，不在调用方分散。
    """
    subtopics = asyncio.run(self.decompose(topic))

    if not subtopics:
        return []

    # 写入 KG（统一在一处）
    for sibling in subtopics:
        s_topic = sibling["sub_topic"]
        s_strength = sibling.get("signal_strength", "unknown")
        s_relevance = 7.0 if s_strength == "strong" else (6.0 if s_strength == "medium" else 5.0)
        s_depth = 6.0 if s_strength == "strong" else (5.5 if s_strength == "medium" else 5.0)

        kg.add_child(topic, s_topic)
        kg.add_curiosity(
            topic=s_topic,
            reason=f"Decomposed from: {topic}",
            relevance=float(s_relevance),
            depth=float(s_depth),
            original_topic=topic
        )

    return subtopics
```

### 调用方改动（最小化）

**`core/spider_agent.py`** — `_explore_topic()` 末尾：
```python
# 原来：explorer.explore() → _notify_dream_agent()
# 新增一行：
result = self.explorer.explore(curiosity_item)
self._notify_dream_agent(topic, result)
# === v0.2.6 新增 ===
self._decompose_and_enqueue(topic)  # 调同一个方法
# === v0.2.6 结束 ===

# 其中 _decompose_and_enqueue() 只是调 decomposer.decompose_and_write()
def _decompose_and_enqueue(self, topic: str):
    try:
        from core.curiosity_decomposer import CuriosityDecomposer
        from core.llm_manager import LLMManager
        from core.provider_registry import init_default_providers

        llm_config = {...}
        llm_manager = LLMManager.get_instance(llm_config)
        registry = init_default_providers()
        state = kg.get_state()

        decomposer = CuriosityDecomposer(
            llm_client=llm_manager,
            provider_registry=registry,
            kg=state
        )

        subtopics = decomposer.decompose_and_write(topic)
        print(f"[SpiderAgent] Decomposed '{topic}' into {len(subtopics)} subtopics")
        for st in subtopics:
            print(f"  + {st['sub_topic']} ({st.get('signal_strength', 'unknown')})")
    except Exception as e:
        print(f"[SpiderAgent] Decompose failed for '{topic}': {e}")
```

**`curious_agent.py`** — `run_one_cycle()` 里：
```python
# 原来（两处写 KG）：
subtopics = asyncio.run(decomposer.decompose(topic))
if subtopics:
    subtopics_sorted = sorted(...)
    for sibling in subtopics_sorted:
        kg.add_child(topic, sibling["sub_topic"])           # ← 写 KG 逻辑
        kg.add_curiosity(topic=s_topic, ...)                # ← 写 KG 逻辑

# 改成（一行）：
subtopics = decomposer.decompose_and_write(topic)  # ← 同一处写 KG
```

**`curious_api.py`** — `api_run()` 末尾：
```python
# 原来没有 decomposition
result = explorer.explore(next_item)

# 改成：
result = explorer.explore(next_item)
# === v0.2.6 新增 ===
decomposer = CuriosityDecomposer(llm_client=llm_manager, provider_registry=registry, kg=state)
decomposer.decompose_and_write(result["topic"])
# === v0.2.6 结束 ===
```

### 架构对比

| | 修复前 | 修复后 |
|--|--------|--------|
| decomposition 逻辑 | 1 处（`CuriosityDecomposer`） | 1 处 |
| KG 写入逻辑（add_child / add_curiosity） | 2 处（`run_one_cycle` + 分散） | **1 处（`decompose_and_write()`）** |
| SpiderAgent decomposition | 无 | `decompose_and_write()` |
| API decomposition | 无 | `decompose_and_write()` |
| 调用方 KG 写入代码 | `run_one_cycle` 里有，spider/api 里没有 | **零写入代码** |

### 依赖关系

- Fix #6 是 Fix #1 的基础设施：Fix #1 需要 SpiderAgent 调 `decompose_and_write()`，Fix #6 把这个调用从"分散写 KG"变成"只调一个方法"
- Fix #6 不影响 Fix #3（论文引用提取），两者可并行

### 验证

```bash
# 任意路径探索后，KG 都有 children
curl -X POST "http://localhost:4848/api/curious/run" \
  -H "Content-Type: application/json" \
  -d '{"topic":"transformer attention mechanism","depth":"deep"}'

curl -s "http://localhost:4848/api/curious/state" | python3 -c "
import json,sys; d=json.load(sys.stdin)
topics = d.get('knowledge',{}).get('topics',{})
has_children = sum(1 for t in topics.values() if t.get('children'))
has_parents = sum(1 for t in topics.values() if t.get('parents'))
print(f'children: {has_children}, parents: {has_parents}')
# 期望: children > 0, parents > 0
"
```

_Last updated: 2026-03-29 by R1D3_
_v0.2.6 Fix #6: 单一职责 decomposition_

---

## Fix #3 IMPLEMENTED: PaperCitationExtractor（论文核心引用提取）

**实现时间**: 2026-03-29
**文件**: `core/paper_citation_extractor.py`（新建，11893 字节）

### 实现方案

**方案 A — LLM 分析（轻量，永远执行）**
```
论文 title + abstract → LLM prompt → 提取 "[技术名] (作者, 年份)" 格式
```
- 用专门的 prompt 让 LLM 从 Related Work / Introduction 识别引用的核心技术
- 优点：不需要下载 PDF，不耗 token
- 缺点：LLM 可能漏掉或编造

**方案 B — PDF 解析（重量，只对高相关论文执行）**
```
PDF 前 8 页 → 找 References 段落 → 分割单条引用 → LLM 二次提取技术名
```
- 正则识别 References 段落边界
- 技术关键词过滤（attention/transformer/reinforcement 等 40+ 关键词）
- 解析后用 LLM 二次提取技术名称
- 最多解析 3 篇高相关论文（避免 PDF 下载开销）

**去重策略**
- 归一化：去掉"(作者,年份)"后缀 + 转小写
- 优先保留 LLM 结果（比 PDF 解析更准确）

### 核心数据结构

```python
# 引用条目
{
    "name": "Attention Is All You Need (Vaswani et al., 2017)",
    "source_paper": "xxx",
    "source_arxiv_id": "1706.03762",
    "method": "llm" | "pdf",   # 来源方法
    "year": "2017"
}
```

### 集成到 Explorer

**在 `core/explorer.py` 的 `_layer2_arxiv()` 之后追加**：

```python
# core/explorer.py
from core.paper_citation_extractor import PaperCitationExtractor

def _layer2_arxiv(self, topic: str, arxiv_links: list = None) -> dict:
    # ... 现有代码 ...
    papers = result.get("papers", [])

    # === v0.2.6 Fix #3: 提取论文核心引用 ===
    if papers:
        extractor = PaperCitationExtractor()
        citations = extractor.extract_all(topic, papers)
        if citations:
            extractor.write_to_kg(topic, citations)
    # === v0.2.6 结束 ===

    return {...}
```

###KG 写入

`write_to_kg()` 对每个 citation：
```python
kg.add_child(topic, citation_name)       # 写入 children
kg.add_curiosity(topic=citation_name,    # 加入探索队列
    reason=f"Paper citation from: {topic}",
    relevance=7.0, depth=5.0,
    original_topic=topic
)
```

### 验证

```bash
# 探索有 arxiv 论文的 topic
curl -X POST "http://localhost:4848/api/curious/run" \
  -H "Content-Type: application/json" \
  -d '{"topic":"transformer attention mechanism","depth":"deep"}'

# 查看日志
tail logs/api.log | grep CitationExtractor
# 期望输出：
# [CitationExtractor] LLM extracted 5 citations
# [CitationExtractor] PDF extracted 3 from 1706.03762
# [CitationExtractor] Total: 8, Deduplicated: 6
# [CitationExtractor] Wrote 6 citations as children of 'transformer attention mechanism'

# 验证 KG
curl -s "http://localhost:4848/api/curious/state" | python3 -c "
import json,sys; d=json.load(sys.stdin)
topic = d['knowledge']['topics'].get('transformer attention mechanism', {})
children = topic.get('children', [])
print(f'Children: {len(children)}')
for c in children:
    print(f'  - {c}')
"
```

_Last updated: 2026-03-29 by R1D3_
_v0.2.6 Fix #3: PaperCitationExtractor implemented_

---

## Fix #3 UPDATED: 论文引文提取应集成到分解流程，不是独立写 KG

**修正时间**: 2026-03-29 by R1D3

### 重新分析

**原来的方案（错误）**：
```
paper_citation_extractor.py 独立模块
    │
    └── write_to_kg() 直接写 KG
```
问题：写入逻辑分散，绕过了 `decompose_and_write()` 的统一管理。

**正确的方案**：
```
decompose(topic)
    │
    ├── _llm_generate_candidates()     → sub-topics (LLM 生成)
    ├── _verify_with_providers()        → verified
    ├── _kg_augment()                  → enriched
    └── _extract_paper_citations()      → ⭐ sub-topics (论文引文) ← 新增步骤
    │
    └── return all_sub_topics          ← 和 LLM 生成的结果合并返回
         │
         └── decompose_and_write()      ← 统一写 KG，不分开写
```

### 两种任务的本质对比

| | 知识点分解 | 论文引文提取 |
|--|-----------|-------------|
| 输入 | topic | topic |
| 输出 | sub-topic 列表 | sub-topic 列表 |
| 子 topic 来源 | LLM 推理 | 论文 Related Work |
| 子 topic 格式 | `{"sub_topic": str, ...}` | `{"sub_topic": str, "source": "citation", ...}` |
| 写 KG 时机 | `decompose_and_write()` 统一写 | `decompose_and_write()` 统一写 |

### 新增步骤：`_extract_paper_citations()`

在 `CuriosityDecomposer` 里新增方法：

```python
async def _extract_paper_citations(self, topic: str, papers: list[dict]) -> list[dict]:
    """
    Step 4: 从论文中提取核心引文，作为 sub-topics 返回

    方案 A: LLM 分析 abstract（轻量）
    方案 B: PDF 解析 References（重量，只对高相关论文）
    去重: 与 _llm_generate_candidates 结果合并去重

    返回格式与 _llm_generate_candidates 一致：
    [{"sub_topic": "...", "source": "citation", "paper": "...", ...}, ...]
    """
    if not papers:
        return []

    extractor = PaperCitationExtractor(llm_client=self.llm)
    citations = extractor.extract_all(topic, papers)

    # 转换成 decompose 的标准格式
    subtopics = []
    for c in citations:
        name = c["name"]
        if len(name) > 100:
            name = name[:100]
        subtopics.append({
            "sub_topic": name,
            "source": "citation",
            "source_paper": c.get("source_paper", ""),
            "source_arxiv_id": c.get("source_arxiv_id", ""),
            "signal_strength": "strong",  # 引文有一定可信度
            "verification": {"method": c.get("method", "llm")}
        })

    return subtopics
```

### 修改 `decompose()` 主流程

```python
async def decompose(self, topic: str) -> list[dict]:
    # Step 1: LLM 生成候选
    candidates = await self._llm_generate_candidates(topic)
    if not candidates:
        raise ClarificationNeeded(topic, reason="LLM generated no candidates")

    # Step 2: Provider 验证
    verified = await self._verify_with_providers(candidates)
    if not verified:
        verified = await self._cascade_fallback(topic, candidates)

    # Step 3: KG 补充
    enriched = self._kg_augment(topic, verified)

    # === v0.2.6 Fix #3 UPDATED: 新增 Step 4 ===
    # Step 4: 论文引文提取（如果 papers 可用）
    if hasattr(self, '_papers') and self._papers:
        citation_subtopics = await self._extract_paper_citations(topic, self._papers)
        # 合并去重：citation subtopics 和 LLM candidates 去重
        enriched = self._merge_and_deduplicate(enriched, citation_subtopics)
    # === v0.2.6 结束 ===

    return enriched
```

### 统一写入：`decompose_and_write()` 不变

```python
def decompose_and_write(self, topic: str) -> list[dict]:
    subtopics = asyncio.run(self.decompose(topic))
    if not subtopics:
        return []

    # 统一写 KG（所有来源的 subtopics 一起写，不分开）
    for sibling in subtopics:
        kg.add_child(topic, sibling["sub_topic"])
        kg.add_curiosity(
            topic=sibling["sub_topic"],
            reason=f"Decomposed from: {topic} (source: {sibling.get('source', 'llm')})",
            relevance=7.0,
            depth=5.0,
            original_topic=topic
        )
    return subtopics
```

### `paper_citation_extractor.py` 的改动

移除 `write_to_kg()` 方法，改为只返回结构化数据：

```python
class PaperCitationExtractor:
    def extract_all(self, topic: str, papers: list[dict]) -> list[dict]:
        """只返回数据，不写 KG"""
        # ... 方案 A + 方案 B + 去重 ...
        return [
            {
                "name": "Attention Is All You Need (Vaswani et al., 2017)",
                "source_paper": "...",
                "source_arxiv_id": "...",
                "method": "llm",
                "year": "2017"
            },
            ...
        ]
    # 移除 write_to_kg() — 写入由 decompose_and_write() 统一处理
```

### 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/curiosity_decomposer.py` | 修改 | 新增 `_extract_paper_citations()` 和 `_merge_and_deduplicate()` |
| `core/paper_citation_extractor.py` | 修改 | 移除 `write_to_kg()`，只返回数据 |
| `core/curiosity_agent.py` (run_one_cycle) | 不变 | 调 `decompose_and_write()`，自动获得引文 subtopics |
| `core/spider_agent.py` | 不变 | 调 `decompose_and_enqueue()`，自动获得引文 subtopics |

### 验证方式（不变）

```bash
curl -X POST "http://localhost:4848/api/curious/run" \
  -H "Content-Type: application/json" \
  -d '{"topic":"transformer attention mechanism","depth":"deep"}'

# 查看 KG children（包含 LLM 生成 + 论文引文两类子节点）
curl -s "http://localhost:4848/api/curious/state" | python3 -c "
import json,sys; d=json.load(sys.stdin)
children = d['knowledge']['topics'].get('transformer attention mechanism',{}).get('children',[])
print(f'Total children: {len(children)}')
for c in children:
    print(f'  - {c}')
"
```

_Last updated: 2026-03-29 by R1D3_
_v0.2.6 Fix #3 UPDATED: 论文引文集成到分解流程，由 decompose_and_write() 统一写 KG_

---

## Fix #7: 分解后 parent 没有标记为 exploring（父子关系写入顺序错乱）

**发现时间**: 2026-03-29 by R1D3
**状态**: 待修复

### 问题描述

当前 `run_one_cycle()` 中，`decompose()` 成功后：

```python
# run_one_cycle() 约第 108-139 行
subtopics = asyncio.run(decomposer.decompose(topic))  # topic = A

if subtopics:
    # [B, C, D] 其中 B = best
    next_curiosity["topic"] = B           # 继续探索 B
    kg.add_curiosity(C, parent=A)          # C, D 只写队列，不探索
    kg.add_child(A, C)
    kg.add_curiosity(D, parent=A)
    kg.add_child(A, D)
    kg.add_child(A, B)                     # B 作为 best 也写入 A 的 children
```

**关键缺陷**：

1. **A 在队列里的 status 永远是 `pending`**，从未被标记为 `exploring`
2. `mark_topic_done(B)` 里查找 parent 的逻辑：
   ```python
   for item in state["curiosity_queue"]:
       if item.get("status") == "exploring":
           parent_topic = item["topic"]
   ```
   但 A 从未被标记为 `exploring`，所以这个查找**永远失败**

3. `mark_topic_done(B)` 之后，A 在队列里仍然是 `pending`，不是 `done`

### 当前完整错误流程

```
1. select_next() → A (status=pending)
2. A.known = False → 探索 A，写入 KG[A]
3. decompose(A) → [B, C, D]
   ├── kg.add_curiosity(C, original_topic=A, status=pending)  ← A 没有被标记
   ├── kg.add_child(A, C)
   ├── B = best → next_curiosity["topic"] = B
   └── kg.add_child(A, B)
4. update_curiosity_status(B, "exploring")  ← B 变 exploring
5. 探索 B
6. mark_topic_done(B)
   → 队列里找 status=exploring → 找到 B 自己
   → 尝试 parent_topic → 找不到（A 的 status 是 pending）
   → B.done，但 A 仍然是 pending
7. 下次 run_one_cycle 仍然可能选中 A（因为 A.pending）
```

### 修复方案

在 `decompose_and_write()` 里，分解成功后立即标记 parent 为 exploring：

```python
def decompose_and_write(self, topic: str) -> list[dict]:
    subtopics = asyncio.run(self.decompose(topic))
    if not subtopics:
        return []

    # ⭐ Fix #7: 分解后立即标记 parent 为 exploring
    # 这样 mark_topic_done(child) 能找到 parent
    kg.update_curiosity_status(topic, "exploring")

    for sibling in subtopics:
        kg.add_child(topic, sibling["sub_topic"])
        kg.add_curiosity(
            topic=sibling["sub_topic"],
            reason=f"Decomposed from: {topic}",
            relevance=7.0,
            depth=5.0,
            original_topic=topic,
            parent_topic=topic  # ⭐ 方便追踪
        )

    return subtopics
```

同时修改 `mark_topic_done()`，利用 `parent_topic` 字段正确找到 parent：

```python
def mark_topic_done(topic: str, reason: str) -> None:
    state = _load_state()

    # ⭐ Fix #7: 利用 parent_topic 字段找到 parent
    for item in state.get("curiosity_queue", []):
        if item.get("topic") == topic:
            parent_topic = item.get("parent_topic")
            if parent_topic:
                _update_parent_relation(parent_topic, topic)
                # 如果 parent 的所有 children 都被探索了，标记 parent 为 done
                # （需要检查 parent 的 explored_children 是否等于 children）

    # 原有逻辑：找 status=exploring 的父 topic（保留作为 fallback）
    for item in state.get("curiosity_queue", []):
        if item.get("status") == "exploring":
            parent_topic = item.get("topic")
            if parent_topic and parent_topic != topic:
                _update_parent_relation(parent_topic, topic)
                break

    _save_state(state)
```

### 依赖关系

- Fix #7 依赖 Fix #6（`decompose_and_write()`）的存在
- Fix #7 是 Fix #1 正确工作的前提

_Last updated: 2026-03-29 by R1D3_
_v0.2.6 Fix #7: 分解后 parent 未标记 exploring 导致父子关系写入失败_

---

## Fix #8: `add_curiosity` 去重逻辑漏洞（已完成 topic 会被重复添加）

**发现时间**: 2026-03-29 by R1D3
**状态**: 待修复

### 问题描述

```python
# knowledge_graph.py 第 105-107 行
for item in state["curiosity_queue"]:
    if item["topic"].lower() == topic.lower() and item["status"] != "done":
        return  # ← 已存在且未完成，才跳过
# 漏洞：如果 status == "done"，继续往下执行
```

**错误场景**：
```
1. topic A 被探索，status = done
2. later，parent P decomposition 生成 A 作为 subtopic
3. add_curiosity(A) 检查：
   - A 存在于队列，status = done
   - "done" != "done" → False
   - 不 return，继续
4. 新增一条 A 的队列条目，status = pending
5. 队列里现在有两条 A（一条 done，一条 pending）
```

### 修复

```python
# 改成：只要队列里已存在，就跳过
for item in state["curiosity_queue"]:
    if item["topic"].lower() == topic.lower():
        return  # ← 去掉 status 检查
```

---

## Fix #9: `decompose()` 无法访问 papers，导致论文引文提取无法工作

**发现时间**: 2026-03-29 by R1D3
**状态**: 待修复

### 问题描述

```
run_one_cycle() 里：
1. explorer.explore(A) → parent_result，包含 papers
2. parent_findings = {..., "papers": parent_result.get("papers", [])}
3. decomposer.decompose(A)  ← 只传了 topic，没有 papers！
4. decompose() 内部无法获取这些 papers
5. Fix #3 的 _extract_paper_citations() 无法工作
```

### 修复

**方案 1（推荐）：传入 papers 参数**

```python
# curiosity_decomposer.py
async def decompose(self, topic: str, papers: list[dict] = None) -> list[dict]:
    self._papers = papers or []  # ← 存储起来给 _extract_paper_citations 用
    ...

# curiosity_agent.py run_one_cycle() 里：
subtopics = asyncio.run(decomposer.decompose(topic, papers=parent_findings.get("papers", [])))
```

**方案 2：通过 kg state 传递**

papers 已经在 KG 里（Layer2 分析后写入 KG），`decompose()` 通过 `self.kg`（即 state dict）读取：
```python
# 在 decompose() 末尾或 _extract_paper_citations() 里
stored_papers = self.kg.get("knowledge", {}).get("topics", {}).get(topic, {}).get("papers", [])
```

### KG 里 papers 字段的位置

Layer2 之后，`kg.add_knowledge(topic, sources=sources)` 写入了 papers：
```python
kg.add_knowledge(topic, depth=5, summary=..., sources=parent_findings["sources"])
```
但 papers 不在 sources 里。需要在 `add_knowledge()` 或者 `explorer.explore()` 的返回值里确保 papers 被写入 KG，并且 `decompose()` 能读到。

---

## Fix #10: `_cascade_fallback` 的 `kg_fallback` 使用还不存在的 children（循环依赖）

**发现时间**: 2026-03-29 by R1D3
**状态**: 待修复

### 问题描述

```python
# curiosity_decomposer.py _cascade_fallback() 末尾
kg_candidates = self._get_kg_children(topic)
if kg_candidates:
    return [{"sub_topic": c, "verified": True, "source": "kg_fallback"} for c in kg_candidates]
```

`self.kg` 传入的是 `state`（整个状态字典），`_get_kg_children()` 访问的是：
```python
return self.kg.get("topics", {}).get(topic, {}).get("children", [])
# 即 state["topics"][topic]["children"]
```

**但问题是**：topic 的 children 是在 `decompose()` **之后**才写入 KG 的。如果一个 topic 还没有被 decomposition 过，它的 children 就是空的，`kg_fallback` 永远不触发。

**更严重的是**：如果 `_cascade_fallback` 是因为"没有通过验证的 candidates"触发的，它返回 `kg_fallback` 作为备选。但这些 kg children 本身也是从 LLM candidates 来的，只是已经被验证过了。

### 分析

`kg_fallback` 的设计意图是：当 LLM candidates 全部验证失败时，用 KG 里已有的 children 作为备选。但：

1. 刚探索的新 topic，KG 里没有 children → fallback 无效
2. 老 topic 有 children，但 children 是上一次 decomposition 写的 → fallback 有效

**这是一个低优先级的问题**，只在 topic 被重复 decomposition 时有意义。可以暂时不改。

---

## 问题汇总（按优先级）

| # | 问题 | 优先级 | 修复 |
|---|------|--------|------|
| 7 | 分解后 parent 未标记 exploring | P0 | decompose_and_write() 里加 update_curiosity_status |
| 8 | add_curiosity 去重逻辑漏洞 | P0 | 去掉 status 检查 |
| 9 | decompose() 无法访问 papers | P1 | decompose(topic, papers) 传入参数 |
| 6 | 分解和写入分散在两处 | P0 | 新增 decompose_and_write() |
| 1 | SpiderAgent 没有 decomposition | P0 | SpiderAgent 调 decompose_and_write() |
| 2 | DreamAgent 闭环未形成 | P0 | SpiderAgent 探索后 decomposition |
| 3 | 论文引文没有变成子节点 | P1 | _extract_paper_citations() 集成到 decompose() |
| 5 | API 没有 decomposition | P1 | api_run() 调 decompose_and_write() |
| 4 | 网页引用没有变成子节点 | P2 | WebCitationExtractor（低优先级） |
| 10 | kg_fallback 循环依赖 | P3 | 低优先级，可不改 |

_Last updated: 2026-03-29 by R1D3_
_v0.2.6 Fix #7-10: 完整问题清单_

---

## 实现记录：方案 A 完整实施（Step 1 + Step 2）

**实施时间**: 2026-03-29
**状态**: ✅ 核心功能已实现

### 已完成的改动

#### 1. KG schema 变更 ✅

**文件**: `core/knowledge_graph.py`

- `add_knowledge()`: 新 topic 初始化时增加 `cites: []` 和 `cited_by: []` 字段
- 已有 topic 兼容：不存在这两个字段时自动初始化为空列表
- `add_child()`: 新建 parent topic 时也初始化 `cites` 和 `cited_by`

#### 2. 新增 `add_citation()` 函数 ✅

**文件**: `core/knowledge_graph.py`

```python
def add_citation(citing_topic: str, cited_topic: str) -> None:
    """
    添加论文引用关系（双向写入 cites + cited_by）
    citing_topic cites cited_topic
    """
    # 写入 citing_topic.cites
    # 写入 cited_topic.cited_by
```

#### 3. KG Overview 支持 cites 边 ✅

**文件**: `core/knowledge_graph.py` — `get_kg_overview()`

- 新增 `cites_count` 和 `cited_by_count` 字段到节点数据
- 新增 `type: "cites"` 边类型

#### 4. Explorer Layer2 集成引文提取 ✅

**文件**: `core/explorer.py` — `_layer2_arxiv()`

```python
# Layer2 分析 papers 之后
if papers:
    extractor = PaperCitationExtractor()
    citations = extractor.extract_all(topic, papers)
    for c in citations:
        kg.add_citation(topic, c["name"])
        kg.add_curiosity(
            topic=c["name"],
            reason=f"Cited by: {topic}",
            relevance=7.0, depth=5.0,
            original_topic=topic,
            topic_type="citation"
        )
```

#### 5. PaperCitationExtractor 改造 ✅

**文件**: `core/paper_citation_extractor.py`

- 移除 `write_to_kg()` 方法（不再自己写 KG）
- 只返回结构化数据：`extract_all(topic, papers) -> list[dict]`

#### 6. UI 支持 cites 可视化 ✅

**文件**: `ui/index.html`

- `buildGraphData()`: 新增 cites 边构建逻辑（和 children 分开）
- 边样式：紫色点划线（`#e040fb`, `8,4` dash）
- 图例：新增"紫点线 = 论文引用"
- 控制面板：新增"论文引用"复选框
- `toggleLinkType()`: 支持 cites 切换

### 验证结果

```
curl http://localhost:4848/api/kg/overview
→ cites edges: 2
  [cites] LLM self-reflection mechanisms → Reflexion
  [cites] LLM self-reflection mechanisms → Self-Refine

KG 节点:
  LLM self-reflection mechanisms: cites=['Reflexion', 'Self-Refine']
  Reflexion: cited_by=['LLM self-reflection mechanisms']
  Self-Refine: cited_by=['LLM self-reflection mechanisms']
```

### 剩余工作

| 工作 | 状态 | 说明 |
|------|------|------|
| Fix #1 SpiderAgent decomposition | 待修复 | 依赖 Fix #6 |
| Fix #2 DreamAgent 闭环 | 待修复 | 依赖 Fix #1 |
| Fix #5 API decomposition | 待修复 | 依赖 Fix #6 |
| Fix #6 decompose_and_write() | 待实现 | 基础设施 |
| Fix #7 parent 未标记 exploring | 待修复 | 依赖 Fix #6 |
| Fix #8 add_curiosity 去重漏洞 | 待修复 | 独立 bug |
| Fix #9 decompose() 无法访问 papers | 已绕过 | Layer2 独立调用引文提取，不走 decompose |
| Fix #10 kg_fallback 循环 | P3 | 低优先级 |

**注意**: Fix #9 已通过"绕过"方式解决——引文提取不经过 `decompose()`，而是在 Layer2 里独立调用，不需要 `decompose()` 访问 papers。

_Last updated: 2026-03-29 by R1D3_
_v0.2.6: Plan A fully implemented (KG cites + UI + Layer2 integration)_

---

# ============================================================
# OpenCode 修复清单 — v0.2.6 完整修复指南
# ============================================================
# 更新时间: 2026-03-29 by R1D3
# 目的: 为 OpenCode 提供清晰、可执行的修复清单
# ============================================================

## 执行顺序（P0 先修，互相依赖）

```
Step 1: Fix #8（独立）
Step 2: Fix #6（基础设施，所有调用方依赖它）
Step 3: Fix #7（依赖 Fix #6）
Step 4: Fix #1（依赖 Fix #6）
Step 5: Fix #2（依赖 Fix #1）
Step 6: Fix #5（依赖 Fix #6）
```

---

## Fix #8: add_curiosity 去重漏洞（独立，P0）

**问题**: 只要队列里已存在 topic（无论什么 status），就跳过，不应该重新加入
**文件**: `core/knowledge_graph.py`

**修改位置**: `add_curiosity()` 函数，约第 105-107 行

**现有代码**:
```python
for item in state["curiosity_queue"]:
    if item["topic"].lower() == topic.lower() and item["status"] != "done":
        return
```

**改为**:
```python
for item in state["curiosity_queue"]:
    if item["topic"].lower() == topic.lower():
        return
```

---

## Fix #6: 新增 decompose_and_write() 统一 KG 写入路径（基础设施，P0）

**问题**: 分解和 KG 写入分散在 curious_agent.py 和 spider_agent.py 两处，应该集中
**文件**: `core/curiosity_decomposer.py`

**修改**: 在 `CuriosityDecomposer` 类末尾新增方法

**新增代码**:
```python
def decompose_and_write(self, topic: str) -> list[dict]:
    """
    完整流程：decompose + 统一写 KG

    所有调用方（SpiderAgent / run_one_cycle / api_run）都调这个方法。
    decomposition 结果自动写入 KG，不在调用方分散。

    Args:
        topic: 待分解的 topic

    Returns:
        subtopics 列表（格式同 decompose()）
    """
    import asyncio
    try:
        asyncio.get_running_loop()
        # 在已有 event loop 内：启动专属线程执行（避免循环引用）
        import threading
        result_holder = []

        def _run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result_holder.append(loop.run_until_complete(self.decompose(topic)))
            finally:
                loop.close()

        t = threading.Thread(target=_run_in_thread)
        t.start()
        t.join()
        subtopics = result_holder[0] if result_holder else []

    except RuntimeError:
        # 正常路径：没有 running loop，直接 asyncio.run
        subtopics = asyncio.run(self.decompose(topic))

    if not subtopics:
        return []

    # Fix #7: 分解后立即标记 parent 为 exploring（这样 mark_topic_done 能找到它）
    from core import knowledge_graph as kg
    kg.update_curiosity_status(topic, "exploring")

    # 统一写 KG
    for sibling in subtopics:
        s_topic = sibling["sub_topic"]
        s_strength = sibling.get("signal_strength", "unknown")
        s_relevance = 7.0 if s_strength == "strong" else (6.0 if s_strength == "medium" else 5.0)
        s_depth = 6.0 if s_strength == "strong" else (5.5 if s_strength == "medium" else 5.0)

        kg.add_child(topic, s_topic)
        kg.add_curiosity(
            topic=s_topic,
            reason=f"Decomposed from: {topic}",
            relevance=float(s_relevance),
            depth=float(s_depth),
            original_topic=topic  # ← 关键：显式存储 parent，Fix #7 依赖这个字段
        )

    return subtopics

---

## Fix #7: mark_topic_done 用 original_topic 找 parent（依赖 Fix #6）
```

---

## Fix #7: mark_topic_done 用 original_topic 找 parent（依赖 Fix #6）

**问题**: `mark_topic_done()` 原来的 parent 查找逻辑是错的——它找 `status=="exploring"` 的 queue item，然后用其 `topic` 字段当 parent。但 parent 从未被标记为 exploring（只有 Fix #6 的 `decompose_and_write` 才会标记），所以永远找不到。

**正确方案**: 利用 Fix #6 在 children 的 queue item 里存储的 `original_topic` 字段，`mark_topic_done` 直接读这个字段找 parent。

**文件**: `core/knowledge_graph.py` — `mark_topic_done()` 函数

**修改位置**: 约第 330-340 行（parent 查找那段）

**现有代码**（找 status=="exploring" 的 item）:
```python
for queue_item in state.get("curiosity_queue", []):
    if queue_item.get("status") == "exploring":
        parent_topic = queue_item.get("topic")  # Bug: topic 不是 parent 字段！
        if parent_topic and parent_topic != topic:
            _update_parent_relation(parent_topic, topic)
            break
```

**改为**（从 completed item 的 original_topic 字段读 parent）:
```python
# 从当前 topic 的队列条目读取 original_topic（即 parent）
parent_topic = None
for item in state.get("curiosity_queue", []):
    if item.get("topic") == topic:
        parent_topic = item.get("original_topic")  # Fix #6 存储的 parent
        break

# 如果有 parent，写入父子关系
if parent_topic:
    _update_parent_relation(parent_topic, topic)
```

---

## Fix #1: SpiderAgent 集成 decomposition（依赖 Fix #6，P0）

**问题**: SpiderAgent 探索完 topic 后不会 decomposition，KG 永远无法形成树状结构
**文件**: `core/spider_agent.py`

**修改 1**: 新增 `_decompose_and_enqueue()` 方法

```python
def _decompose_and_enqueue(self, topic: str):
    """
    探索完成后触发 decomposition，把 subtopics 加入队列。
    使用统一的 decompose_and_write() 方法。
    """
    try:
        from core.curiosity_decomposer import CuriosityDecomposer
        from core.llm_manager import LLMManager
        from core.provider_registry import init_default_providers
        from core import knowledge_graph as kg
        from core.config import get_config

        config = get_config()
        llm_config = {"providers": {}, "selection_strategy": "capability"}
        for p in config.llm_providers:
            llm_config["providers"][p.name] = {
                "api_url": p.api_url,
                "timeout": p.timeout,
                "enabled": p.enabled,
                "models": [
                    {"model": m.model, "weight": m.weight, "capabilities": m.capabilities, "max_tokens": m.max_tokens}
                    for m in p.models
                ]
            }

        llm_manager = LLMManager.get_instance(llm_config)
        registry = init_default_providers()
        state = kg.get_state()

        decomposer = CuriosityDecomposer(
            llm_client=llm_manager,
            provider_registry=registry,
            kg=state
        )

        subtopics = decomposer.decompose_and_write(topic)
        print(f"[SpiderAgent] Decomposed '{topic}' into {len(subtopics)} subtopics")
        for st in subtopics:
            print(f"  + {st['sub_topic']} ({st.get('signal_strength', 'unknown')})")
    except Exception as e:
        print(f"[SpiderAgent] Decompose failed for '{topic}': {e}")
```

**修改 2**: 在 `_explore_topic()` 末尾（`self._notify_dream_agent(topic, result)` 之后）追加一行

```python
# === v0.2.6 Fix #1: 探索完成后触发 decomposition ===
self._decompose_and_enqueue(topic)
# === v0.2.6 结束 ===
```

---

## Fix #2: DreamAgent 洞察触发 SpiderAgent 新探索（依赖 Fix #1，P0）

**问题**: DreamAgent 生成 insights 后没有形成探索闭环
**文件**: `core/spider_agent.py` — `_process_inbox_cycle()`

**现有代码**:
```python
def _process_inbox_cycle(self):
    inbox_items = kg.fetch_and_clear_dream_inbox()
    for item in inbox_items:
        topic = item.get("topic")
        if not topic or kg.is_topic_completed(topic):
            continue
        result = self._explore_topic(topic, source_insight)
        if result:
            cycle_topics.append(topic)
```

**改为**（在 `_explore_topic` 之后追加 decomposition）:
```python
def _process_inbox_cycle(self):
    inbox_items = kg.fetch_and_clear_dream_inbox()
    if not inbox_items:
        return

    cycle_topics = []

    for item in inbox_items:
        topic = item.get("topic")
        source_insight = item.get("source_insight", "")

        if not topic:
            continue
        if kg.is_topic_completed(topic):
            continue

        result = self._explore_topic(topic, source_insight)

        if result:
            cycle_topics.append(topic)
            self._explored_topics.append(topic)
            if len(self._explored_topics) > 100:
                self._explored_topics = self._explored_topics[-100:]

            # === v0.2.6 Fix #2: 探索完成后触发 decomposition（形成闭环）===
            self._decompose_and_enqueue(topic)
            # === v0.2.6 结束 ===

    if len(cycle_topics) >= 2:
        self._apply_hebbian_learning(cycle_topics)
```

**闭环流程**:
```
DreamAgent 生成 insight
  → kg.add_to_dream_inbox(trigger_topic)
  → SpiderAgent 消费 inbox，探索 trigger_topic
  → SpiderAgent decomposition，产生 children
  → SpiderAgent 通知 DreamAgent（via notification_queue）
  → DreamAgent 对新 children 做远距离联想
  → 新 insight → 新 inbox → 新探索 ...
```

---

## Fix #5: API /api/curious/run 支持 decomposition（依赖 Fix #6，P1）

**问题**: API 触发探索时不走 decomposition，无法形成树状结构
**文件**: `curious_api.py` — `api_run()` 函数

**修改位置**: 在 `writer.process(...)` 之后，`return jsonify(...)` 之前

**追加代码**:
```python
# 现有代码（保留）
if quality >= 7.0:
    writer = AgentBehaviorWriter()
    writer.process(result["topic"], findings, quality, result.get("sources", []))

# === v0.2.6 Fix #5: 触发 decomposition ===
# 注意：api_run() 内没有 llm_manager/registry，必须现场初始化（参考 Fix #1）
from core.curiosity_decomposer import CuriosityDecomposer
from core.llm_manager import LLMManager
from core.provider_registry import init_default_providers
from core import knowledge_graph as kg
from core.config import get_config

config = get_config()
llm_config = {"providers": {}, "selection_strategy": "capability"}
for p in config.llm_providers:
    llm_config["providers"][p.name] = {
        "api_url": p.api_url,
        "timeout": p.timeout,
        "enabled": p.enabled,
        "models": [
            {"model": m.model, "weight": m.weight, "capabilities": m.capabilities, "max_tokens": m.max_tokens}
            for m in p.models
        ]
    }

llm_manager = LLMManager.get_instance(llm_config)
registry = init_default_providers()
state = kg.get_state()

decomposer = CuriosityDecomposer(
    llm_client=llm_manager,
    provider_registry=registry,
    kg=state
)
try:
    subtopics = decomposer.decompose_and_write(result["topic"])
    print(f"[API] Decomposed '{result['topic']}' into {len(subtopics)} subtopics")
except Exception as e:
    print(f"[API] Decompose failed: {e}")
# === v0.2.6 结束 ===

return jsonify({...})  # 现有 return
```

---

## Fix #4: 网页引用提取（P2，低优先级）

**问题**: Layer1 搜索结果的来源网页，如果本身有外部引用，没有被提取为子节点
**文件**: `core/explorer.py` — `_layer1_search()` 或新增 `core/web_citation_extractor.py`

**策略**: 参考 `paper_citation_extractor.py` 的模式，新增 `WebCitationExtractor`

**实现优先级**: P2（论文引文的价值更高，可后续实现）

---

## 修改文件汇总

| 文件 | 涉及 Fix | 操作 |
|------|---------|------|
| `core/knowledge_graph.py` | #7 | 修改 `mark_topic_done()` |
| `core/curiosity_decomposer.py` | #6 | 新增 `decompose_and_write()` 方法 |
| `core/spider_agent.py` | #1, #2 | 新增 `_decompose_and_enqueue()` 方法；修改 `_explore_topic()` 和 `_process_inbox_cycle()` |
| `curious_api.py` | #5 | 在 `api_run()` 末尾追加 decomposition 调用 |
| `core/web_citation_extractor.py` | #4（可选） | 新建文件 |

---

## 验证命令（修复后执行）

```bash
cd /root/dev/curious-agent

# 1. 启动 CA
bash run_curious.sh

# 2. 触发一次探索
curl -s -X POST "http://localhost:4848/api/curious/run?topic=transformer+attention+mechanism&depth=deep" | python3 -c "import json,sys; d=json.load(sys.stdin); print('Status:', d.get('status'), 'Action:', d.get('action'))"

# 3. 检查 KG 是否有 children（decomposition 生效）
sleep 5
curl -s "http://localhost:4848/api/curious/state" | python3 -c "
import json,sys
d=json.load(sys.stdin)
topics = d.get('knowledge',{}).get('topics',{})
has_children = sum(1 for t in topics.values() if t.get('children'))
has_parents = sum(1 for t in topics.values() if t.get('parents'))
has_cites = sum(1 for t in topics.values() if t.get('cites'))
print(f'children edges: {has_children}, parents edges: {has_parents}, cites edges: {has_cites}')
for k,v in topics.items():
    if v.get('children') or v.get('cites'):
        print(f'  {k}: children={v.get(\"children\")}, cites={v.get(\"cites\")}')
"

# 4. 检查 KG 概览
curl -s "http://localhost:4848/api/kg/overview" | python3 -c "
import json,sys
d=json.load(sys.stdin)
edges = d.get('edges', [])
child_edges = [e for e in edges if e['type']=='child_of']
cites_edges = [e for e in edges if e['type']=='cites']
print(f'Total edges: {len(edges)}')
print(f'  decomposition: {len(child_edges)}')
print(f'  cites: {len(cites_edges)}')
"
```

---

_Last updated: 2026-03-29 13:55 by R1D3 + weNix_
_v0.2.6: ✅ 全部修复完成（OpenCode 执行）_
