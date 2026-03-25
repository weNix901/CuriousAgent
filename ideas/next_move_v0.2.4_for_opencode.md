# next_move_v0.2.4_for_opencode - 完整开发任务文档

> **版本**: v0.2.4 | **更新**: 2026-03-25 | **状态**: 待开发
> **范围**: Curious Agent 侧 + R1D3 侧，完整任务，含集成到主流程的显式说明
> **设计文档**: `docs/10-双体协作架构设计.md`
> **目标**: 确保每个模块完成后都能实际可用，而非"开发完成但不可调用"

---

## 0. 前置声明：为什么这个文档特别强调"集成到主流程"

### 0.1 历史问题回顾

v0.2.3 之前发生过的问题：
- CuriosityDecomposer 开发完成，但 `curious_agent.py` 的主循环从未调用它
- QualityV2Assessor 开发完成，但只在测试文件里存在，主流程里没有实际调用
- MetaCognitiveMonitor 开发完成，但它的建议从未影响探索决策

**根本原因**：模块开发和主流程集成是分开的两件事，文档只描述了"模块做什么"，没有说清楚"主流程在哪个节点调用它"。

### 0.2 v0.2.4 的原则

> **每个任务必须有明确的"主流程集成点"——在哪个文件的哪个函数，在哪一行代码，被谁调用。**

每个任务分成三层：
1. **模块实现**：写什么
2. **主流程集成**：在哪里被调用（精确到行号范围）
3. **集成测试**：怎么验证它真的被调用了

---

## 1. 基线：v0.2.3 已完成能力

| 模块 | 文件 | 状态 | 是否已在主流程集成 |
|------|------|------|------------------|
| CompetenceTracker | `core/competence_tracker.py` | ✅ 已完成 | ✅ 已在 curious_agent.py 主循环中调用 |
| CuriosityDecomposer | `core/curiosity_decomposer.py` | ✅ 已完成 | ⚠️ **未集成** |
| QualityV2Assessor | `core/quality_v2.py` | ✅ 已完成 | ⚠️ **未集成** |
| MetaCognitiveMonitor | `core/meta_cognitive_monitor.py` | ✅ 已完成 | ⚠️ **未集成** |
| AgentBehaviorWriter | `core/agent_behavior_writer.py` | ✅ 已完成 | ✅ 已在主流程调用 |
| inject API | `curious_api.py` | ✅ 已完成 | ✅ 已在主流程 |
| state API | `curious_api.py` | ✅ 已完成 | ✅ 已在主流程 |
| config.json | `config.json` | ✅ 已存在 | ✅ |

> **⚠️ 标记的模块**：这是 v0.2.4 的隐藏任务——先把历史模块集成到主流程，再做新功能。

---

## 2. v0.2.4 任务总览

### 2.1 阶段顺序（必须按此执行）

```
[阶段一] 历史积压：把 v0.2.3 未集成的模块接入主流程
    ├── T-1: CuriosityDecomposer 集成到主流程
    ├── T-2: QualityV2Assessor 集成到主流程
    └── T-3: MetaCognitiveMonitor 决策建议被采纳
            │
            ▼
[阶段二] 双体协作基础设施
    ├── T-4: Curious Agent 统一写入 shared_knowledge/curious/
    ├── T-5: R1D3 sync_discoveries.py 演进（读 shared_knowledge/）
    ├── T-6: R1D3 write_learning_need() 实现
    └── T-7: trigger_explore.sh 增强
            │
            ▼
[阶段三] injection_priority 机制
    ├── T-8: config.py 新增配置结构
    ├── T-9: inject 端点增强（priority 判断 + 异步触发）
    └── T-10: async_explorer.py 新建
            │
            ▼
[阶段四] Layer 3 合成能力
    ├── T-11: InsightSynthesizer 模块实现
    └── T-12: Explorer 集成 Layer 3 调用
            │
            ▼
[阶段五] exploration mode 配置
    ├── T-13: daemon 三模式支持
    └── T-14: hybrid mode daemon + inject 联动
            │
            ▼
[阶段六] 测试与集成验收
    └── T-15: 全流程集成测试
```

### 2.2 任务一览表

| ID | 任务 | 优先级 | 阶段 | 依赖 |
|----|------|--------|------|------|
| T-1 | CuriosityDecomposer 集成到主流程 | P0 | 阶段一 | 无 |
| T-2 | QualityV2Assessor 集成到主流程 | P0 | 阶段一 | T-1 |
| T-3 | MetaCognitiveMonitor 决策被采纳 | P0 | 阶段一 | T-2 |
| T-4 | 统一写入 shared_knowledge/curious/ | P0 | 阶段二 | 无 |
| T-5 | R1D3 sync 演进（读 shared_knowledge/） | P0 | 阶段二 | T-4 |
| T-6 | R1D3 write_learning_need() | P0 | 阶段二 | T-5 |
| T-7 | trigger_explore.sh 增强 | P1 | 阶段二 | T-6 |
| T-8 | config.py 新增配置结构 | P0 | 阶段三 | 无 |
| T-9 | inject 端点增强 | P0 | 阶段三 | T-8 |
| T-10 | async_explorer.py 新建 | P0 | 阶段三 | T-9 |
| T-11 | InsightSynthesizer 实现 | P0 | 阶段四 | T-2, T-3 |
| T-12 | Explorer 集成 Layer 3 | P0 | 阶段四 | T-11 |
| T-13 | daemon 三模式支持 | P1 | 阶段五 | T-8 |
| T-14 | hybrid mode 联动 | P1 | 阶段五 | T-13 |
| T-15 | 全流程集成测试 | P0 | 阶段六 | 全部 |

---

## 3. 阶段一：历史积压——模块主流程集成

---

### T-1: CuriosityDecomposer 集成到主流程

#### 问题定位

当前 `curious_agent.py` 的 `run_one_cycle()` 没有调用 CuriosityDecomposer。搜索确认：
```bash
grep -n "CuriosityDecomposer" /root/dev/curious-agent/curious_agent.py
# 预期：无结果（未集成）
```

#### 主流程集成点

**文件**: `curious_agent.py`，函数 `run_one_cycle()`，约第 80-120 行。

在 `topic = curiosity_item["topic"]` 之后、`result = self.explorer.explore()` 之前插入：

