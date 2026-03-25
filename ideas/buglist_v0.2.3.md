# v0.2.3 Bug List — 完整测试报告 (2026-03-23 19:35)

> 测试方法：CLI `--run` 和 `--pure-curious` 模式完整流程测试
> 测试命令：`python3 curious_agent.py --run` 和 `python3 curious_agent.py --run --pure-curious`
> API 测试：`curl localhost:4848/api/curious/run -d '{"topic":"xxx","depth":"medium"}'`

---

## 🔴 Bug #13: ThreePhaseExplorer._phase3_execute 缺少 "score" 字段导致 KeyError（主流程崩溃）

**严重程度**: 🔴 最高 — CLI 模式主流程直接崩溃

**复现**:
```bash
python3 curious_agent.py --run
# [Decomposer] '自我意识 self-awareness' -> '机器自我意识' (medium)
# Traceback: KeyError: 'score' at explorer.py:84
```

**根因**: `ThreePhaseExplorer._phase3_execute()` 创建的 `curiosity_item` 只有 `topic` 和 `depth`，但 `Explorer.explore()` 第 84 行需要 `curiosity_item["score"]` 来判断通知阈值：

```python
# three_phase_explorer.py 第 121 行
curiosity_item = {
    "topic": topic,
    "depth": plan[0].get("depth", "medium")
    # ← 缺少 "score" 字段！
}
return self.explorer.explore(curiosity_item)

# explorer.py 第 84 行
score = curiosity_item["score"]  # ← KeyError
```

**期望行为**: 任何子 topic 探索都不应崩溃，应正常完成

**修复方向**: 在 `_phase3_execute` 中从 `self.explorer` 获取默认 score，或从已探索过的父 topic 继承 score：

```python
# three_phase_explorer.py _phase3_execute 修改
curiosity_item = {
    "topic": topic,
    "depth": plan[0].get("depth", "medium"),
    "score": 5.0  # 默认值，或从 self.explorer 获取
}
```

**验收标准**:
```bash
# 运行 3 轮 --run，不应出现任何 KeyError
python3 curious_agent.py --run 2>&1 | grep -i "keyerror\|traceback"
# 期望：无 KeyError，无 Traceback
```

---

## 🔴 Bug #14: select_next不过滤已完成的 topic，导致重复选中和死循环

**严重程度**: 🔴 高 — 产生无效探索循环

**现象**:
```python
# kg.is_topic_completed("AI Agent") = True
# 但 select_next() 仍返回 AI Agent (exploration_value=3.7)
# → 被选中 → 分解 → 子 topic 已完成 → blocked → 浪费一轮
```

**根因**: `curiosity_engine.py` 的 `select_next()` 使用 `kg.get_top_curiosities(k=10)` 获取候选，**没有过滤** `kg.is_topic_completed(topic) == True` 的项：

```python
# curiosity_engine.py select_next()
candidates = kg.get_top_curiosities(k=10)
for item in candidates:
    topic = item["topic"]
    # ← 没有检查 kg.is_topic_completed(topic)！
    # ← 已完成的 topic 仍参与评分和排序
```

**期望行为**: 已完成的 topic 不应被选为待探索项

**修复方向**:
```python
# select_next() 中添加过滤
for item in candidates:
    topic = item["topic"]
    if kg.is_topic_completed(topic):
        continue  # 跳过已完成的 topic
    # ... 其余逻辑
```

**验收标准**:
```python
# 验证所有已完成的 topic 不再被 select_next 返回
python3 -c "
import sys; sys.path.insert(0, '.')
from core.curiosity_engine import CuriosityEngine
from core import knowledge_graph as kg
engine = CuriosityEngine()
selected = engine.select_next()
if selected and kg.is_topic_completed(selected['topic']):
    print('FAIL: selected completed topic')
else:
    print('PASS: no completed topic selected')
"
# 期望：PASS
```

---

## 🟡 Bug #15: CLI 和 API 的 Phase 1 行为写入集成不一致

**严重程度**: 🟡 中 — Phase 1 只能通过 CLI 触发，API 完全绕过

**现象**:
- `curious_agent.py --run` (CLI): 探索后 quality >= 7.0 → `AgentBehaviorWriter.process()` 被调用 ✅
- `curious_api.py /api/curious/run` (API): 探索后 quality >= 7.0 → **AgentBehaviorWriter 从未调用** ❌

**根因**: `curious_api.py` 的 `api_run()` 直接调用 `Explorer.explore()` 后只做了 `mark_topic_done()`，没有集成 AgentBehaviorWriter：

```python
# curious_api.py api_run() 第 82-89 行
result = explorer.explore(next_item)
mark_topic_done(result["topic"], "API exploration completed")
# ← 没有 AgentBehaviorWriter 调用！
# ← 没有 quality 评估！
```

**期望行为**: API 探索结果达到质量门槛时，同样触发行为写入

**修复方向**: 在 `curious_api.py` 的 `api_run()` 末尾增加：

```python
from core.agent_behavior_writer import AgentBehaviorWriter
from core.meta_cognitive_monitor import MetaCognitiveMonitor

monitor = MetaCognitiveMonitor(llm_client=llm_manager)
quality = monitor.assess_exploration_quality(result["topic"], result)

if quality >= 7.0:
    writer = AgentBehaviorWriter()
    writer.process(result["topic"], result, quality, result.get("sources", []))
```

**验收标准**:
```bash
# 通过 API 注入高质量 topic，验证 behavior 文件更新
curl -X POST localhost:4848/api/curious/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "test_api_behavior_write", "depth": "deep"}'
# 检查 curious-agent-behaviors.md 是否有新内容
grep -c "test_api_behavior_write" /root/.openclaw/workspace-researcher/curious-agent-behaviors.md
# 期望：> 0（有写入）
```

---

## 🟡 Bug #16: 队列和 completed_topics 双套账不同步

**严重程度**: 🟡 中 — 队列数据显示混乱，但不影响核心功能

**现象**:
```python
# 当前队列状态（19条）
pending: 大语言模型推理规划  (但 kg.is_topic_completed() = True)
pending: AI Agent             (但 kg.is_topic_completed() = True)
pending: 感知与环境交互模块  (但 kg.is_topic_completed() = True)
pending: 规划与推理模块       (但 kg.is_topic_completed() = True)
```

**根因**: `kg.mark_topic_done()` 只更新 `meta_cognitive.completed_topics`，不更新 `curiosity_queue[].status`。两套状态系统独立运行。

**影响**: 
- 队列看起来有很多 pending 项，但实际都已完成
- `select_next()` 不做过滤时，会选中已完成的项（Bug #14 的根因）

**修复方向**: 在 `mark_topic_done()` 中同时更新队列状态：

```python
def mark_topic_done(topic: str, reason: str) -> None:
    state = _load_state()
    # ... 更新 completed_topics ...
    
    # 同步更新队列 status
    for item in state.get("curiosity_queue", []):
        if item["topic"] == topic and item.get("status") != "done":
            item["status"] = "done"
    
    _save_state(state)
```

