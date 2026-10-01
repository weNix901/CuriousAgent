# next_move_v0.3.6 — 冲突检测 + 缺口生成 + 发现回流

> **版本**：v0.3.6（大版本，跨 CA2.0 Phase 2/3/4）
> **依据**：v0.3.5 实测现状（2026-10-01）+ 正向/逆向核查
> **决策者**：weNix（2026-10-01：接受调整，撤销数据模型改造，范围选大）

---

## 一、与前版的差异（为什么调整）

### 1.1 撤销项：findings per-source 数据模型改造

v0.3.5 批7 曾结论"C1-B 要先做 per-source 数据模型改造"，2026-10-01 逆向核查**推翻**：

- C1-B 需要的**不是 per-source 原文**，而是**来源级一致性信号**
- 该信号**已有现成基础设施**：`provider_registry` + `curiosity_decomposer._verify_with_providers()`
- 真问题不是"缺数据模型"，而是"**产出没落库**"——一条**死管道**

→ 成本从"改 11 文件数据模型"降到"1 个落库点 + 1 个比对器"。

### 1.2 新增项：检索匹配正确性预检（C0 残留）

**发现于批3 人工复核（2026-10-01，weNix）**：

id18「知识图谱」查询，语义检索命中了 **"Knowledge Distillation"**（sim=0.786）——
系统**拿了错误节点的 quality=8.0/src=0 去判四态**，判成 `partial`；
真相是知识图谱**无对应节点**，应为 `unknown`。

**这意味着**：四态判决器的输入（similarity/quality/source_count）**依赖检索匹配的
正确性**。检索一旦"语义近但主题错"，判决就是**基于错节点的错误判定**。

- C0-A 修了**短词检索**，但**长词的"语义错配"未修**
- 直接打在 C1 公理："决策权归属外部测量"——**但测量对象本身错了，测的就不是它**
- 影响面：所有"语义近但主题不同"的长查询，四态会**系统性失真**

### 1.3 新增项：C2（缺口生成）+ C3（发现回流）+ 三项游离待办

**v0.3.5 只盯 C1-B，遗漏 CA2.0 Phase 3/4。实测：**

| 组件 | 实测状态 |
|------|---------|
| C2-C 自动入队 | ❌ 无 `gap→queue` 代码 |
| C2-B 显式需求 | ❌ `learning_needs/` 目录不存在 |
| C3-B 行为库接通 | ✅ **已通**（4794 行，extraPaths 正确） |
| C3-C 命中追踪 | ❌ 无检索命中日志 |

#### 并入项：三项游离待办（weNix 2026-10-01 决定全部并入）

**① 7 个 pre-existing 测试失败（历史债，根因已查明）**

`tests/test_api_v026.py` 7 个失败，根因是 **commit `09d6b37`（2026-04-17）**
一次性删除了 6 条路由却未同步测试：

| 被删路由 | 对应测试 |
|----------|---------|
| `/api/kg/dream_insights` | TestDreamInsightsAPI (×2) |
| `/api/kg/dormant` | TestDormantNodesAPI |
| `/api/kg/reactivate` | TestReactivateAPI (×2) |
| `/api/kg/frontier` | TestFrontierAPI |
| `/api/kg/calibration` | TestCalibrationAPI |
| **`/api/kg/confidence/<topic>`** | **→ Bug A 的根源：该路由 2026-04-17 被删，Hook 一直 404** |

底层实现大部分仍在（`meta_cognitive_monitor.detect_frontier` /
`get_calibration_error`、`kg_repository.mark_dormant`/`reactivate` 都活着），
只是路由层被削。

→ **处置**：优先**恢复 5 条路由**（接线到现存实现；frontier/calibration 是 C1 有用信号），
而非删测试。

**② confidence 空节点伪装（R-v0.3.5-1）**
软调制公式 `sim × (0.5 + 0.5·q/10)`，quality=0 时 `sim=0.9 → 0.45`。
空节点可伪装"有点知识"。**与批0 同类**（四态输入失真）→ **并入批0** 一起修。

**③ C1-C Hook 端到端验证**
批5/批6 只做了单元级验证（实测端点 200、Skill 输出正确），但
**knowledge-gate Hook 在真实 agent 回复里是否真的注入四态上下文，未验**。
Bug A 的教训就是"看着修好了其实没生效"——必须补端到端验证。
→ **作为批0 的验证门**。