```python
# ===== T-1 集成点 开始 =====
# 【集成点 1】使用 CuriosityDecomposer 分解话题
# 插入位置：curious_agent.py run_one_cycle() 函数内
#         在 "topic = curiosity_item['topic']" 之后
#         在 "result = self.explorer.explore(topic)" 之前

from core.curiosity_decomposer import CuriosityDecomposer

decomposer = CuriosityDecomposer(
    llm_client=self.llm,
    provider_registry=self.provider_registry,
    kg=self.kg
)
sub_topics = await decomposer.decompose(topic)

if not sub_topics:
    # 所有候选都无法验证，fallback 到原始 topic 探索
    logger.warning(f"[T-1] Decompose returned empty for {topic}, falling back to direct explore")
    sub_topics = None
else:
    logger.info(f"[T-1] Decomposed {topic} into {len(sub_topics)} sub-topics")

curiosity_item["sub_topics"] = sub_topics
# ===== T-1 集成点 结束 =====

# 现有代码继续（不改）：
result = self.explorer.explore(topic, depth=depth, sub_topics=sub_topics)
```

**注意**：
- `decomposer.decompose()` 是 async 方法，确保 `run_one_cycle` 是 async def
- 如果已集成过，这里会有 import 语句，只需添加实例化和调用

#### T-1 验收标准

```bash
# 验证1：grep 确认集成
grep -n "CuriosityDecomposer" /root/dev/curious-agent/curious_agent.py
# 预期：至少 2 处（import + 实例化）

# 验证2：运行一轮探索，观察日志包含 "Decomposed"
cd /root/dev/curious-agent && python3 curious_agent.py --run --depth medium 2>&1 | grep -i decompos
# 预期：有 "Decomposed X into N sub-topics" 或 "falling back" 日志
```

---

### T-2: QualityV2Assessor 集成到主流程

#### 问题定位

`curious_agent.py` 主循环探索完成后调用了 quality 评估，但 QualityV2Assessor 未被实际使用。

#### 主流程集成点

**文件**: `curious_agent.py`，函数 `run_one_cycle()`，约第 120-150 行（探索完成后）。

在 `result = self.explorer.explore(...)` 之后、行为写入之前插入：

```python
# ===== T-2 集成点 开始 =====
# 【集成点 2】使用 QualityV2Assessor 替代旧的简单评分
# 插入位置：curious_agent.py run_one_cycle() 函数内
#         在 "result = self.explorer.explore(...)" 之后
#         在 "self.behavior_writer.process(...)" 之前

from core.quality_v2 import QualityV2Assessor

quality_assessor = QualityV2Assessor(llm_client=self.llm)
quality = quality_assessor.assess_quality(
    topic=topic,
    findings=result.get("findings", {}),
    knowledge_graph=self.kg
)
logger.info(f"[T-2] QualityV2 assessed quality={quality} for {topic}")

# 持久化到 state.json
from core.knowledge_graph import update_topic_quality
update_topic_quality(topic, quality)
# ===== T-2 集成点 结束 =====

# 后续现有代码（不改）：
if quality >= 7.0:
    self.behavior_writer.process(topic, result["findings"], quality, result.get("sources", []))
```

**注意**：
- 需要 `update_topic_quality(topic, quality)` 函数在 knowledge_graph.py 中存在或新增
- 如果 QualityV2Assessor.assess_quality 失败（LLM 不可用），fallback：
  ```python
  try:
      quality = quality_assessor.assess_quality(...)
  except Exception as e:
      logger.warning(f"[T-2] QualityV2 failed: {e}, using fallback")
      quality = quality_assessor.fallback_quality_assessment(result.get("findings", {}))
  ```

#### T-2 验收标准

```bash
# 验证1：grep 确认集成
grep -n "QualityV2Assessor" /root/dev/curious-agent/curious_agent.py

# 验证2：运行探索后检查 state.json 有 quality 记录
cd /root/dev/curious-agent && python3 curious_agent.py --run --depth medium
python3 -c "
import json
s = json.load(open('/root/dev/curious-agent/knowledge/state.json'))
lq = s.get('meta_cognitive', {}).get('last_quality', {})
print('last_quality:', lq)
# 预期：有 topic → float 的映射
"
```

---

### T-3: MetaCognitiveMonitor 决策被采纳

#### 问题定位

MetaCognitiveMonitor 计算了 `should_continue`、`should_explore` 建议，但主循环没有调用它们。

#### 主流程集成点（两处）

**集成点 A**：在 `run_one_cycle()` 开始时，判断是否应该探索

**文件**: `curious_agent.py`，函数 `run_one_cycle()` 开始处

```python
# ===== T-3 集成点 A 开始 =====
# 【集成点 3A】MetaCognitiveController 决策 — 是否探索
# 插入位置：curious_agent.py run_one_cycle() 函数开始
#         在 "curiosity_item = self.engine.select_next()" 之后

from core.meta_cognitive_controller import MetaCognitiveController
from core.meta_cognitive_monitor import MetaCognitiveMonitor

monitor = MetaCognitiveMonitor(llm_client=self.llm)
controller = MetaCognitiveController(monitor=monitor)

should_explore, reason = controller.should_explore(topic)
if not should_explore:
    logger.info(f"[T-3A] Exploration blocked for {topic}: {reason}")
    from core.knowledge_graph import update_curiosity_status
    update_curiosity_status(topic, "paused")
    return {"status": "blocked", "topic": topic, "reason": reason}
# ===== T-3 集成点 A 结束 =====
```

**集成点 B**：在探索完成后，判断是否继续深入

**文件**: `curious_agent.py`，函数 `run_one_cycle()` 探索完成后

```python
# ===== T-3 集成点 B 开始 =====
# 【集成点 3B】MetaCognitiveController 决策 — 是否继续深入
# 插入位置：curious_agent.py run_one_cycle() 函数内
#         在 "result = self.explorer.explore(...)" 之后
#         在 T-2 quality 评估之后

marginal_return = monitor.compute_marginal_return(topic, quality)
should_continue, reason = controller.should_continue(topic)
should_notify, notify_reason = controller.should_notify(topic)

logger.info(f"[T-3B] Decision for {topic}: continue={should_continue}, notify={should_notify}, marginal={marginal_return:.3f}")

if not should_continue:
    logger.info(f"[T-3B] Stopping deep exploration for {topic}: {reason}")
    from core.knowledge_graph import update_curiosity_status
    update_curiosity_status(topic, "done")

# should_notify 用于后续通知逻辑（T-4 之后的主动通知）
curiosity_item["should_notify"] = should_notify
curiosity_item["notify_reason"] = notify_reason
# ===== T-3 集成点 B 结束 =====
```

**注意**：
- 需要 `update_curiosity_status(topic, status)` 在 knowledge_graph.py 中存在
- `should_notify == True` 且 `quality >= 7.0` 时，写入 notify_queue（见阶段二后）

#### T-3 验收标准

```bash
# 验证1：grep 确认两处集成
grep -n "should_explore\|should_continue\|should_notify" /root/dev/curious-agent/curious_agent.py
# 预期：至少 3 处（should_explore 判断 + should_continue 判断 + should_notify 判断）

# 验证2：触发阻止场景
# 手动在 state.json 设置 explore_count >= max_explore_count（3）
cd /root/dev/curious-agent && python3 curious_agent.py --run --depth medium 2>&1 | grep -i "blocked\|stopping"
# 预期：某个 topic 被 blocked 或 stopping
```