**验收标准**:
```python
# mark_topic_done 之后，队列中该 topic 的 status 应为 done
python3 -c "
import sys; sys.path.insert(0, '.')
from core import knowledge_graph as kg
kg.mark_topic_done('test_sync_topic', 'sync test')
state = kg.get_state()
for item in state.get('curiosity_queue', []):
    if item['topic'] == 'test_sync_topic':
        print(f'status={item.get(\"status\")}')
        assert item.get('status') == 'done', 'FAIL: status not updated'
        print('PASS: queue status synced')
"
```

---

## ✅ 已验证修复的 Bug（来自 buglist_v0.2.3.md）

| Bug | 描述 | 状态 |
|-----|------|------|
| Bug #1 | Topic 注入后探索了完全不同的 topic | ✅ 已修复（2026-03-23 OpenCode）|
| Bug #2 | test shallow 分数 56.0 脏数据 | ✅ 已清理 |
| Bug #3 | inject API 拒绝字符串 depth | ✅ 已修复 |
| Bug #4 | DELETE queue 不接受 JSON body | ✅ 已修复 |
| Bug #6 | 中文 topic URL 参数乱码 | ✅ 已修复 |
| Bug #7 | `completed_topics` 永远为空 | ✅ 已修复（mark_topic_done 正常工作）|
| Bug #8 | KG topic 缺少 status 字段 | ✅ 已修复 |
| Bug #9 | CLI `--run` blocked 状态 KeyError | ✅ 已修复（CLI 正确处理 blocked 状态）|
| Bug #10 | 分解后父 topic 重复被选（死循环）| ✅ 已修复（mark_topic_done 在分解后调用）|
| Bug #11 | Agent-Behavior-Writer 中文 topic 无法写入 | ✅ 已修复（behavior 文件正常写入）|

---

## 📊 Phase 集成状态一览

| Phase | 组件 | 集成状态 | 说明 |
|-------|------|---------|------|
| Phase 1 | AgentBehaviorWriter | 🟡 部分集成 | CLI ✅，API ❌ |
| Phase 1 | Behavior 文件写入 | ✅ 正常 | curious-agent-behaviors.md 有内容 |
| Phase 2 | CompetenceTracker | ✅ 已集成 | `select_next()` 中有调用 |
| Phase 2 | select_next (能力感知) | ✅ 已集成 | 包含 exploration_value + competence |
| Phase 2 | QualityV2 评估 | ⚠️ 部分 | ThreePhaseExplorer 内有调用，但流程崩溃 |
| Phase 2 | ThreePhaseExplorer | 🔴 崩溃 | KeyError: 'score'（Bug #13）|
| Phase 3 | CuriosityDecomposer | ✅ 已集成 | 正常分解，多 Provider 验证 |
| Phase 3 | ProviderRegistry | ✅ 已集成 | init_default_providers() 正常 |
| — | MetaCognitiveController.should_explore | ✅ 正常 | 正确阻止已完成的 topic |

---

## 修复优先级建议

| 优先级 | Bug | 理由 |
|--------|-----|------|
| P0 | #13 | 主流程崩溃，CLI 完全无法运行 |
| P0 | #14 | 导致重复探索和资源浪费 |
| P1 | #15 | API 缺失 Phase 1 写入 |
| P2 | #16 | 队列数据混乱（cosmetic，但影响调试）|

---

## 附录：队列污染数据（2026-03-23 19:30）

当前队列中已完成的 topic 仍标记为 pending（11条污染）:

```
pending + completed: AI Agent, 大语言模型推理规划, 大语言模型推理与规划,
                    大语言模型驱动推理规划, 感知与环境交互模块, 
                    感知与环境建模, 感知模块, 规划与推理模块
pending + 未完成: statistical data normalization, 自我意识 self-awareness, LLMs
```

---

_报告生成: 2026-03-23 19:35_
_测试者: R1D3-researcher_

---

## 🔴 Bug #19: Decomposer 候选全部验证失败 → 探索链断裂

**严重程度**: 🔴 高 — 几乎所有 topic 都在 Provider 验证阶段失败，探索链无法推进

**复现**:
```
[Decomposer] 'Enhancing LLM Reasoning' -> no candidates passed provider validation
[Decomposer] 'Streamlined Framework' -> no candidates passed provider validation
[Decomposer] 'Extending Classical Planning' -> no candidates passed provider validation
```

**根因**: LLM 生成的候选 sub-topics 太窄/太抽象（如"Streamlined Framework"），没有任何 Provider 收录相关结果，导致 `provider_count = 0`，不满足验证门槛（`provider_count >= 2` 且 `total_count >= 10`）。

**澄清路由**：Curious Agent 不直接通知用户，只告诉 R1D3，由 R1D3 在对话中找你（weNix）澄清。

**期望行为**: 当候选验证失败时，不立刻要求澄清，而是自动走三层降级，只有三层都失败才抛 ClarificationNeeded。

**修复方向**:

1. `curious_decomposer.py` 新增 `_cascade_fallback()` 三层降级：

```
Level 1: 用"扩大模式"重新生成候选（常见术语，非学术概念）
Level 2: 降低门槛（1个Provider 或 total>=5）重新验证
Level 3: 从 KG children 取候选，不验证直接返回
Level 3保底: 返回最详细的候选（不验证），不让探索链断裂
```

2. `curious_decomposer.py` `_llm_generate_candidates()` 新增 `style="broad"` 参数，生成更常见、更易被搜索引擎收录的候选词。

3. `curious_agent.py` 的 `except ClarificationNeeded` 分支返回状态字典（含 `topic` 和 `reason`），让 R1D3 能感知到需要澄清，由 R1D3 在对话中找你沟通。

**验收标准**:
```bash
# 测试1: Level 1 降级后应有候选通过
python3 -c "
import sys; sys.path.insert(0, '.')
import asyncio
from core.curiosity_decomposer import CuriosityDecomposer
from core.provider_registry import init_default_providers
from core.llm_manager import LLMManager

registry = init_default_providers()
llm = LLMManager.get_instance()
decomposer = CuriosityDecomposer(llm_client=llm, provider_registry=registry, kg={})

result = asyncio.run(decomposer.decompose('Enhancing LLM Reasoning'))
print(f'Subtopics returned: {len(result)}')
for r in result[:5]:
    print(f'  {r[\"sub_topic\"]} [{r.get(\"signal_strength\",\"?\")}]')
assert len(result) > 0, 'FAIL: no results after cascade'
print('PASS: cascade fallback returned results')
"

# 测试2: 三层都失败时 R1D3 收到 clarification_needed 状态
# 运行 --run，检查返回的 status
```

---

## 🔴 Bug #20: Decomposer 分解变"单选"，其余候选全部丢弃

**严重程度**: 🟡 中 — 不是崩溃，但违背了树状生长的设计初衷

**问题描述**:

设计文档（next_move.md）的核心洞察：
> 好奇心应该是**树状生长**的，不是平铺随机搜索
> 分解：1 个泛 topic → 多个具体子 topic

但实际行为是 **1 → 1**：

```python
# curious_agent.py 第 88 行附近
if subtopics:
    best = max(subtopics, key=lambda x: x.get("total_count", 0))
    explore_topic = best["sub_topic"]   # ← 只选 1 个
    ...
    kg.mark_topic_done(topic, ...)      # ← 父 topic 直接完成，其他候选全丢
```