---

#### （原）C2/C3 实测细节

→ C2 整块缺失，C3 只差"反馈环"一段。

---

## 二、v0.3.5 实测基线（本计划的输入真值）

### 2.1 四态真实分布（抽样 235 done 节点）

```
known:   164  (70%)
partial:  71  (30%)
unknown/void: 0（抽样内，需专门构造）
quality=0: 2/235 (0.9%)
src=0:    50/235 (21%)   ← 主要 partial 来源
```

### 2.2 C1 六信号真值

| # | 信号 | 状态 |
|---|------|------|
| 1 | KG 是否存节点 | ✅ |
| 2 | quality | ✅ 已非问题（0 占 <1%） |
| 3 | 来源数 | ⚠️ 21% 为 0 |
| 4 | 探索失败记录 | ✅ failed=17 |
| 5 | provider 一致性 | 🔴 **死数据**（`/api/providers/record` 无调用方，`provider_heatmap.json` 未生成） |
| 6 | 来源间冲突 | ❌ 待建（本版目标） |

### 2.3 已知遗留风险

- **R-v0.3.5-1**：软调制公式 `confidence = sim × (0.5 + 0.5·q/10)`，quality=0 时
  `sim=0.9 → 0.45`。空节点可能伪装"有点知识"。本版记为**观察项**，不修。
- **R-v0.3.5-2**：20 问标注集 `expected` 为**系统自评**，非人工基准。
  `tests/data/coverage_labelled_20.json` 已落盘，**待 weNix 复核**。

---

## 三、正向推理：v0.3.6 需要什么

CA2.0 剩余三块：**C1-B（冲突检测）→ C2（缺口生成）→ C3（发现回流）**。

**依赖链**（关键洞察：批次顺序由"数据依赖"决定，非由能力重要性决定）：

```
批1 接通 provider 一致性管道  ──┬──► 批2 C1-B 冲突检测
（死管道复活 = 信号5 有数据）    │
                                 │
批3 20问标注集复核（人工基准）───┴──► θ/冲突阈值 定标

批4 C2-A/C 缺口计算器 + 自动入队 ──► 批5 C3-C 命中追踪 ──► 批6 C3-D 反馈回好奇
（缺口头号，用批2 的冲突信号做负项）
```

**为什么批1 必须最先**：C1-B 的输入是 provider 一致性，而这管道是死的。
不先接通，批2 无输入（= 批7 空壳重演）。且批1 顺带修复"信号5 死数据"。

---

## 四、执行批次

| 批 | 任务 | 依赖 | 交付物 | 归属 |
|---|------|------|--------|------|
| **0** | **检索匹配正确性预检**（C0 残留） | 无 | 匹配门限/别名/主题一致性检查；防错节点污染四态输入 | CA |
| **0b** | **confidence 空节点伪装修复**（R-v0.3.5-1） | 批0 | 公式边界修正；空节点不再伪装 known | CA |
| **0c** | **C1-C Hook 端到端验证** | 批0 | 真实 agent 回复中验证四态注入生效 | R1D3 |
| **0d** | **恢复 5 条被删路由**（历史债） | 无 | dream_insights/dormant/reactivate/frontier/calibration | CA |
| **1** | **接通 provider 一致性管道** | 无 | 分解器验证结果落 `ops.db`；死端点复活 | CA |
| **2** | **C1-B 冲突检测** | 批1 | `conflict_resolver.py` + 四态输出加 `conflict` 字段 | CA |
| **3** | **20 问标注集复核** | 无（并行） | weNix 修正 `expected`；θ/冲突阈值回测 | weNix+CA |
| **4** | **C2-A/C 缺口计算器 + 自动入队** | 批2 | `gap_calculator.py` + `gap→queue` 闭环 | CA |
| **5** | **C3-C 命中追踪** | 批4 | 检索命中日志 + discovery 引用回填 | R1D3+CA |
| **6** | **C3-D 反馈回好奇** | 批5 | 被引用发现 → 提升同类缺口优先级 | CA |

---

## 五、任务详情

### 批0 — 检索匹配正确性预检（C0 残留）

**问题**（批3 复核实测）：语义检索会返回"语义近但主题错"的节点，四态
判决器**不加甄别**地把该节点的 quality/source_count 当作查询 topic 的信号。

**实例**：`知识图谱` → 命中 `Knowledge Distillation`（sim=0.786，差 0.028 输给
第二名）→ 误判 `partial`，真值应为 `unknown`。