---

## 4. 阶段二：双体协作基础设施

---

### T-4: Curious Agent 统一写入 shared_knowledge/curious/

#### 目标

AgentBehaviorWriter 统一写入 `shared_knowledge/curious/`（替代 `memory/curious/`），同时维护 `index.md`。

#### 主流程集成点

**文件**: `core/agent_behavior_writer.py`，方法 `_sync_to_memory()`

```python
# ===== T-4 集成点 开始 =====
# 【集成点 4】修改 _sync_to_memory() 目标目录
# 修改位置：core/agent_behavior_writer.py _sync_to_memory() 方法内
#         替换 MEMORY_CURIOUS_DIR 为 SHARED_KNOWLEDGE_DIR

SHARED_KNOWLEDGE_DIR = "/root/.openclaw/workspace-researcher/shared_knowledge"
CURIOUS_KNOWLEDGE_DIR = f"{SHARED_KNOWLEDGE_DIR}/curious"  # 权威目录
LEGACY_MEMORY_DIR = "/root/.openclaw/workspace-researcher/memory/curious"  # 兼容降级

def _sync_to_memory(self, topic, findings, quality, sources, discovery_type):
    # 优先写入 shared_knowledge/curious/（统一 schema）
    shared_path = Path(CURIOUS_KNOWLEDGE_DIR)
    shared_path.mkdir(parents=True, exist_ok=True)
    self._write_shared_knowledge(topic, findings, quality, sources, discovery_type, shared_path)

    # 兼容写入 legacy memory/curious/（不删除旧文件）
    legacy_path = Path(LEGACY_MEMORY_DIR)
    legacy_path.mkdir(parents=True, exist_ok=True)
    self._write_legacy_format(topic, findings, quality, sources, discovery_type, legacy_path)

def _write_shared_knowledge(self, topic, findings, quality, sources, discovery_type, base_path):
    """T-4: 写入统一 schema 到 shared_knowledge/curious/"""
    date = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r'[^\w\s-]', '', topic)[:60].strip().replace(' ', '-')
    filename = base_path / f"{date}-{slug}.md"

    TYPE_TO_SECTION = {
        "metacognition_strategy": "## 💡 元认知策略",
        "reasoning_strategy": "## 🧠 推理策略",
        "confidence_rule": "## 📊 置信度规则",
        "self_check_rule": "## 🪞 自我检查规则",
        "proactive_behavior": "## 🔍 主动行为",
        "tool_discovery": "## 🤖 工具发现",
    }
    section = TYPE_TO_SECTION.get(discovery_type, "## 📌 其他规则")

    content = f"""# [finding] {topic}

<!-- shared_knowledge_metadata
{{
  "schema_version": "1.0",
  "type": "curious_finding",
  "source": "curious_agent",
  "topic": "{topic}",
  "quality": {quality},
  "confidence": {quality / 10.0},
  "created_at": "{datetime.now().isoformat()}",
  "shared": false,
  "behavior_applied": true,
  "behavior_section": "{section}",
  "cross_validation": {{"status": "pending", "r1d3_understanding_summary": null}}
}}
-->

**好奇心指数**: {quality}
**置信度**: {quality / 10.0}
**探索时间**: {date}
**shared**: false

---

## 核心发现

{findings.get('summary', '')}
"""

    filename.write_text(content, encoding="utf-8")
    self._update_curious_index(topic, quality, base_path.parent)

def _update_curious_index(self, topic, quality, shared_knowledge_parent):
    """T-4: 维护 shared_knowledge/curious/index.md"""
    index_path = shared_knowledge_parent / "curious" / "index.md"
    entry = f"- **[{quality}]** {topic}\n"

    if index_path.exists():
        content = index_path.read_text()
        if topic not in content:
            content = content.replace("## 最近发现\n", f"## 最近发现\n{entry}")
            index_path.write_text(content)
    else:
        header = "# Curious Agent 探索结果\n\n> 统一索引 | shared_knowledge/curious/\n\n---\n\n## 最近发现\n\n"
        index_path.write_text(header + entry, encoding="utf-8")
# ===== T-4 集成点 结束 =====
```

#### T-4 验收标准

```bash
# 1. 触发高质量探索（quality >= 7.0）
cd /root/dev/curious-agent && python3 curious_agent.py --run --depth medium

# 2. shared_knowledge/curious/ 有新文件
ls /root/.openclaw/workspace-researcher/shared_knowledge/curious/ 2>/dev/null

# 3. shared_knowledge/curious/index.md 已更新
cat /root/.openclaw/workspace-researcher/shared_knowledge/curious/index.md 2>/dev/null | head -15

# 4. legacy memory/curious/ 仍有兼容文件（不删除）
ls /root/.openclaw/workspace-researcher/memory/curious/*.md 2>/dev/null | head -3
```

---

### T-5: R1D3 sync_discoveries.py 演进（读 shared_knowledge/）

#### 目标

R1D3 的 `sync_discoveries.py` 优先读 `shared_knowledge/curious/`，降级读 `memory/curious/`。

#### 主流程集成点

**文件**: `skills/curious-agent/scripts/sync_discoveries.py`，函数 `sync()`

```python
# ===== T-5 集成点 开始 =====
# 【集成点 5】修改 sync() 策略
# 修改位置：skills/curious-agent/scripts/sync_discoveries.py sync() 函数
#         替换原有的 state.json 读取逻辑

SHARED_CURIOUS = os.environ.get(
    "CURIOUS_SHARED_KNOWLEDGE",
    "/root/.openclaw/workspace-researcher/shared_knowledge/curious"
)
LEGACY_MEMORY = "/root/.openclaw/workspace-researcher/memory/curious"

def sync():
    """
    T-5: 同步策略（按优先级）：
    1. 优先扫描 shared_knowledge/curious/（新 schema，有 schema_version）
    2. 降级扫描 memory/curious/（旧 schema，兼容）
    3. 如果都没有，才从 state.json 拉取（最降级）
    """
    new_count = 0

    # 策略1: shared_knowledge/curious/（优先）
    if os.path.exists(SHARED_CURIOUS):
        new_count = _sync_from_shared_knowledge()
        if new_count > 0:
            logger.info(f"[T-5] Synced {new_count} from shared_knowledge/curious/")
            return new_count

    # 策略2: 降级 legacy memory/curious/
    if os.path.exists(LEGACY_MEMORY):
        new_count = _sync_from_legacy_memory()
        if new_count > 0:
            logger.info(f"[T-5] Synced {new_count} from legacy memory/curious/ (deprecated)")
        return new_count

    logger.info("[T-5] No discoveries to sync")
    return 0

def _sync_from_shared_knowledge():
    """T-5: 从 shared_knowledge/curious/ 同步"""
    files = sorted(Path(SHARED_CURIOUS).glob("*.md"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    files = [f for f in files if f.name != "index.md"]

    new_topics = []
    for f in files[:20]:
        content = f.read_text(encoding="utf-8")

        shared_match = re.search(r'"shared":\s*(true|false)', content)
        is_shared = shared_match.group(1) == "true" if shared_match else False

        if not is_shared:
            topic_match = re.search(r'^# \[finding\]\s*(.+)$', content, re.MULTILINE)
            quality_match = re.search(r'\*\*好奇心指数\*\*:\s*([\d.]+)', content)

            if topic_match and quality_match:
                topic = topic_match.group(1).strip()
                quality = float(quality_match.group(1))
                new_topics.append({"topic": topic, "quality": quality, "file": str(f)})

                # 标记 shared: true（写回文件）
                updated_content = re.sub(r'("shared":\s*)false', r'\g<1>true', content)
                if updated_content != content:
                    f.write_text(updated_content, encoding="utf-8")

    if new_topics:
        _update_index_from_shared(new_topics)

    return len(new_topics)
# ===== T-5 集成点 结束 =====
```