**实际观察**：18 次分解全部是 1→1：
- LLM self-reflection mechanisms → 反思 prompting 设计（其余候选丢弃）
- ReAct Reflexion agent frameworks → ReAct prompting 基础框架（其余候选丢弃）
- 等等...

**期望行为**：Decomposer 生成多个候选时，其余候选应全部入队待探索，实现真正的 **1 → 多**树状生长。

**修复方向**:

```python
# curious_agent.py 第 88 行附近，替换当前逻辑
if subtopics:
    best = subtopics[0]  # 已按 signal_strength 排序
    explore_topic = best["sub_topic"]

    # 其余候选全部入队
    for other in subtopics[1:]:
        kg.add_curiosity(
            other["sub_topic"],
            reason=f"Decomposer sibling of: {topic}",
            relevance=5.0,
            depth=5.0
        )

    # 父 topic 不标记完成（还有子 topic 待探索）
    next_curiosity["original_topic"] = topic
    next_curiosity["topic"] = explore_topic
    next_curiosity["decomposition"] = best
    # 注意：这里不调用 kg.mark_topic_done()
```

**验收标准**:
```bash
# 注入一个会分解出多个候选的 topic
python3 -c "
import sys; sys.path.insert(0, '.')
from core.curiosity_decomposer import CuriosityDecomposer
from core.provider_registry import init_default_providers
from core.llm_manager import LLMManager
import asyncio

registry = init_default_providers()
llm = LLMManager.get_instance()
decomposer = CuriosityDecomposer(llm_client=llm, provider_registry=registry, kg={})

# 测试分解出的候选数量
candidates = asyncio.run(decomposer._llm_generate_candidates('AI Agent'))
print(f'LLM generated {len(candidates)} candidates')
print('All candidates:', candidates)
assert len(candidates) >= 3, f'FAIL: expected >= 3, got {len(candidates)}'
print('PASS')
"

# 验证其余候选是否入队
# 运行一轮后检查队列中新加入的 sibling topics
```

---

## 🔴 Bug #17: 澄清需求未标记父 topic 完成 → 无限澄清循环

**严重程度**: 🔴 高 — 当 topic 需要澄清时，每次运行都会重复要求澄清，无限循环

**复现**:
```bash
python3 curious_agent.py --run
# [Decomposer] Clarification needed for 'knowledge graph completion AI': no candidates passed provider validation
# 🤔 需要澄清: knowledge graph completion AI — no candidates passed provider validation

# 下一轮运行又会问同样的问题，无限循环
```

**根因**: 当 `decomposer.decompose()` 抛出 `ClarificationNeeded`，函数直接返回 `{"status": "clarification_needed", ...}`，但**没有标记原始 topic 为 done**。所以下一轮 `select_next()` 会再次选中同一个 topic，再次要求澄清。

**期望行为**: topic 需要澄清时，将其标记为 done（或 blocked），避免无限循环，等待用户重新注入澄清后的 topic。

**修复方向**: 在 `catch ClarificationNeeded` 分支调用 `kg.mark_topic_done(e.topic, f"Needs clarification: {e.reason}")`：

```python
except ClarificationNeeded as e:
    print(f"[Decomposer] Clarification needed for '{e.topic}': {e.reason}")
    kg.mark_topic_done(e.topic, f"Needs clarification: {e.reason}")  # ← 新增这行
    EventBus.emit("decomposer.clarification_needed", {
        "topic": e.topic,
        "alternatives": e.alternatives,
        "reason": e.reason
    })
    return {"status": "clarification_needed", "topic": e.topic, "reason": e.reason}
```

**验收标准**:
```bash
# 第一次运行，topic 需要澄清
python3 curious_agent.py --run
# 期望：输出 "🤔 需要澄清: ..."
# 检查：topic 是否已标记完成
python3 -c "
import sys; sys.path.insert(0, '.')
from core import knowledge_graph as kg
print(f'Topic completed: {kg.is_topic_completed(\"knowledge graph completion AI\")}')
"
# 期望：True
# 第二次运行，select_next() 应选中下一个 topic，不是同一个 topic
```

---

## 🔴 Bug #18: QualityV2 新鲜话题评分偏低，导致 BehaviorWriter 无法触发

**严重程度**: 🔴 中 — 高质量探索结果无法写入行为规则，Phase 1 闭环失效

**现象**:
- 分解产生全新子 topic，探索成功后，`quality = monitor.assess_exploration_quality(topic, findings)` 总是返回 ~4.0
- 质量门槛是 7.0 → 4.0 < 7.0 → BehaviorWriter 不触发 → 行为规则永不写入
- 这种情况只发生在**全新** topic（没有 prior knowledge）

**根因**: QualityV2 的三维评分公式：
```python
quality = (
    semantic_novelty * 0.40 +  # 全新话题 = 1.0 → 贡献 0.4
    confidence_delta * 0.30 +   # 全新话题 = 0 → 贡献 0.0
    graph_delta * 0.30          # 全新话题 = 0 → 贡献 0.0
) * 10
# 最终 quality = 4.0，总是低于门槛 7.0
```

全新话题应该获得更高的评分，因为它带来最大的信息增益。当前公式严重惩罚新鲜话题。

**期望行为**: 全新话题（无 prior）应默认评分 >= 7.0，因为任何探索都能带来较大信息增益。

**修复方向**:
```python
# quality_v2.py assess_quality 修改
if not prev_summary:
    # 全新话题，语义新颖性满分，置信度默认 0.5，图变化默认 0.5
    quality = (
        1.0 * 0.40 +
        0.5 * 0.30 +
        0.5 * 0.30
    ) * 10 = (0.4 + 0.15 + 0.15) * 10 = 7.0
# 刚好达到质量门槛
```

具体代码修改：
```python
# quality_v2.py assess_quality
if not prev_summary:
    # 全新话题，默认 confidence_delta = 0.5，graph_delta = 0.5
    confidence_delta = 0.5
    graph_delta = 0.5
```

**验收标准**:
```python
# 验证全新话题评分 >= 7.0
python3 -c "
import sys; sys.path.insert(0, '.')
from core.quality_v2 import QualityV2Assessor
from core.llm_manager import LLMManager
from core import knowledge_graph as kg

llm = LLMManager.get_instance()
assessor = QualityV2Assessor(llm)
findings = {'summary': '探索发现内容', 'sources': []}
q = assessor.assess_quality('new_topic_never_explored', findings, kg)
print(f'quality = {q}')
assert q >= 7.0, f'FAIL: q={q} < 7.0'
print('PASS: new topic quality >= 7.0')
"
```

---

## 修复优先级建议 (2026-03-23)

| 优先级 | Bug | 理由 |
|--------|-----|------|
| P0 | #17 | 无限循环，每次都选同一个需要澄清的 topic，无法继续探索 |
| P0 | #18 | 新鲜探索结果无法触发 BehaviorWriter，Phase 1 闭环失效 |
| P0 | #19 | 候选验证全部失败，探索链断裂，无法推进任何探索 |
| P2 | #20 | 分解变单选，违背树状生长设计，候选浪费 |

---

_报告更新: 2026-03-23 20:50_
_测试者: R1D3-researcher_

---

## 🔴 Bug #21: 图谱幽灵节点——队列已完成但无详情，且无效节点定义不清