**改动方向**（待细化，先定候选方案）：

| 方案 | 说明 | 风险 |
|------|------|------|
| A. 匹配门限提高 | 单靠相似度阈值（现 0.75）不够，错配在 0.786 仍发生 | 🟡 提高阈值会漏真命中 |
| B. 主题一致性校验 | 命中 topic 与查询 topic 做词面/别名/同义校验，不一致则降级为 `unknown` | 🟢 需别名表 |
| C. 多命中一致性 | 取 top-k，若 top-1 与其余分歧大则标记"匹配不可靠" | 🟡 需调参 |
| D. 匹配置信度字段 | 四态输出新增 `match_confidence`，低于阈值时四态降级 | 🟢 与批2 `conflict` 字段同构 |

**倾向**：B + D 组合（词面/别名校验 + 匹配置信度字段），因为**可解释、无需调参**，
且与 C1 "外部测量" 公理一致。

**验收**：`知识图谱` 不再匹配 `Knowledge Distillation`（返回 `unknown`）；
现有 20 问中真实命中（如 RAG→Reranker）不受影响。

**为什么先做**：批2 的冲突检测、批4 的缺口计算，**全部依赖四态输入正确**。
输入错 → 后面全错。这是 C0 未清理完的地基。

---

### 批1 — 接通 provider 一致性管道

**问题**：`curiosity_decomposer._verify_with_providers()` 产出了
`provider_results = {provider_name: result_count}`，但**只在内存里用一次就丢**。
`/api/providers/record` 端点存在、逻辑完整，但**无任何调用方**。
`provider_heatmap.json` 从未生成。

**改动点**：

| # | 位置 | 改动 |
|---|------|------|
| 1.1 | `core/curiosity_decomposer.py::_verify_with_providers` | 验证完成后，把 `provider_results` 落库（`ops.db.provider_agreement` 表） |
| 1.2 | `ops.db` schema | 新增表 `provider_agreement(topic, provider, result_count, agreed, ts)` |
| 1.3 | 幂等 | 同一 topic 重复验证覆盖，不累积（避免热图失真） |

**为什么落 `ops.db` 而非文件**：v0.3.4 数据治理已收敛为 4 真值源，
运行状态进 SQLite。`provider_heatmap.json` 是旧的文件副本模式，**应改为 ops.db 表**。

**验收**：分解一个 topic 后，`ops.db.provider_agreement` 有该 topic 的多 provider 记录；
`GET /api/kg/confidence/<topic>` 的 `result` 出现 `provider_agreement` 字段。

---

### 批2 — C1-B 冲突检测

**设计原则**：冲突检测 = 外部测量，不问 LLM 内省（同 C1 公理）。

**新建 `core/api/conflict_resolver.py`**（纯函数，仿 `coverage_resolver`）：

```python
def resolve_conflict(
    provider_results: dict,   # {provider: result_count}
    source_count: int,
    threshold: float = 0.5,   # 一致性阈值，待批3 定标
) -> ConflictVerdict:
    """多 provider 结果一致性 → 冲突判定。
    一致 (all providers 都找到 或 都找不到) → no_conflict
    分歧 (部分找到部分找不到)               → weak_conflict
    冲突 (结果数差异 > threshold)           → strong_conflict
    """
```

**四态输出扩展**（`coverage_resolver.py` 的 `CoverageVerdict`）：

```python
+ conflict: str = "none"   # none | weak | strong
+ conflict_reason: str = ""
```

**注意**：`conflict` 是**附加维度**，不改变四态主判定（`known` 仍是 `known`，
只是附带"来源有分歧"标注）。这是规格原话"四态之外的附加维度"。

**验收**：构造一个部分 provider 一致的 topic → `conflict != "none"`；
全部一致的 topic → `conflict == "none"`。

---

### 批3 — 20 问标注集复核（人工基准）

**这是全版唯一的"人工工作"，且是所有阈值定标的前提。**

**输入**：`tests/data/coverage_labelled_20.json`（已落盘）
**动作**：weNix 逐条确认/修正 `expected`，填 `_meta.human_review`
**产出**：
- 修正后的标注集（作为 C1-A 验收基准）
- θ₁/θ₂ 回测（用真人基准重新网格搜索）
- C1-B 冲突阈值 `threshold` 回测（需构造带冲突的样本）