#### T-5 验收标准

```bash
# 1. 手动创建测试文件（shared:false）
cat > /tmp/test_find.md << 'EOF'
# [finding] T-5 test topic

<!-- shared_knowledge_metadata
{"schema_version": "1.0", "type": "curious_finding", "shared": false}
-->

**好奇心指数**: 8.0
**shared**: false

## 核心发现

T-5 test content
EOF
mkdir -p /root/.openclaw/workspace-researcher/shared_knowledge/curious
cp /tmp/test_find.md /root/.openclaw/workspace-researcher/shared_knowledge/curious/2026-03-25-t5-test.md

# 2. 运行 sync
cd /root/.openclaw/workspace-researcher && python3 skills/curious-agent/scripts/sync_discoveries.py

# 3. 检查索引更新
grep "T-5 test" /root/.openclaw/workspace-researcher/memory/curious-discoveries.md

# 4. 检查源文件 shared 变为 true
grep "shared" /root/.openclaw/workspace-researcher/shared_knowledge/curious/2026-03-25-t5-test.md
```

---

### T-6: R1D3 write_learning_need() 实现

#### 目标

R1D3 的学习需求结构化写入 `shared_knowledge/r1d3/learning_needs/`。

#### 主流程集成点

**新增文件**: `skills/curious-agent/scripts/write_learning_need.py`

**R1D3 内部调用方式**：
```python
# R1D3 感知到知识缺口时调用：
from skills.curious_agent.scripts.write_learning_need import write_learning_need
write_learning_need(
    topic="Agent 自我认知",
    need_type="curiosity_driven",
    r1d3_description="深入理解 Agent 如何形成对自身的认知",
    trigger_scenario="R1D3 主动好奇",
    confidence_before=0.3,
    existing_knowledge="知道 Reflexion 和 Self-Contrast 等框架",
    granularity_hint="broad",
    curious_topic_hint="agent_self-awareness_mechanisms"
)
```

**实现**（核心结构）：

```python
# skills/curious-agent/scripts/write_learning_need.py

SHARED_KNOWLEDGE_DIR = "/root/.openclaw/workspace-researcher/shared_knowledge"
LEARNING_NEEDS_DIR = f"{SHARED_KNOWLEDGE_DIR}/r1d3/learning_needs"

def write_learning_need(topic, need_type, r1d3_description, trigger_scenario,
                        confidence_before, existing_knowledge="", granularity_hint="broad",
                        curious_topic_hint=None) -> str:
    """T-6: 写入 R1D3 学习需求"""
    date = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r'[^\w\s-]', '', topic)[:60].strip().replace(' ', '-')
    filename = f"{LEARNING_NEEDS_DIR}/{date}-{slug}.md"

    Path(LEARNING_NEEDS_DIR).mkdir(parents=True, exist_ok=True)

    content = f"""# [need] {topic}

<!-- shared_knowledge_metadata
{{
  "schema_version": "1.0",
  "type": "r1d3_learning_need",
  "source": "r1d3",
  "topic": "{topic}",
  "need_type": "{need_type}",
  "confidence_before": {confidence_before},
  "confidence_after": null,
  "粒度标注": "{granularity_hint}",
  "created_at": "{datetime.now().isoformat()}",
  "updated_at": "{datetime.now().isoformat()}",
  "shared": false,
  "curious_status": "pending",
  "curious_finding_ref": null,
  "curious_topic_hint": "{curious_topic_hint or topic}"
}}
-->

**学习需求**: {r1d3_description}
**触发场景**: {trigger_scenario}
**当前置信度**: {confidence_before}

---

## R1D3 已有理解

{existing_knowledge or "（暂无）"}
"""

    Path(filename).write_text(content, encoding="utf-8")
    return filename

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--need-type", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--trigger-scenario", default="cli")
    parser.add_argument("--confidence-before", type=float, default=0.3)
    args = parser.parse_args()
    write_learning_need(
        topic=args.topic,
        need_type=args.need_type,
        r1d3_description=args.description,
        trigger_scenario=args.trigger_scenario,
        confidence_before=args.confidence_before
    )
```

#### T-6 验收标准

```bash
# 1. 运行 write_learning_need
cd /root/.openclaw/workspace-researcher && python3 -c "
from skills.curious_agent.scripts.write_learning_need import write_learning_need
result = write_learning_need(
    topic='test learning need',
    need_type='curiosity_driven',
    r1d3_description='test desc',
    trigger_scenario='unit test',
    confidence_before=0.4
)
print('Written:', result)
"

# 2. 检查文件存在且 schema_version 正确
grep "schema_version" /root/.openclaw/workspace-researcher/shared_knowledge/r1d3/learning_needs/*.md
```

---

### T-7: trigger_explore.sh 增强

#### 目标

`trigger_explore.sh` 双重写入：learning_need（持久化）+ inject API（触发探索）。

#### 主流程集成点

**文件**: `skills/curious-agent/scripts/trigger_explore.sh`

```bash
#!/bin/bash
# T-7: trigger_explore.sh — 双重写入：learning_need + inject API
# 用法: bash trigger_explore.sh "topic name"

TOPIC="$1"
if [ -z "$TOPIC" ]; then
    echo "Usage: $0 <topic>"
    exit 1
fi

# ===== T-7 集成点 开始 =====

# 步骤1: 写入 learning_need（持久化 R1D3 意图）
echo "[trigger_explore] Writing learning_need for: $TOPIC"
python3 /root/.openclaw/workspace-researcher/skills/curious-agent/scripts/write_learning_need.py \
    --topic "$TOPIC" \
    --need-type curiosity_driven \
    --description "R1D3 主动好奇: $TOPIC" \
    --trigger-scenario "trigger_explore.sh 调用" \
    --confidence-before 0.3

# 步骤2: 调用 inject API（触发 Curious Agent 探索）
echo "[trigger_explore] Injecting topic: $TOPIC"
RESPONSE=$(curl -s -X POST http://localhost:4848/api/curious/inject \
    -H "Content-Type: application/json" \
    -d "{\"topic\": \"$TOPIC\", \"source\": \"r1d3\", \"priority\": \"high\"}")

echo "[trigger_explore] Response: $RESPONSE"

# ===== T-7 集成点 结束 =====
```