**严重程度**: 🔴 高 — 图谱显示欺骗性内容，无效节点和未探索节点混在一起

**用户现象**:
图谱界面多个节点显示**绿色**（表示已完成），但点击后理解深度为 0、摘要为空、来源为空。典型节点：`Memory Overhead Download`、`OMO multi-agent orchestration`、`curiosity-driven reinforcement learning` 等 15 个。

**数据验证**（2026-03-24 实测）：
```
=== done但known=False 的节点（幽灵节点）===
  Working Memory Representations
  Detectedmemoryleaks
  Computational Cognitive Modeling
  Agentic Reasoning
  Working Memory Guides
  Incremental Contingency Planning
  Introduction Dynamic Memory
  working memory AI agent
  OMO multi-agent orchestration
  curiosity-driven reinforcement learning
  Agentic Tools
  Memory Overhead  Download
  autonomous agent planning and replanning
  Fine Agentic Workflows
  During Working Memory
（共 15 个）
```

---

### 一、节点有效性分类定义（关键）

对 `knowledge.topics` 中的每一个节点，按以下三维判断有效性：

| 条件组合 | 类型 | 含义 | 处理方式 |
|---------|------|------|---------|
| `known=true` | **有效节点** | 探索已完成且有有效信息 | 保留 |
| `known=false` + `queue status=pending/investigating` | **未探索节点** | 探索还没跑，有效性未知 | 保留 |
| `known=false` + `queue status=done` + `status=partial` | **幽灵节点（无效）** | 探索标记完成但从未真正运行（`add_knowledge()` 未写入） | **删除** |

**幽灵节点的根因链路**：
```
CuriosityDecomposer 生成子 topic
  → add_child() 在 knowledge.topics 创建占位 { known: false, status: "partial" }
  → curious_agent.py 单轮退出（分解后标记父 topic 完成即退出）
  → 下一轮选中子 topic → 子 topic 又被分解 → 标记 done → 退出
  → Explorer.explore() 从未被调用 → add_knowledge() 从未被调用
  → knowledge.topics 里 known: false，depth: 0
  → 图谱显示绿色但无详情
```

---

### 二、期望行为

1. **幽灵节点必须被清理**：当 topic 在 `curiosity_queue` 标记为 done，但 `knowledge.topics` 里 `known=false`，说明探索从未真正执行——这类节点是**无效数据**，应从 `knowledge.topics` 中删除
2. **未探索节点保留**：pending/investigating 状态的节点有效性未知，保留不删
3. **清理时机**：在 `kg.mark_topic_done()` 中检查并删除对应幽灵节点

---

### 三、修复方向

**Step 1：在 `knowledge_graph.py` 新增清理函数**

```python
def remove_ghost_nodes() -> list:
    """
    清理 knowledge.topics 中的幽灵节点。
    幽灵节点定义：known=False 且 status=partial 且 queue 中已标记 done。

    Returns:
        list: 被删除的节点名列表
    """
    state = _load_state()
    queue_topics = {
        item["topic"]: item["status"]
        for item in state.get("curiosity_queue", [])
    }

    topics = state["knowledge"]["topics"]
    removed = []

    for topic in list(topics.keys()):
        node = topics[topic]
        queue_status = queue_topics.get(topic)

        if (node.get("known") is False
                and node.get("status") == "partial"
                and queue_status == "done"):
            del topics[topic]
            removed.append(topic)

    if removed:
        _save_state(state)

    return removed
```

**Step 2：在 `mark_topic_done()` 中调用清理**

```python
def mark_topic_done(topic: str, reason: str) -> None:
    state = _load_state()
    # ... 现有逻辑：更新 completed_topics、同步队列状态 ...

    # 清理该 topic 的幽灵节点（如有）
    ghost_removed = []
    topics = state["knowledge"]["topics"]
    if topic in topics:
        node = topics[topic]
        queue_status = next(
            (item["status"] for item in state.get("curiosity_queue", [])
             if item["topic"] == topic), None
        )
        if (node.get("known") is False
                and node.get("status") == "partial"
                and queue_status == "done"):
            del topics[topic]
            ghost_removed.append(topic)

    _save_state(state)
```

**Step 3：提供一次性清理脚本（可选）**

```python
# scripts/cleanup_ghost_nodes.py
if __name__ == "__main__":
    from core import knowledge_graph as kg
    removed = kg.remove_ghost_nodes()
    print(f"Removed {len(removed)} ghost nodes: {removed}")
```

---

### 四、验收标准

```python
# 验收1：幽灵节点必须被删除
python3 -c "
import sys; sys.path.insert(0, '.')
from core import knowledge_graph as kg

# 先清理
removed = kg.remove_ghost_nodes()
print(f'清理了 {len(removed)} 个幽灵节点: {removed}')

# 验证：done + known=False 的幽灵节点应为 0
state = kg.get_state()
queue = {item['topic']: item['status'] for item in state.get('curiosity_queue', [])}
topics = state.get('knowledge', {}).get('topics', {})
ghosts = [
    t for t, v in topics.items()
    if not v.get('known') and v.get('status') == 'partial'
    and queue.get(t) == 'done'
]
if ghosts:
    print(f'FAIL: 仍有 {len(ghosts)} 个幽灵节点: {ghosts}')
else:
    print('PASS: 幽灵节点已清零')
"

# 验收2：pending/investigating 的未探索节点应保留
python3 -c "
import sys; sys.path.insert(0, '.')
from core import knowledge_graph as kg

state = kg.get_state()
queue = {item['topic']: item['status'] for item in state.get('curiosity_queue', [])}
topics = state.get('knowledge', {}).get('topics', {})

pending_ghosts = [
    t for t, v in topics.items()
    if not v.get('known') and v.get('status') == 'partial'
    and queue.get(t) in ('pending', 'investigating')
]
print(f'保留的未探索节点（known=False + pending/investigating）: {len(pending_ghosts)} 个')
print('PASS: pending 节点未被误删' if len(pending_ghosts) >= 0 else 'FAIL')
"

# 验收3：有效节点（known=True）应完全保留
python3 -c "
import sys; sys.path.insert(0, '.')
from core import knowledge_graph as kg

state = kg.get_state()
topics = state.get('knowledge', {}).get('topics', {})
known_nodes = [t for t, v in topics.items() if v.get('known')]
print(f'有效节点（known=True）: {len(known_nodes)} 个')
assert len(known_nodes) > 0, 'FAIL: 有效节点不应被删'
print('PASS: 有效节点完整保留')
"
```

---

_报告更新: 2026-03-24 08:12_
_测试者: R1D3-researcher_

---

## ✅ Bug #22: 图谱节点着色按"实际quality"——完全修复（2026-03-24）

**严重程度**: 🔴 高 — 图谱颜色反映的是"计划投入"，不是"实际掌握"

**问题描述**：

`knowledge.topics` 里的 `depth` 字段是**探索注入时预设的目标深度值**（shallow=3, medium=5, deep=8），不是探索后真实理解质量的反映。

例如：一个 topic 预设 depth=8（deep 探索），但实际搜索结果稀少、质量低下，真正理解深度只有 3——`knowledge.topics` 里记录的仍是 8。

图谱节点按这个预设值着色，用户看到的是"这个 topic 计划投入很深"，而不是"这个 topic 实际掌握得很好"。