**验收**：标注集 `_meta.human_review.reviewed_by` 非空；
`calibrate()` 在真人基准上 agreement ≥ 70%。

**⚠️ 阻塞关系**：批3 若不完成，C1-A 的"一致率"永远只是自评。

---

### 批4 — C2-A/C 缺口计算器 + 自动入队

**新建 `core/api/gap_calculator.py`**：

```python
缺口价值 = 覆盖度缺口 × 相关性 × 可解性   # 可解性仅排序，不进价值
覆盖度缺口 = 1 - KG_quality(topic)/10
相关性     = 共现频率 + 会话关键词 + 显式需求
```

**相关性代理**（CA2.0 §4.2）：
1. 共现频率 — KG 路径距离（`exploration_history.co_occurrence` 已有）
2. 会话触发 — 近 N 次会话用户消息关键词
3. 显式需求 — **需新建** `shared_knowledge/r1d3/learning_needs/`

**自动入队闭环**：
```
高价值缺口 → 去重检查 → queue.add → 触发探索
```

**验收**：无人工植入下，探索队列**自动**出现 ≥1 条合理任务。

---

### 批5 — C3-C 命中追踪

行为库已接通（C3-B ✅），缺"命中追踪"。
**动作**：记录 discovery 是否被 `memory_search` 检索/被 R1D3 输出引用。
**证据**：检索命中日志（文件被加载 = extraPaths 配置 + 检索命中日志）。

**验收**：从"某个缺口"到"某条 R1D3 输出变化"的文件级追溯链 ≥1 例。

---

### 批6 — C3-D 反馈回好奇

**动作**：被引用/被检索的 discovery → 提升同类缺口优先级（反馈环闭合）。

**验收**：至少 1 例 discovery 被引用后，其同类缺口优先级实际上升（可观测 diff）。

---

## 六、验收标准（整体）

| 项 | 标准 | 验证方式 |
|----|------|---------|
| 批0 | 检索匹配正确 | `知识图谱` 不再错匹配；真命中不受影响 |
| 批0b | 空节点不伪装 | quality=0 节点不再得到 known 判定 |
| 批0c | Hook 端到端生效 | 真实回复中四态上下文实际注入 |
| 批0d | 路由恢复 | 7 个陈旧测试全部转绿 |
| 批1 | provider 一致性落库 | `ops.db.provider_agreement` 有数据 |
| 批2 | C1-B 冲突可判 | 构造样本 → `conflict != none` |
| 批3 | 人工基准建立 | `human_review.reviewed_by` 非空 + agreement ≥ 70% |
| 批4 | 缺口自动入队 | 队列自动出现 ≥1 合理任务 |
| 批5 | 追溯链 | 缺口→输出变化 ≥1 例 |
| 批6 | 反馈环 | 优先级上升 ≥1 例 |

---

## 七、风险登记

| # | 风险 | 等级 | 缓解 |
|---|------|------|------|
| R0 | 检索语义错配污染四态输入（C0 残留） | 🔴 | 批0 预检；未修前所有长查询判定不可信 |
| R1 | provider 一致性数据稀疏（分解不常跑） | 🟡 | 批1 落库后需跑一批 topic 才有样本 |
| R2 | 冲突阈值无基准可定标 | 🔴 | 依赖批3 人工基准；无基准则阈值只能"观察" |
| R3 | C2 相关性代理"读心"倾向 | 🟡 | 坚持外部可查信号，不做意图推断 |
| R4 | confidence 空节点伪装（R-v0.3.5-1） | 🟡 | 观察项，本版不修 |
| R5 | 20 问标注集不覆盖 void 态 | 🟡 | 批3 复核时补 void 样本（需 failed 记录） |

---

## 八、待 weNix 决策项

1. **批1 落库位置**：`ops.db.provider_agreement` 表（推荐）vs 保留 `provider_heatmap.json`？
2. **批3 时序**：是否在批1 完成后立即复核标注集（解锁阈值定标）？
3. **C2-B 显式需求目录**：`shared_knowledge/r1d3/learning_needs/` 由谁写？（R1D3 主动声明 vs 从对话推断）

---

_本计划基于 2026-10-01 v0.3.5 实测数据写成。_
_数据源：Neo4j（1429 节点）、queue.db（failed=17/pending=182）、_
_coverage_labelled_20.json、provider_heatmap 死管道核查。_