#### T-7 验收标准

```bash
# 1. 运行 trigger_explore.sh
bash /root/.openclaw/workspace-researcher/skills/curious-agent/scripts/trigger_explore.sh "T-7 test topic"

# 2. 检查 learning_need 是否写入
ls /root/.openclaw/workspace-researcher/shared_knowledge/r1d3/learning_needs/ | tail -3

# 3. 检查 curiosity_queue 有该 topic
curl -s http://localhost:4848/api/curious/state | python3 -c "
import sys,json
s=json.load(sys.stdin)
topics = [x['topic'] for x in s['curiosity_queue']]
print('Topics in queue:', topics)
"
```

---

## 5. 阶段三：injection_priority 机制

---

### T-8: config.py 新增配置结构

#### 主流程集成点

**文件**: `core/config.py`

```python
# T-8: 新增配置类（在 Config 类中添加或新建）

class InjectionPriorityConfig:
    def __init__(self, enabled=True, priority_sources=None, boost_score=2.0, trigger_immediate=True):
        self.enabled = enabled
        self.priority_sources = priority_sources or ["r1d3"]
        self.boost_score = boost_score
        self.trigger_immediate = trigger_immediate

class ExplorationConfig:
    def __init__(self):
        self.mode = "hybrid"
        self.daemon_interval_minutes = 60
        self.daemon_explore_per_round = 1
        self.injection_priority = InjectionPriorityConfig()
```

**config.json 新增**：
```json
{
  "exploration": {
    "mode": "hybrid",
    "daemon": {
      "interval_minutes": 60,
      "explore_per_round": 1
    },
    "injection_priority": {
      "enabled": true,
      "priority_sources": ["r1d3"],
      "boost_score": 2.0,
      "trigger_immediate": true
    }
  }
}
```

#### T-8 验收标准

```bash
grep -n "class InjectionPriorityConfig\|class ExplorationConfig" /root/dev/curious-agent/core/config.py
cd /root/dev/curious-agent && python3 -c "
from core.config import get_config
cfg = get_config()
print('mode:', cfg.exploration.mode)
print('priority_sources:', cfg.exploration.injection_priority.priority_sources)
print('trigger_immediate:', cfg.exploration.injection_priority.trigger_immediate)
"
```

---

### T-9: inject 端点增强

#### 目标

inject 端点识别 `source=r1d3`，应用 boost_score，立即异步触发探索。

#### 主流程集成点（最关键）

**文件**: `curious_api.py`，函数 `api_inject()`，在 `add_curiosity()` 调用之后、return 之前。

```python
# ===== T-9 集成点 开始 =====
# 【集成点 6】inject_priority: source=r1d3 时优先处理
# 插入位置：curious_api.py api_inject() 函数
#         在 "add_curiosity(...)" 调用之后
#         在最终 "return jsonify(...)" 之前

from core.config import get_config
from core.async_explorer import trigger_async_exploration

config = get_config()
priority_cfg = config.exploration.injection_priority

priority_triggered = False
if priority_cfg.enabled and source in priority_cfg.priority_sources:
    effective_score = final_score + priority_cfg.boost_score
    from core.knowledge_graph import update_curiosity_score
    update_curiosity_score(topic, effective_score)

    if priority_cfg.trigger_immediate:
        trigger_async_exploration(topic, score=effective_score)
        priority_triggered = True
        logger.info(f"[T-9] Priority injection for {topic}, async triggered")

# 修改返回值
result_data = {
    "status": "ok",
    "topic": topic,
    "score": final_score,
    "alpha": alpha,
    "mode": mode
}
if priority_triggered:
    result_data["priority"] = True
    result_data["async_triggered"] = True

return jsonify(result_data)
# ===== T-9 集成点 结束 =====
```

#### T-9 验收标准

```bash
# 测试普通 inject
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"T-9 default test","source":"default"}'
# 预期：无 priority 字段

# 测试优先 inject
curl -X POST http://localhost:4848/api/curious/inject \
  -H "Content-Type: application/json" \
  -d '{"topic":"T-9 priority test","source":"r1d3"}'
# 预期：返回包含 "priority": true, "async_triggered": true
```

---

### T-10: async_explorer.py 新建

#### 目标

inject 优先触发时，不阻塞 API 响应，在独立线程中执行探索。

#### 主流程集成点

**新增文件**: `core/async_explorer.py`

**被谁调用**：T-9 的 `curious_api.py` 中的 `trigger_async_exploration()`

```python
# core/async_explorer.py
"""
T-10: 异步探索器 — inject 优先触发时不阻塞 API 响应

被调用位置（集成点 6）：
  curious_api.py api_inject() 函数内
  if priority_cfg.trigger_immediate:
      trigger_async_exploration(topic, score=effective_score)
"""

import logging
import threading
from core.explorer import Explorer
from core.quality_v2 import QualityV2Assessor
from core.knowledge_graph import add_exploration_result, update_curiosity_status
from core.config import get_config

logger = logging.getLogger(__name__)

_explorer = None
_quality_assessor = None

def _get_instances():
    global _explorer, _quality_assessor
    if _explorer is None
    _explorer = Explorer()
        _quality_assessor = QualityV2Assessor()
    return _explorer, _quality_assessor

def _explore_in_thread(topic: str, score: float):
    """在线程中执行探索，完成后更新状态"""
    explorer, quality_assessor = _get_instances()
    try:
        logger.info(f"[T-10] Async exploration started for {topic}")
        result = explorer.explore(topic, depth="medium")
        quality = quality_assessor.assess_quality(topic, result.get("findings", {}), None)
        add_exploration_result(topic, result, quality)
        update_curiosity_status(topic, "done")
        logger.info(f"[T-10] Async exploration completed for {topic}, quality={quality}")
    except Exception as e:
        logger.error(f"[T-10] Async exploration failed for {topic}: {e}")
        update_curiosity_status(topic, "paused")

def trigger_async_exploration(topic: str, score: float = None):
    """
    T-10: 立即触发异步探索
    
    在独立线程中执行，不阻塞 API 响应。
    被 curious_api.py 的 api_inject() 调用（集成点 6）。
    """
    thread = threading.Thread(
        target=_explore_in_thread,
        args=(topic, score),
        daemon=True
    )
    thread.start()
    logger.info(f"[T-10] Triggered async exploration thread for {topic}")
```