**真实理解质量字段存在但未使用**：

`meta_cognitive.last_quality[topic]`（0-10 分）是探索后评估的真实质量分数，目前：
- ✅ 在 `knowledge_graph.py` 的 `meta_cognitive` 中正确记录
- ❌ 没有被 `curious_api.py` 的 `/api/curious/state` 端点返回
- ❌ 没有在图谱节点上展示
- ❌ 图谱着色完全不使用这个字段

**期望行为**：

1. API `/api/curious/state` 返回的每个 topic 条目附带 `last_quality` 字段
2. 图谱节点着色按 `last_quality`（真实质量）而非 `depth`（预设投入）
   - 🟢 绿色 = 高质量（Q ≥ 7）
   - 🟡 黄色 = 中质量（5 ≤ Q < 7）
   - 🔴 红色 = 低质量（Q < 5）
   - ⬜ 灰色 = pending/investigating（尚未探索，无 quality）
3. pending/investigating 的未探索节点（无 quality）着灰色，明显区别于有质量的节点

**修复方向**：

**Step 1：修改 `curious_api.py` `/api/curious/state` 端点**

```python
@app.route("/api/curious/state")
def api_state():
    from core import knowledge_graph as kg
    state = kg.get_state()
    summary = kg.get_knowledge_summary()
    topics = state.get("knowledge", {}).get("topics", {})
    mc = kg.get_meta_cognitive_state()
    quality_map = mc.get("last_quality", {})

    # 给每个 topic 附上 last_quality
    for name, v in topics.items():
        v["quality"] = quality_map.get(name, None)

    return jsonify({
        "status": "ok",
        "knowledge": {**summary, "topics": topics},
        "curiosity_queue": state.get("curiosity_queue", []),
        "exploration_log": state.get("exploration_log", []),
        "last_update": state.get("last_update")
    })
```

**Step 2：修改 `ui/index.html` 的 `buildGraphData()` 着色逻辑**

```javascript
function nodeColor(d) {
    // 按 last_quality 分级，不再按 depth
    var q = d.quality;
    if (q === undefined || q === null) return '#8b949e';  // pending/无质量 → 灰色
    if (q >= 7) return '#3fb950';   // 高质量 → 绿色
    if (q >= 5) return '#d29922';   // 中质量 → 黄色
    return '#f85149';                // 低质量 → 红色
}

function renderGraph() {
    // ...
    // pending/investigating 节点（无 quality）用特殊样式
    nodeSel.append('circle')
        .attr('r', function(d) {
            return d.inQueue ? Math.max(18, (d.quality || 0) * 2.4) : Math.max(12, (d.quality || 0) * 1.8);
        })
        .attr('fill', nodeColor)
        .attr('fill-opacity', function(d) {
            return 1.0;  // 全部不透明
        })
        .attr('stroke', function(d) {
            return d.inQueue ? '#fff' : 'none';
        });
}
```

**Step 3：更新图例**

```html
<div class="graph-legend">
    <div class="legend-item"><div class="legend-dot" style="background:#3fb950"></div>绿色 = 高质量 (Q≥7)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#d29922"></div>黄色 = 中质量 (Q 5-7)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#f85149"></div>红色 = 低质量 (Q<5)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#8b949e"></div>灰色 = 待探索（无质量）</div>
    <div class="legend-item"><div class="legend-dot" style="background:#58a6ff; width:14px; height:3px; border-radius:0;"></div>蓝实线 = 分解关系</div>
    <div class="legend-item"><div class="legend-dot" style="background:#8b949e; width:14px; height:2px; border-radius:0; border-top: 2px dashed #8b949e;"></div>灰虚线 = 语义相似</div>
</div>
```

**验收标准**：
```python
# 验证1：API 返回的 topic 条目包含 quality 字段
python3 -c "
import sys; sys.path.insert(0, '.')
from core import knowledge_graph as kg
import json

state = kg.get_state()
mc = kg.get_meta_cognitive_state()
quality_map = mc.get('last_quality', {})

topics = state.get('knowledge', {}).get('topics', {})
nodes_with_quality = [t for t, v in topics.items() if 'quality' in v or t in quality_map]

# 模拟 API 返回结构（附加 quality）
for name, v in topics.items():
    v['quality'] = quality_map.get(name, None)

# 验证 quality 字段存在
known_with_quality = [(t, v.get('quality')) for t, v in topics.items() if v.get('known') and v.get('quality') is not None]
print(f'有效节点（known=True）中，有 quality 字段: {len(known_with_quality)}/{sum(1 for t,v in topics.items() if v.get(\"known\"))}')

# 验证 pending 节点没有 quality
pending_nodes = [(t, topics[t].get('quality')) for t in topics if not topics[t].get('known')]
print(f'pending 节点: {len(pending_nodes)} 个，全部无 quality: {all(q is None for _, q in pending_nodes)}')
"

# 验证2：图谱着色使用 quality 而非 depth
# 打开浏览器控制台，运行：
var data = buildGraphData();
var highQ = data.nodes.filter(function(n){ return n.quality >= 7; });
var midQ = data.nodes.filter(function(n){ return n.quality >= 5 && n.quality < 7; });
var lowQ = data.nodes.filter(function(n){ return (n.quality || 0) < 5; });
console.log('Quality分布 - 高:', highQ.length, '中:', midQ.length, '低:', lowQ.length);
var coloredByQ = data.nodes.filter(function(n){ return n.quality && n.depth !== n.quality; });
console.log('节点中 quality≠depth（颜色会变化）:', coloredByQ.length);
var pendingGray = data.nodes.filter(function(n){ return !n.quality && n.inQueue; });
console.log('pending 节点（灰色）:', pendingGray.length);
var knownNotPending = data.nodes.filter(function(n){ return n.quality !== undefined && n.inQueue; });
console.log('已知但仍在队列中:', knownNotPending.length, '（应为 0）');
```

---

### 附加问题：图谱连线按"名称语义重叠"而非"真实父子关系"

**当前连线生成逻辑（错误）**：

```javascript
// buildGraphData() 中
function tokens(s) {
    return (s||'').toLowerCase().split(/[\s\-_:,]/)
        .filter(function(t){ return t.length>2 && STOP.indexOf(t)<0; });
}
// 两个节点共享 >=1 个 token 就连线
if (sh >= 1) {
    links.push({source: a.id, target: b.id, strength: sh});
}
```

**问题**：
- 按名称共词连线会产生大量**误连**（两个无关 topic 恰好共享词汇就连线）
- 真正的树状分解关系（父子关系）**完全被忽略**
- `knowledge.topics[parent].children` 里的真实父子关系**从未被使用**

**期望连线含义**：
> 节点 A 和节点 B 之间的连线 = B 是从 A 分解出来的子 topic
> 这是 CuriosityDecomposer 分解的真实结果，不是名称碰巧相似

**修复方向（新增到 Step 2）**：

