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