#### T-10 验收标准

```bash
# 功能测试（需要配合 T-9 一起验证）
# T-9 验收时如果 async_triggered=true，说明 T-10 已被正确调用

# 直接测试 async_explorer
cd /root/dev/curious-agent && python3 -c "
from core.async_explorer import trigger_async_exploration
import time

trigger_async_exploration('test async topic', score=7.5)
print('Triggered, waiting...')
time.sleep(5)
print('Check complete - verify in state.json')
"

# 检查 state.json 是否有 test async topic 的记录
grep "test async" /root/dev/curious-agent/knowledge/state.json
```

---

## 6. 阶段四：Layer 3 合成能力

---

### T-11: InsightSynthesizer 模块实现

#### 目标

跨 sub-topic 搜索结果生成原创分析（Layer 3 核心）。

#### 新建文件

**文件**: `core/insight_synthesizer.py`

```python
# core/insight_synthesizer.py
"""
T-11: InsightSynthesizer - Layer 3 跨 sub-topic 原创分析合成器

核心能力：
1. cross_topic_patterns() — 跨子话题模式识别
2. generate_hypotheses() — 基于模式生成假设
3. compute_confidence() — 假设置信度评分
4. synthesize() — 合成入口
"""

class InsightSynthesizer:
    def __init__(self, llm_client=None):
        from core.llm_client import LLMClient
        self.llm = llm_client or LLMClient()
    
    def synthesize(self, topic: str, sub_topic_results: dict) -> list[dict]:
        """
        T-11: 合成入口
        
        Args:
            topic: 父话题
            sub_topic_results: { "sub_topic_name": [SearchResult, ...], ... }
        
        Returns:
            [Insight, ...] — 原创洞察列表
        """
        all_snippets = []
        for sub_topic, results in sub_topic_results.items():
            for r in results:
                snippet = self._extract_snippet(r)
                if snippet:
                    all_snippets.append(f"[{sub_topic}] {snippet}")
        
        if not all_snippets:
            return []
        
        # 跨维度模式识别
        patterns = self.cross_topic_patterns(topic, all_snippets)
        
        # 生成原创假设
        hypotheses = self.generate_hypotheses(patterns)
        
        # 置信度评分
        insights = []
        for h in hypotheses:
            confidence = self.compute_confidence(h, all_snippets)
            if confidence >= 0.5:
                insights.append(self._format_insight(topic, h, confidence))
        
        return insights
    
    def cross_topic_patterns(self, topic: str, snippets: list[str]) -> list[dict]:
        prompt = f"""给定主题：{topic}

信息片段：
{chr(10).join(f'- {s}' for s in snippets[:20])}

任务：从这些片段中识别跨维度的共同模式。
输出 JSON：
{{
  "patterns": [
    {{
      "pattern": "模式描述",
      "supporting_snippets": ["片段1", "片段2"],
      "related_sub_topics": ["相关子话题"]
    }}
  ]
}}"""
        result = self.llm.chat(prompt)
        return self._parse_json(result).get("patterns", [])
    
    def generate_hypotheses(self, patterns: list[dict]) -> list[dict]:
        prompt = f"""基于以下跨维度模式，生成原创假设：

{chr(10).join(f'- {p["pattern"]}' for p in patterns)}

要求：
1. 每个假设必须有推理过程
2. 假设应该超出原始信息的简单总结
3. 允许有一定推测性，但必须有片段支撑
4. 生成 3-5 个最具洞察力的假设

输出 JSON：
{{
  "hypotheses": [
    {{
      "hypothesis": "假设内容",
      "type": "causal|correlation|contrast|deduction",
      "reasoning": "推理过程",
      "supporting_snippets": ["片段"]
    }}
  ]
}}"""
        result = self.llm.chat(prompt)
        return self._parse_json(result).get("hypotheses", [])
    
    def compute_confidence(self, hypothesis: dict, snippets: list[str]) -> float:
        support_count = len(hypothesis.get("supporting_snippets", []))
        confidence = min(support_count / 5, 1.0) * 0.7 + 0.3
        return round(confidence, 2)
    
    def _format_insight(self, topic: str, hypothesis: dict, confidence: float) -> dict:
        return {
            "topic": topic,
            "hypothesis": hypothesis["hypothesis"],
            "type": hypothesis.get("type", "correlation"),
            "reasoning": hypothesis.get("reasoning", ""),
            "confidence": confidence,
            "supporting_snippets": hypothesis.get("supporting_snippets", []),
            "generated_by": "InsightSynthesizer"
        }
    
    def _extract_snippet(self, result) -> str:
        if isinstance(result, dict):
            return result.get("snippet", result.get("summary", ""))
        return getattr(result, "snippet", str(result))
    
    def _parse_json(self, text: str) -> dict:
        import json, re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {}
```

#### T-11 验收标准

```bash
cd /root/dev/curious-agent && python3 -c "
from core.insight_synthesizer import InsightSynthesizer
synth = InsightSynthesizer()
results = {
    'memory': [{'snippet': 'Context window limits affect capacity'}, {'snippet': 'Importance scoring for retrieval'}],
    'planning': [{'snippet': 'Reasoning chains need context'}, {'snippet': 'Context window bottleneck'}]
}
insights = synth.synthesize('agent', results)
print(f'Generated {len(insights)} insights')
for i in insights:
    print(f'  - [{i[\"type\"]}] {i[\"hypothesis\"][:60]}... (conf={i[\"confidence\"]})')
"
# 预期：生成 1-3 条原创洞察，confidence >= 0.5
```

---

### T-12: Explorer 集成 Layer 3

#### 目标

在 `explorer.explore()` 完成后，调用 InsightSynthesizer。

#### 主流程集成点（最关键）

**文件**: `core/explorer.py`

搜索 `explore` 方法，在返回 result 之前插入 Layer 3 调用：

```python
# ===== T-12 集成点 开始 =====
# 【集成点 7】Explorer 集成 Layer 3 — InsightSynthesizer
# 插入位置：core/explorer.py explore() 方法
#         在 "return result" 之前
#         前提：T-11 已实现（T-2/T-3 已集成）

# 仅在 medium/deep 深度时执行 Layer 3
if depth in ("medium", "deep") and sub_topics:
    from core.insight_synthesizer import InsightSynthesizer
    
    synthesizer = InsightSynthesizer(llm_client=self.llm_client)
    
    # 构造 sub_topic_results: {name: [search_results]}
    sub_topic_results = {}
    for st in sub_topics:
        st_name = st.get("sub_topic", st.get("topic", "unknown"))
        # 从 result 的 layer1_results 中提取
        st_results = result.get("layer1_results", {}).get(st_name, [])
        if st_results:
            sub_topic_results[st_name] = st_results
    
    if sub_topic_results:
        insights = synthesizer.synthesize(topic, sub_topic_results)
        result["insights"] = insights
        logger.info(f"[T-12] Layer 3 generated {len(insights)} insights for {topic}")
# ===== T-12 集成点 结束 =====

return result
```