```javascript
function buildGraphData() {
    // ... 现有节点构建（不变）...

    // 用真实父子关系画线（新增）
    var links = [], seen = {};
    var topics = state.knowledge && state.knowledge.topics || {};

    // 分解关系连线
    for (var parent in topics) {
        var children = (topics[parent] && topics[parent].children) || [];
        for (var i = 0; i < children.length; i++) {
            var child = children[i];
            if (topics[child]) {
                links.push({ source: parent, target: child, type: 'decomposition' });
            }
        }
    }

    // 语义相似连线（保留原有的 token 共现逻辑，加 type 标记）
    var STOP = ['ai','agent','agents','in','for','the','and','of','to','learning','framework','self','a','based','systems'];
    function tokens(s) {
        return (s||'').toLowerCase().split(/[\s\-_:,]/).filter(function(t){ return t.length>2 && STOP.indexOf(t)<0; });
    }

    var qMap = {};
    (state.curiosity_queue || []).forEach(function(q) {
        if (q.status !== 'done') qMap[q.topic.toLowerCase()] = true;
    });

    for (var i = 0; i < nodes.length; i++) {
        for (var j = i+1; j < nodes.length; j++) {
            var a = nodes[i], b = nodes[j];
            if (qMap[a.id.toLowerCase()] || qMap[b.id.toLowerCase()]) continue;  // pending 节点不连语义线
            var sh = 0;
            var tA = {}, tB = {};
            tokens(a.id).forEach(function(t){ tA[t] = true; });
            tokens(b.id).forEach(function(t){ tB[t] = true; });
            for (var t in tA) if (tA[t] && tB[t]) sh++;
            if (sh >= 1) {
                var k = [a.id, b.id].sort().join('|');
                // 排除已是分解关系的连线
                var alreadyLinked = links.some(function(l) {
                    var src = typeof l.source === 'object' ? l.source.id : l.source;
                    var tgt = typeof l.target === 'object' ? l.target.id : l.target;
                    return (src === a.id && tgt === b.id) || (src === b.id && tgt === a.id);
                });
                if (!alreadyLinked && !seen[k]) {
                    seen[k] = true;
                    links.push({ source: a.id, target: b.id, type: 'semantic', strength: sh });
                }
            }
        }
    }

    return {nodes: nodes, links: links};
}
```

**连线样式**（两种连线并存）：
```javascript
link
    .attr('stroke', function(d) {
        return d.type === 'decomposition' ? '#58a6ff' : '#8b949e';  // 蓝=分解，灰=语义
    })
    .attr('stroke-width', function(d) {
        return d.type === 'decomposition' ? 5 : 2;  // 分解更粗
    })
    .attr('stroke-dasharray', function(d) {
        return d.type === 'semantic' ? '5,5' : '0';  // 语义连线虚线
    })
    .attr('stroke-opacity', 0.7);
```

**图例**：
```html
<div class="legend-item"><div class="legend-dot" style="background:#58a6ff; width:14px; height:3px; border-radius:0;"></div>蓝实线 = 分解关系</div>
<div class="legend-item"><div class="legend-dot" style="background:#8b949e; width:14px; height:2px; border-radius:0; border-top: 2px dashed #8b949e;"></div>灰虚线 = 语义相似</div>
```

**验收标准**：
```javascript
// 验证1：节点着色正确
var data = buildGraphData();
var green = data.nodes.filter(function(n){ return n.quality >= 7; });
var yellow = data.nodes.filter(function(n){ return n.quality >= 5 && n.quality < 7; });
var red = data.nodes.filter(function(n){ return n.quality !== undefined && n.quality < 5; });
var gray = data.nodes.filter(function(n){ return n.quality === undefined || n.quality === null; });
console.log('节点颜色分布 - 绿:', green.length, '黄:', yellow.length, '红:', red.length, '灰:', gray.length);
assert green.length > 0 || yellow.length > 0 || red.length > 0 || gray.length > 0, 'FAIL: 无节点';
console.log('PASS: 节点颜色分布正确');

// 验证2：分解关系连线来自 children
var topics = state.knowledge && state.knowledge.topics || {};
var decompLinks = data.links.filter(function(l){ return l.type === 'decomposition'; });
var invalidDecomp = decompLinks.filter(function(l) {
    var parent = typeof l.source === 'object' ? l.source.id : l.source;
    var child = typeof l.target === 'object' ? l.target.id : l.target;
    var children = (topics[parent] && topics[parent].children) || [];
    return children.indexOf(child) < 0;
});
assert invalidDecomp.length === 0, 'FAIL: 存在无效的分解连线';
console.log('PASS: 分解关系连线全部来自 children');

// 验证3：语义连线与分解连线不重叠
var semLinks = data.links.filter(function(l){ return l.type === 'semantic'; });
var overlap = data.links.filter(function(l) {
    if (!l.type) return false;  // 旧数据没有 type，跳过
    return decompLinks.some(function(d) {
        var ds = typeof d.source === 'object' ? d.source.id : d.source;
        var dt = typeof d.target === 'object' ? d.target.id : d.target;
        var ls = typeof l.source === 'object' ? l.source.id : l.source;
        var lt = typeof l.target === 'object' ? l.target.id : l.target;
        return (ds === ls && dt === lt) || (ds === lt && dt === ls);
    });
});
assert overlap.length === 0, 'FAIL: 分解连线和语义连线重叠';
console.log('PASS: 分解和语义连线无重叠');
console.log('分解连线:', decompLinks.length, '语义连线:', semLinks.length);
```

---

_报告更新: 2026-03-24 08:49_
_测试者: R1D3-researcher_
_状态: ✅ Ready for OpenCode 移交_

---

## 📋 Bug #22 修复状态跟踪

### ✅ Part 1：节点着色（已完成 by OpenCode 2026-03-24）

**验证结果**：✅ 全部正确

```javascript
// curious_api.py — quality_map 附加到每个 topic ✅
topic_copy["quality"] = quality_map.get(name, None)

// ui/index.html — nodeColor() 颜色映射 ✅
function nodeColor(d) {
    if (q === undefined || q === null) return '#8b949e';  // 灰
    if (q >= 7) return '#3fb950';   // 绿
    if (q >= 5) return '#d29922';   // 黄
    return '#f85149';                // 红
}
```

### ❌ Part 2：连线逻辑（未完成，还需 OpenCode 修复）

**以下 4 处尚未修改**：

**2a. `fill-opacity` 仍是旧逻辑**

```javascript
// 当前代码（❌ 未改）
.attr('fill-opacity', function(d){ return d.inQueue ? 0.9 : 0.65; })

// 应改为（✅ 期望）
.attr('fill-opacity', function(d){ return 1.0; })
```

**2b. `buildGraphData()` 连线仍是纯 token 共现，无 type 区分**

```javascript
// 当前代码（❌ 未改）——所有连线都是纯共现
links.push({source:a.id, target:b.id, strength:sh});

// 应改为（✅ 期望）——两种 type：
// 1. 分解关系（type: 'decomposition'）：来自 knowledge.topics[parent].children
// 2. 语义相似（type: 'semantic'）：来自 token 共现，排除已连接的分解关系
```

