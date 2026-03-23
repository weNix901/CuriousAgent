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