#### T-12 验收标准

```bash
# 验证1：grep 确认集成
grep -n "InsightSynthesizer" /root/dev/curious-agent/core/explorer.py

# 验证2：运行一轮 medium 深度探索，检查结果包含 insights
cd /root/dev/curious-agent && python3 curious_agent.py --run --depth medium 2>&1 | grep -i insight
# 预期：有 "[T-12] Layer 3 generated N insights" 日志
```

---

## 7. 阶段五：exploration mode 配置

---

### T-13: daemon 三模式支持

#### 主流程集成点

**文件**: `curious_agent.py`，函数 `run_daemon()`

```python
# ===== T-13 集成点 开始 =====
# 【集成点 8】exploration mode — daemon 三模式支持
# 修改位置：curious_agent.py run_daemon() 函数

def run_daemon(mode: str = None):
    from core.config import get_config
    config = get_config()
    mode = mode or config.exploration.mode
    interval = config.exploration.daemon_interval_minutes

    logger.info(f"[T-13] Exploration mode: {mode}, interval: {interval}min")

    if mode == "api_only":
        # 不执行任何定时探索，只等待外部 inject
        logger.info("[T-13] Mode: api_only, waiting for external injection...")
        import time
        while True:
            time.sleep(3600)

    elif mode == "daemon":
        # 纯定时探索，忽略 trigger_immediate
        logger.info("[T-13] Mode: daemon, pure timed exploration...")
        import time
        while True:
            topic = engine.select_next()
            if topic:
                result = explorer.explore(topic)
                quality = quality_assessor.assess(result)
                write_to_kg(topic, result, quality)
            time.sleep(interval * 60)

    elif mode == "hybrid":
        # 混合模式：daemon 轮询 + inject 优先（inject 通过 T-9/T-10 异步触发）
        logger.info("[T-13] Mode: hybrid, daemon + inject priority...")
        import time
        while True:
            topic = engine.select_next()
            if topic:
                result = explorer.explore(topic)
                quality = quality_assessor.assess(result)
                write_to_kg(topic, result, quality)
            time.sleep(interval * 60)
# ===== T-13 集成点 结束 =====
```

#### T-13 验收标准

```bash
# 验证 config 中 mode 可读取
cd /root/dev/curious-agent && python3 -c "
from core.config import get_config
cfg = get_config()
print('Current mode:', cfg.exploration.mode)
"
```

---

## 8. 阶段六：测试与集成验收

---

### T-15: 全流程集成测试

#### 测试脚本

**新建文件**: `tests/test_v0.2.4_integration.py`

```python
"""
T-15: v0.2.4 全流程集成测试

运行方式：
  cd /root/dev/curious-agent && python3 tests/test_v0.2.4_integration.py

测试覆盖：
  T-1: CuriosityDecomposer 主流程集成
  T-2: QualityV2Assessor 主流程集成
  T-3: MetaCognitiveMonitor 决策被采纳
  T-4: 统一写入 shared_knowledge/curious/
  T-5: R1D3 sync 读 shared_knowledge/
  T-6: write_learning_need()
  T-7: trigger_explore.sh 双重写入
  T-8: config.py 新配置结构
  T-9: inject priority
  T-10: async_explorer
  T-11: InsightSynthesizer
  T-12: Explorer Layer 3 集成
"""

import subprocess
import json
import os
import time
import sys

CURIOUS_API = "http://localhost:4848"
SHARED_KNOWLEDGE = "/root/.openclaw/workspace-researcher/shared_knowledge"
STATE_FILE = "/root/dev/curious-agent/knowledge/state.json"

def run(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"FAIL: {cmd}")
        print(f"  stdout: {result.stdout}")
        print(f"  stderr: {result.stderr}")
    return result

def test(name, condition, details=""):
    status = "✅" if condition else "❌"
    print(f"{status} {name}")
    if details:
        print(f"   {details}")
    return condition

def main():
    results = []
    
    print("=" * 60)
    print("T-15: v0.2.4 全流程集成测试")
    print("=" * 60)

    # T-8: config 加载
    print("\n[T-8] Config 新配置结构...")
    r = run(f"cd /root/dev/curious-agent && python3 -c \"from core.config import get_config; cfg=get_config(); print(cfg.exploration.mode, cfg.exploration.injection_priority.trigger_immediate)\"", check=False)
    results.append(test("T-8: config.py ExplorationConfig 加载", r.returncode == 0, r.stdout.strip()))

    # T-1: CuriosityDecomposer 集成
    print("\n[T-1] CuriosityDecomposer 主流程集成...")
    r = run(f"grep -n 'CuriosityDecomposer' /root/dev/curious-agent/curious_agent.py", check=False)
    results.append(test("T-1: CuriosityDecomposer 在 curious_agent.py 中", r.returncode == 0 and r.stdout.count('\n') >= 2, r.stdout.strip()))

    # T-2: QualityV2Assessor 集成
    print("\n[T-2] QualityV2Assessor 主流程集成...")
    r = run(f"grep -n 'QualityV2Assessor' /root/dev/curious-agent/curious_agent.py", check=False)
    results.append(test("T-2: QualityV2Assessor 在 curious_agent.py 中", r.returncode == 0, r.stdout.strip()))

    # T-3: MetaCognitiveMonitor 决策
    print("\n[T-3] MetaCognitiveMonitor 决策被采纳...")
    r = run(f"grep -n 'should_explore\|should_continue' /root/dev/curious-agent/curious_agent.py", check=False)
    results.append(test("T-3: should_explore/should_continue 在主流程中", r.returncode == 0 and r.stdout.count('\n') >= 2, r.stdout.strip()))

    # T-4: shared_knowledge 写入
    print("\n[T-4] 统一写入 shared_knowledge/curious/...")
    r = run(f"grep -n 'SHARED_KNOWLEDGE\|CURIOUS_KNOWLEDGE' /root/dev/curious-agent/core/agent_behavior_writer.py", check=False)
    results.append(test("T-4: agent_behavior_writer.py 使用 CURIOUS_KNOWLEDGE_DIR", r.returncode == 0, r.stdout.strip()))

    # T-5: R1D3 sync
    print("\n[T-5] R1D3 sync 读 shared_knowledge/...")
    r = run(f"grep -n 'SHARED_CURIOUS' /root/.openclaw/workspace-researcher/skills/curious-agent/scripts/sync_discoveries.py", check=False)
    results.append(test("T-5: sync_discoveries.py 优先读 shared_knowledge", r.returncode == 0, r.stdout.strip()))

    # T-6: write_learning_need
    print("\n[T-6] write_learning_need 实现...")
    r = run(f"ls /root/.openclaw/workspace-researcher/skills/curious-agent/scripts/write_learning_need.py 2>/dev/null", check=False)
    results.append(test("T-6: write_learning_need.py 文件存在", r.returncode == 0, r.stdout.strip()))
    if r.returncode == 0:
        r2 = run(f"grep -n 'schema_version' /root/.openclaw/workspace-researcher/skills/curious-agent/scripts/write_learning_need.py", check=False)
        results.append(test("T-6: write_learning_need.py 写入 schema_version", r2.returncode == 0, r2.stdout.strip()))

    # T-7: trigger_explore.sh
    print("\n[T-7] trigger_explore.sh 增强...")
    r = run(f"grep -n 'write_learning_need' /root/.openclaw/workspace-researcher/skills/curious-agent/scripts/trigger_explore.sh", check=False)
    results.append(test("T-7: trigger_explore.sh 调用 write_learning_need", r.returncode == 0, r.stdout.strip()))

    # T-9: inject priority
    print("\n[T-9] inject priority 机制...")
    r = run(f"grep -n 'trigger_async_exploration' /root/dev/curious-agent/curious_api.py", check=False)
    results.append(test("T-9: curious_api.py 调用 trigger_async_exploration", r.returncode == 0, r.stdout.strip()))

    # T-10: async_explorer
    print("\n[T-10] async_explorer.py...")
    r = run(f"ls /root/dev/curious-agent/core/async_explorer.py 2>/dev/null", check=False)
    results.append(test("T-10: async_explorer.py 文件存在", r.returncode == 0, r.stdout.strip()))

    # T-11: InsightSynthesizer
    print("\n[T-11] InsightSynthesizer...")
    r = run(f"ls /root/dev/curious-agent/core/insight_synthesizer.py 2>/dev/null", check=False)
    results.append(test("T-11: insight_synthesizer.py 文件存在", r.returncode == 0, r.stdout.strip()))
    if r.returncode == 0:
        r2 = run(f"cd /root/dev/curious-agent && python3 -c 'from core.insight_synthesizer import InsightSynthesizer; print(\"ok\")'", check=False)
        results.append(test("T-11: InsightSynthesizer 可导入", r2.returncode == 0, r2.stdout.strip()))

    # T-12: Explorer Layer 3 集成
    print("\n[T-12] Explorer Layer 3 集成...")
    r = run(f"grep -n 'InsightSynthesizer' /root/dev/curious-agent/core/explorer.py", check=False)
    results.append(test("T-12: explorer.py 调用 InsightSynthesizer", r.returncode == 0, r.stdout.strip()))

    # 汇总
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")
    if passed == total:
        print("🎉 所有集成点已就绪！")
    else:
        print("⚠️  部分集成点未完成，需要继续实现")
    print("=" * 60)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
```