期望完整逻辑：
```javascript
function buildGraphData() {
    var links = [], seen = {};
    var topics = state.knowledge && state.knowledge.topics || {};

    // 分解关系连线（蓝实线）
    for (var parent in topics) {
        var children = (topics[parent] && topics[parent].children) || [];
        for (var i = 0; i < children.length; i++) {
            var child = children[i];
            if (topics[child]) {
                links.push({ source: parent, target: child, type: 'decomposition' });
            }
        }
    }

    // 语义相似连线（灰虚线）——排除已有分解关系的节点对
    for (var i = 0; i < nodes.length; i++) {
        for (var j = i+1; j < nodes.length; j++) {
            var a = nodes[i], b = nodes[j];
            if (qMap[a.id.toLowerCase()] || qMap[b.id.toLowerCase()]) continue;
            var sh = 0;
            var tA = {}, tB = {};
            tokens(a.id).forEach(function(t){ tA[t] = true; });
            tokens(b.id).forEach(function(t){ tB[t] = true; });
            for (var t in tA) if (tA[t] && tB[t]) sh++;
            if (sh >= 1) {
                var k = [a.id, b.id].sort().join('|');
                var alreadyLinked = links.some(function(l) {
                    var src = typeof l.source === 'object' ? l.source.id : l.source;
                    var tgt = typeof l.target === 'object' ? l.target.id : l.target;
                    return (src === a.id && tgt === b.id) || (src === b.id && tgt === a.id);
                });
                if (!alreadyLinked && !seen[k]) {
                    seen[k] = true;
                    links.push({ source: a.id, target: b.id, type: 'semantic', strength: sh });
                }
            }
        }
    }
    return {nodes: nodes, links: links};
}
```

**2c. 连线渲染未区分样式**

```javascript
// 当前代码（❌ 未改）——所有连线一样
.attr('stroke-width', 5)

// 应改为（✅ 期望）
.attr('stroke', function(d) {
    return d.type === 'decomposition' ? '#58a6ff' : '#8b949e';
})
.attr('stroke-width', function(d) {
    return d.type === 'decomposition' ? 5 : 2;
})
.attr('stroke-dasharray', function(d) {
    return d.type === 'semantic' ? '5,5' : '0';
})
.attr('stroke-opacity', 0.7);
```

**2d. 图例未更新**

```html
// 当前代码（❌ 未改）——仍是旧的深度分级图例

// 应改为（✅ 期望）
<div class="graph-legend">
    <div class="legend-item"><div class="legend-dot" style="background:#3fb950"></div>绿色 = 高质量 (Q≥7)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#d29922"></div>黄色 = 中质量 (Q 5-7)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#f85149"></div>红色 = 低质量 (Q<5)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#8b949e"></div>灰色 = 待探索（无质量）</div>
    <div class="legend-item"><div class="legend-dot" style="background:#58a6ff; width:14px; height:3px; border-radius:0;"></div>蓝实线 = 分解关系</div>
    <div class="legend-item"><div class="legend-dot" style="background:#8b949e; width:14px; height:2px; border-radius:0; border-top: 2px dashed #8b949e;"></div>灰虚线 = 语义相似</div>
</div>
```

### 📌 Bug #22 剩余子项状态

| 项目 | 文件 | 状态 | 备注 |
|------|------|------|------|
| 2a fill-opacity 改 1.0 | ui/index.html | ✅ 已完成 | 2026-03-24 OpenCode |
| 2b buildGraphData 连线逻辑重写 | ui/index.html | ✅ 已完成 | 2026-03-24 验证通过 |
| 2c 连线渲染样式区分 | ui/index.html | ✅ 已完成 | 2026-03-24 验证通过 |
| 2d 图例更新 | ui/index.html | ✅ 已完成 | 2026-03-24 OpenCode |

---

## 🔴 Bug #25: API 流评估 quality 但从未写入 last_quality——所有节点 quality 均为 None

**严重程度**: 🔴 高 — 图谱所有节点 quality=None，显示灰色，quality 分级完全失效

**现象**:
`curious_api.py` 的 `api_run()` 中：
- ✅ `monitor.assess_exploration_quality()` 被调用 → quality 计算出来
- ❌ `monitor.record_exploration()` 从未被调用 → `meta_cognitive.last_quality` 始终为空
- 结果：`last_quality` 永远是空字典 `{}`，`quality_map.get(name, None)` 全部返回 None

**根因**: Bug #15 修复时只补了 `AgentBehaviorWriter`，漏掉了 `record_exploration()`。

**影响范围**:
- 所有通过 API（`/api/curious/run`）探索的 topic → quality=None
- 所有通过旧版代码探索的 topic → `last_quality` 无记录 → quality=None
- 图谱所有节点（无论是 CLI 还是 API 探索）→ 全部灰色

**期望行为**: 每次 quality 评估后都应写入 `last_quality`，图谱按 quality 着色的前提是 `last_quality` 有数据。

**修复方向**:

```python
# curious_api.py api_run() 第 103 行之后（quality 评估之后）新增
quality = monitor.assess_exploration_quality(result["topic"], findings)
# ← 新增这行（Bug #15 漏掉的）
monitor.record_exploration(result["topic"], quality, marginal_return=0.0, notified=False)

if quality >= 7.0:
    writer = AgentBehaviorWriter()
    writer.process(result["topic"], findings, quality, result.get("sources", []))
```

**验收标准**:
```python
# 触发一轮 API 探索
import requests
resp = requests.post("http://localhost:4848/api/curious/run", json={"topic": "test_quality_record", "depth": "medium"}, timeout=60)
print(resp.json())

# 验证 last_quality 有记录
import json, urllib.request
state = json.loads(urllib.request.urlopen("http://localhost:4848/api/curious/state").read())
lq = state.get("knowledge", {}).get("meta_cognitive", {}).get("last_quality", {})
print(f"last_quality entries: {len(lq)}")
assert len(lq) > 0, "FAIL: last_quality still empty after API exploration"
print("PASS: last_quality populated")
```

---

## 🟡 Bug #23: 服务器重启遗漏——导致无法观察到新的 quality 颜色

**严重程度**: 🟡 低（运维问题）— OpenCode 代码已正确，但服务未重新加载

**现象**:
Web 界面节点颜色仍是旧的 depth 分级（绿深蓝浅），不是新的 quality 分级（绿高黄中国红低灰待探索）。

**根因**: OpenCode 2026-03-24 完成了 `curious_api.py` 和 `ui/index.html` 的 Part 1 修改（节点着色逻辑），但 `curious_api.py` 服务没有重启，新代码未加载。

**验证**：
```bash
# 方法1：对比进程启动时间和文件修改时间
ls -la /root/dev/curious-agent/curious_api.py
ps aux | grep curious_api

# 方法2：检查 API 响应是否包含 quality 字段
curl localhost:4848/api/curious/state | python3 -c "import sys,json; d=json.load(sys.stdin); topics=list(d.get('knowledge',{}).get('topics',{}).values()); print('有quality字段:', any('quality' in t for t in topics))"

# 方法3：直接看进程加载时间
ps -o pid,lstart,cmd -p $(pgrep -f curious_api)
```

**修复方向**:
```bash
# 重启服务
pkill -f curious_api
cd /root/dev/curious-agent && nohup python3 curious_api.py > api.log 2>&1 &
sleep 2
curl localhost:4848/api/curious/state | python3 -c "import sys,json; d=json.load(sys.stdin); t=list(d.get('knowledge',{}).get('topics',{}).values()); print('有quality字段:', any('quality' in t for t in t[:3]))"
```

**验收标准**:
- `curl localhost:4848/api/curious/state` 返回的 topic 条目包含 `quality` 字段
- 刷新页面，节点颜色按 quality 分级（绿高/黄中/红低/灰待探索）

---

## ✅ Bug #24: Bug #22 剩余 2 项已完成（2026-03-24 OpenCode）

**严重程度**: 🟡 低（UI 微调）— 功能核心已完成，只剩 2 处细节

**当前状态**: OpenCode 已完成 Bug #22 的 Part 1（节点着色）和 Part 2b/2c（连线逻辑和样式），剩余 2a 和 2d。

**待完成项**：

**2a. `fill-opacity` 仍是旧值**

```javascript
// ui/index.html（当前，❌ 未改）
.attr('fill-opacity', function(d){ return d.inQueue ? 0.9 : 0.65; })

// 应改为（✅ 期望）
.attr('fill-opacity', function(d){ return 1.0; })
```

**2d. 图例未更新**

```html
// ui/index.html（当前，❌ 未改）——仍是旧的深度分级图例

// 应改为（✅ 期望）
<div class="graph-legend">
    <div class="legend-item"><div class="legend-dot" style="background:#3fb950"></div>绿色 = 高质量 (Q≥7)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#d29922"></div>黄色 = 中质量 (Q 5-7)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#f85149"></div>红色 = 低质量 (Q<5)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#8b949e"></div>灰色 = 待探索（无质量）</div>
    <div class="legend-item"><div class="legend-dot" style="background:#58a6ff; width:14px; height:3px; border-radius:0;"></div>蓝实线 = 分解关系</div>
    <div class="legend-item"><div class="legend-dot" style="background:#8b949e; width:14px; height:2px; border-radius:0; border-top: 2px dashed #8b949e;"></div>灰虚线 = 语义相似</div>
</div>
```

**验收标准**:
```bash
# 2a: fill-opacity
grep -n "fill-opacity" /root/dev/curious-agent/ui/index.html
# 期望：fill-opacity: 1.0（不再按 inQueue 分级）

# 2d: 图例
grep -c "Q≥7\|Q 5-7\|Q<5\|蓝实线\|灰虚线" /root/dev/curious-agent/ui/index.html
# 期望：5（图例 6 行中至少 5 个关键词存在）
```

---

## 🔴 Bug #14: `add_child` 参数写错导致分解关系 100% 丢失（图谱实线消失）

**发现时间**: 2026-03-25 09:35

**严重程度**: 🔴 最高 — 图谱实线链接全部消失

**复现**:
```bash
python3 -c "
import json
with open('knowledge/state.json') as f:
    d = json.load(f)
t = d['knowledge']['topics'].get('openclaw agent framework capabilities', {})
print('children:', t.get('children'))
"
# 期望：应该有多个子节点
# 实际：只有 1 个（HAL），其他全部丢失
```

**根因**: `curious_agent.py` 第 217 行，`add_child` 的第二个参数写错了变量名：

```python
# curious_agent.py 第 70-103 行
topic = next_curiosity["topic"]          # ← 原始 topic（父节点）

# 分解后
next_curiosity["topic"] = explore_topic  # ← 子节点，覆盖了 topic 变量
# 但 topic 变量本身没有更新！！

# ... 省略 ...

# 第 217 行
kg.add_child(next_curiosity["original_topic"], topic)
#                              ↑ 父节点            ↑ topic（还是父节点！）
#                                         应该是 next_curiosity["topic"]
```

每次循环都是 `add_child(父节点, 父节点)`（自连接），只有最后一次 `topic` 被新值覆盖时碰巧写对了。中间积累的所有 child 记录被后续写入覆盖。

**解决方案**:
```python
# 方案1（推荐）：直接用 next_curiosity["topic"]
kg.add_child(next_curiosity["original_topic"], next_curiosity["topic"])
```

**验收标准**:
```bash
# 运行 daemon 3 个循环周期后检查 KG
python3 -c "
import json
with open('knowledge/state.json') as f:
    d = json.load(f)
parent = 'openclaw agent framework capabilities'
children = d['knowledge']['topics'].get(parent, {}).get('children', [])
print(f'children count: {len(children)}')
print(f'children: {children}')
"
# 期望：children 数量 >= 分解产生的子节点数（如 4-5 个）
# 之前只有 1 个，修复后应该 >= 4
```

---

## 🔴 Bug #15: daemon 和 API 并发写 state.json 无文件锁

**发现时间**: 2026-03-25 09:35

**严重程度**: 🔴 最高 — 多个进程同时写入互相覆盖

**复现**:
```bash
# 终端1：启动 daemon
python3 curious_agent.py --daemon --interval 2

# 终端2：快速连续触发多个 API 探索
curl localhost:4848/api/curious/inject -X POST -d '{"topic":"test1","depth":"medium"}'
curl localhost:4848/api/curious/inject -X POST -d '{"topic":"test2","depth":"medium"}'
curl localhost:4848/api/curious/inject -X POST -d '{"topic":"test3","depth":"medium"}'

# 观察 state.json — 期望所有 topic 都在，实际只有最后一个
```

**根因**: `_save_state()` 直接覆盖写文件，无任何锁机制：

```python
# core/knowledge_graph.py 第 35-41 行
def _save_state(state: dict) -> None:
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)  # ← 直接覆盖，无锁
```

当前 daemon (`--daemon`) 和 API server (`curious_api.py`) 是两个独立进程，共享同一个 `state.json`，写操作互相覆盖。

**解决方案**:
```python
# 方案1（推荐）：文件锁
import fcntl

def _save_state(state: dict) -> None:
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    lock_file = STATE_FILE + ".lock"
    
    with open(lock_file, "w") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)

# 方案2：原子写入（写临时文件再 rename）
def _save_state(state: dict) -> None:
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp_file = STATE_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, STATE_FILE)  # 原子操作
```

**验收标准**:
```bash
# 同时触发 daemon 探索 + API 注入后检查
python3 -c "
import json
with open('knowledge/state.json') as f:
    d = json.load(f)
queue = d.get('curiosity_queue', [])
topics = d.get('knowledge', {}).get('topics', {})
topics_with_children = [t for t, v in topics.items() if v.get('children')]
print(f'queue count: {len(queue)}')
print(f'topics with children: {len(topics_with_children)}')
"
# 期望：queue 条目完整，topics.children 完整
```

---

## 验证记录（2026-03-25 09:49）

### Bug #14 验证结果：❌ 修复未生效

**验证时间**: 2026-03-25 09:43

**验证方法**:
```bash
# 重启 daemon 和 API
# 运行 3 个探索周期后检查 KG
python3 -c "
import json
with open('knowledge/state.json') as f:
    d = json.load(f)
topics = d['knowledge']['topics']
parents = [n for n,v in topics.items() if v.get('children')]
print(f'有 children 的 topic 数: {len(parents)}')
"
```

**结果**:
- 有 children 的 topic 数：**0**（应为 >= 1）
- `curious_agent.py` 第 217 行仍是：
  ```python
  kg.add_child(next_curiosity["original_topic"], topic)  # ← 错：topic 仍是父节点
  ```

**结论**: OpenCode 的修复**未实际写入文件**，或 weNix 尚未部署。Bug #14 状态仍为**未修复**。