#### T-15 验收标准

```bash
# 运行全流程集成测试
cd /root/dev/curious-agent && python3 tests/test_v0.2.4_integration.py

# 预期：全部 ✅（20/20）
# 如果有 ❌，说明对应的模块还未正确集成到主流程
```

---

## 9. 依赖关系与执行顺序总结

### 9.1 关键依赖链

```
T-1 → T-2 → T-3         # 阶段一串行链（每个依赖前一个的集成点）
    ↓
T-4 → T-5              # 阶段二：写入方 → 读取方
    ↓
T-6 → T-7              # R1D3 写入侧
    ↓
T-8 → T-9 → T-10       # 阶段三：配置 → API → 异步执行器
    ↓
T-2,T-3 → T-11 → T-12  # 阶段四：依赖阶段一 + 新模块
    ↓
T-8 → T-13 → T-14      # 阶段五：配置 → daemon 模式
    ↓
全部 → T-15             # 最终集成测试
```

### 9.2 并行可能性

- 阶段一内部不能并行（T-1→T-2→T-3 串行）
- 阶段二和阶段三可以部分并行（T-4/T-5 和 T-8/T-9 无依赖）
- 阶段四依赖阶段一完成后才能开始（T-11 需要 T-2 的集成）
- 阶段五在 T-8 之后可以和阶段三并行

### 9.3 主流程集成点速查

| 集成点 | 文件 | 函数 | 插入位置 |
|--------|------|------|---------|
| 1 | `curious_agent.py` | `run_one_cycle()` | topic 选择后、explore 前 |
| 2 | `curious_agent.py` | `run_one_cycle()` | explore 后、behavior_write 前 |
| 3A | `curious_agent.py` | `run_one_cycle()` | 函数开始，select_next 后 |
| 3B | `curious_agent.py` | `run_one_cycle()` | explore 后，quality 判断后 |
| 4 | `agent_behavior_writer.py` | `_sync_to_memory()` | 替换目标目录常量 |
| 5 | `sync_discoveries.py` | `sync()` | 替换读取策略 |
| 6 | `curious_api.py` | `api_inject()` | add_curiosity 后、return 前 |
| 7 | `explorer.py` | `explore()` | return result 前 |
| 8 | `curious_agent.py` | `run_daemon()` | 函数内部模式分支 |

---

## 10. OpenCode 开发注意事项

### 10.1 每个任务的交付标准

每个任务完成后，必须满足：
1. **代码存在**：文件/函数已创建
2. **主流程集成**：在指定文件的指定位置有调用代码（参考"集成点"列）
3. **集成测试通过**：T-15 中对应的检查项为 ✅

### 10.2 避免"模块完成但不可用"的问题

**检查清单**（每个任务完成时自检）：
- [ ] 我写的代码在哪个文件的哪个函数里被谁调用？（找不到调用方 = 没集成）
- [ ] 集成测试 `tests/test_v0.2.4_integration.py` 中对应的项是否为 ✅？
- [ ] 如果有新增的 import 语句，是否加在了文件顶部？
- [ ] 如果新增了配置文件（config.json），是否通知了 R1D3 侧同步？

### 10.3 向后兼容性

- T-4 保留了 legacy `memory/curious/` 的兼容写入，不删除已有文件
- T-5 优先读新目录，降级读旧目录
- T-8 新增 config.json 字段，不影响现有字段

### 10.4 日志规范

所有新增的集成点必须输出 `[T-N]` 前缀的日志：
```python
logger.info(f"[T-1] Decomposed {topic} into {len(sub_topics)} sub-topics")
logger.info(f"[T-9] Priority injection for {topic}, async triggered")
```
这样在集成测试时可以通过日志确认哪个集成点被执行了。

---

_文档版本: v0.2.4 完整任务文档_
_创建时间: 2026-03-25_
_状态: 待 OpenCode 实现_
_设计文档: `docs/10-双体协作架构设计.md`_
