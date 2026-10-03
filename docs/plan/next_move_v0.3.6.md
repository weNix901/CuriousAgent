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

### 1.3.1 【2026-10-02 实测修订】0d 方向修正：不是「恢复历史」，是「按 CA2.0 目标取舍」

**修订前（错误）**：0d = 「恢复 5 条被删路由」，含 `/api/kg/confidence/<topic>`。

**实测证据（2026-10-02，全只读）**：

| 路由 | live curl @ :4848 | pytest 状态 | CA2.0 目标对位 | 结论 |
|------|:---:|:---:|------|------|
| `/api/kg/confidence/<topic>` | **HTTP 200** ✅ | **passed** ✅ | 服务 C1-C（我的 hook） | ⛔ **已在（v0.3.5 `fd56b6b` 恢复）。绝不重复注册** |
| `/api/kg/dream_insights` (+`/<topic>`) | 404 ❌ | 2 failed | **C3 回流 + F8-c 治理** | ✅ 恢复（纯接线） |
| `/api/kg/frontier` | 404 ❌ | 1 failed | **C2 缺口数据源** | ✅ 恢复（作为 C2 上游） |
| `/api/kg/calibration` | 404 ❌ | 1 failed | C1 自省质量 | ⚠️ 恢复，但**先修空历史假信号**（+`no_data` 态） |
| `/api/kg/dormant` | 404 ❌ | 1 failed | **无对位** | ❌ 不恢复，删测试 |
| `/api/kg/reactivate` | 404 ❌ | 2 failed | C2-D 弱相关 | ❌ 低优先，宜并入 C2-D；本期删测试 |

**两条关键事实（推翻旧计划）**：
1. **confidence 从未「缺失」** —— 它 2026-04-17 被 `09d6b37` 删、2026-10-01 由 `fd56b6b` 恢复。当前 200 且返回体完整（`coverage`/`confidence`/`similarity`/`source_count`）。**把它算进恢复清单 = 双注册 → Flask 启动 `AssertionError` → CA 起不来 → knowledge-gate hook 全断 → R1D3 失能。**
2. **`dormant` 底层缺的是「查询能力」不是「路由」** —— `knowledge_graph_compat` 只有 `mark_dormant`（写），无 `get_dormant_nodes`（读）。CA2.0 §4.1-4.3（C1/C2/C3）**无任何对 dormant 列表的需求**。属 v0.2.6 遗留端点。

> **教训（同 AGENTS.md）**：上一轮用「底层实现存活」推断「可接线恢复」，是又一个「用现象推断结论」。**实现存活 ≠ 语义对位 ≠ 系统需要。** 判定必须读到实现体 + 对照高阶目标。

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
| **0d** | **路由与 CA2.0 目标对齐**（非「恢复历史」） | 无 | 恢复 3 条对位路由（dream_insights×2/frontier/calibration）；删 2 条不对位测试（dormant/reactivate） | CA |
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

**⚠️ 0d 前置：先修 `tests` 包名冲突（阻塞整个测试基线）**

`tests/test_meta_cognitive_controller.py` / `test_meta_cognitive_monitor.py` 在**收集期即 ImportError**：

```
ImportError: cannot import name 'isolated_knowledge_graph' from 'tests.test_utils' (unknown location)
```

**根因（实测）**：`PYTHONPATH` 中的 `/root/dev/dualLoopAgent/openharness` 使 `import tests` 解析到
**另一个仓库**的 `tests/__init__.py`（`/root/dev/dualLoopAgent/openharness/tests/__init__.py`），
不是本仓库的 `tests/`。本仓库无 `tests/__init__.py`，导致符号「在文件中存在却报 unknown location」。

**修法（待定，需 weNix 确认）**：
- 选项 A：本仓库补 `tests/__init__.py` + 在 conftest 中 `sys.path.insert(0, repo_root)` 置顶 → 保证本仓库 `tests` 优先
- 选项 B：改用 `conftest.py` 的 `rootdir` 与 `importmode=importlib`（pytest.ini），避免同名包
- **不选**：改全局 PYTHONPATH（会波及 dualLoopAgent）

**验收**：`pytest tests/ --co` 无 collection error。

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
| 批0d | 路由与目标对齐 | 4 个对位测试转绿（dream_insights×2/frontier/calibration）；2 个不对位测试移除（dormant/reactivate） |
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
| **R6** | **0d 误把 confidence 计入恢复 → 双注册 → CA 起不来 → R1D3 hook 全断** | 🔴 | 已在 §1.3.1 实测排除；编码前必须 `grep -c "api/kg/confidence" curious_api.py` 确认唯一 |
| **R7** | **`tests` 包名冲突（dualLoopAgent 抢占）→ 基线无法收集** | 🔴 | 0d 前置修（见批0 前置节）；`pytest tests/ --co` 必须无 error |
| **R8** | **calibration 空历史 Brier=0.0 被读成「完美校准」** | 🟡 | 恢复时新增 `no_data` verdict；无预测样本时不报 well_calibrated |

---

## 七之半、v0.3.6 测试基线（2026-10-02 重建）

### 基线建立命令（可复现）

```bash
cd /root/dev/curious-agent
timeout 150 python3 -m pytest tests/api/ tests/test_api_v026.py -q -p no:cacheprovider
```

> 注：全量 `pytest tests/` 有 1017 条，单次运行 > 400s 被 SIGKILL；
> 且收集期触发真实 DreamAgent（日志洪水）。**本期基线以「api 子集」为准**。

### 当前基线（修订前，2026-10-02）

| 子集 | 结果 |
|------|------|
| `tests/api/` + `tests/test_api_v026.py` | **7 failed, 41 passed**（44.5s） |
| `tests/` 全量收集 | **1017 collected, 2 errors**（无法完成全跑） |

### 目标基线（v0.3.6 完成后）

| 子集 | 目标 |
|------|------|
| `tests/api/` + `tests/test_api_v026.py` | **全绿**（删除 2 条不对位测试后，不再有绕过断言） |
| `tests/` 全量收集 | **0 error**（修好 `tests` 包名冲突） |

### 测试文件版本标注规范（本版开始强执行）

每个测试文件首行 docstring 必须写清**对应版本 + 覆盖的 CA2.0 条目**：

```python
"""<端点/能力> 测试（v0.3.6）

对应设计：docs/plan/next_move_v0.3.6.md 批0d
对应 CA2.0 条目：C3-B / C2-A
变更说明：<新增/修正/删除及原因>
"""
```

### 测试处置清单（0d）

| 类/测试 | 处置 | 原因 |
|---------|------|------|
| `TestConfidenceAPI` | **保留**（已绿） | 对应 C1-C；confidence 路由已存在 |
| `TestDreamInsightsAPI` (×2) | 保留 | 对应 C3 回流 + F8-c |
| `TestFrontierAPI` | 保留 | 对应 C2 缺口数据源 |
| `TestCalibrationAPI` | 保留（断言加 `no_data` 分支） | C1 自省；空历史时非 well_calibrated |
| `TestDormantNodesAPI` | **删除** | CA2.0 无对位；v0.2.6 遗留 |
| `TestReactivateAPI` (×2) | **删除** | 宜并入 C2-D；本期无对位 |

---

## 七之三、批0c — knowledge-gate Hook 端到端勘察（2026-10-03，只读）

### 勘察结论：Hook 链路上存在三层断裂（"看着修好了其实没生效"）

Hook 实调 `/api/knowledge/check`。追踪 → 该端点用 `get_node_sync(topic)`
**精确匹配**，且读取 **`confidence` 字段**。实测（全库 3724 节点）：

```
total=3724   status=done=3050   confidence>0 = 0   quality>0 = 1366
```

`confidence>0` 的节点数 **= 0**（全库从未写入过非零 confidence）。

| 层 | 问题 | 证据 |
|----|------|------|
| **L1 匹配策略** | 端点用精确匹配，非语义 | `RAG` → 0%（节点名不含 "RAG"） |
| **L2 字段选错** | 读恒为 0 的 `confidence`；有效信号是 `quality` | 精确命中节点仍返回 0% |
| **L3 四态未接** | Hook 只读 confidence，不消费 `coverage` | handler.ts 无 coverage 分支 |

**这就是 Bug A 的完整解释**：路由修了（v0.3.5）、四态做了（0/0b）、E1 门加了，
但 Hook 走的是**另一条匹配方式错 + 字段错 + 不读四态**的路。

### 只读验证：改用 `check_confidence` 后的预期值（2026-10-03）

| 查询 | 现状 | 修复后（check_confidence） |
|------|------|---------------------------|
| `RAG` | 0.0 / novice | **0.700 / intermediate / known** |
| `知识图谱` | 0.0 / novice | **0.000 / unknown**（E1 拦幽灵节点）|
| `transformer attention` | 0.0 / novice | **0.640 / intermediate / known** |
| `agent 上下文管理` | 0.0 / novice | **0.175 / beginner / partial**（0b 生效）|
| `不存在的话题xyz` / `""` | 0.0 / novice | 0.000 / unknown（兜底）|

`check_confidence` 输出键：`confidence, level, gaps, coverage, coverage_reason,
matched_topic, similarity, quality, source_count, topic` —— 旧契约四字段
（`confidence`/`level`/`gaps`/`guidance`/`should_search`/`should_inject`）
全部可映射，其余为纯派生。

### 修法（决策：Y 扩展契约；分两步）

**第一步（Python，本期实现）**：`/api/knowledge/check` 内部改调
`KnowledgeConfidenceHandler.check_confidence()`，响应体**扩展**（向后兼容）：

```json
{
  "success": true,
  "result": {
    "topic": "...",
    "confidence": 0.70,          // 旧字段，值改为有效置信度
    "level": "intermediate",     // 旧字段
    "gaps": [],                  // 旧字段
    "guidance": "...",          // 旧字段（由四态派生）
    "should_search": true,       // 旧字段（由四态派生）
    "should_inject": true,       // 旧字段（由四态派生）

    "coverage": "known",         // 新增（四态）
    "coverage_reason": "...",    // 新增
    "matched_topic": "...",      // 新增
    "similarity": 0.756,         // 新增
    "quality": 8.5,              // 新增
    "source_count": 5            // 新增
  }
}
```

- 旧字段**保留**（Hook 零改即可拿到正确 confidence）
- 新字段**追加**（L3 可解，Hook 后续可消费四态）
- `guidance`/`should_search`/`should_inject` 由四态映射：
  - `known` → 不搜索，直接用 KG
  - `partial` → 建议搜索补充
  - `unknown` → 搜索 + 注入探索
  - `void` → 搜索 + 标注"系统无基础"

**第二步（TS，后续）**：Hook 消费 `coverage`，注入四态上下文，完成 0c 验收
（“真实回复中四态实际注入”）。

### 0c 验收标准（分层）

| 阶段 | 标准 | 验证方式 |
|------|------|---------|
| 第一步 | `/api/knowledge/check` 返回有效 confidence + 四态 | live curl `RAG` → confidence 0.7 且含 `coverage=known` |
| **中间门** | **Hook 从新响应中取到正确的 `confidence`** | 模拟 `handler.ts` 调端点，确认解析值 == 期望（只读，不改 TS）|
| 第二步 | 真实 agent 回复中四态上下文实际注入 | 带 Hook 的对话流，检查注入内容含 coverage |

**中间门（新，2026-10-03）** —— 为何要单独立门：
Hook 的失败模式是“静默”（`handler.ts` 外层 try/catch 吞异常，Bug A 教训）。
若跳过中间门直接做第二步，一旦 Hook 取数错（如字段路径变化），会表现为
“改了但没生效”，难以定位。中间门只读验证：
1. Hook 的解析路径 `kgData.result.confidence` 在新响应体下仍成立；
2. 取值与 `check_confidence` 的预期一致（如 RAG→0.70）；
3. Hook 的三档分支（≥0.85 / ≥0.6 / >0）对当前数据落在预期档位。
通过后才进第二步。

#### 中间门实测结果（2026-10-03，通过）

Node 直接执行 Hook 解析逻辑打真实端点：

| topic | Hook 解析 conf | coverage | 现有分支 |
|-------|:---:|:---:|------|
| `RAG` | 0.700 | known | 中(60-85%) |
| `transformer attention` | 0.640 | known | 中(60-85%) |
| `知识图谱` | 0.000 | unknown | **conf=0 → 不注入** |
| `agent 上下文管理` | 0.175 | partial | 低(<60%) |
| `不存在xyz` | 0.000 | unknown | **conf=0 → 不注入** |

修复前这些全是 conf=0（永远不注入）。中间门揭示新问题：**`coverage=unknown`
被现有三分支静默吞掉**（conf=0 → 无注入）—— 按 C1 设计，unknown 应触发
“搜索 + 注入探索”。这成为第二步（Z）的核心动机。

#### 第二步（Z）设计 — Hook 消费四态

**目标**：Hook 从“只看 confidence 数值”改为“以 `coverage` 四态为主轴”，
使 `unknown`/`void` 不再静默。

**现状问题**（`handler.ts` L92-107）：三分支只看 `confidence` 数值；
`coverage=unknown` 且 conf=0 时，`else if (confidence > 0)` 不成立 → **零注入**。
四态信息已随响应体到达，Hook 却未读。

**改法**：新增 `coverage` 优先分派（数值分支降为兜底）：

| coverage | 注入文案 | 意图 |
|-----------|---------|------|
| `known` | KG 有完整知识（conf=…），直接使用 | 直接作答 |
| `partial` | KG 有部分知识（conf=…），建议搜索补充 | 作答 + 搜索 |
| `unknown` | KG 无此主题，先搜索，失败则 LLM 作答并注入 CA 探索 | 搜索 + 探索 |
| `void` | KG 无此主题且历史探索失败，系统无知识基础 | 搜索 + 重构探索 |

- 旧数值分支**保留为 fallback**（当响应无 `coverage` 字段时，如旧服务端）
- 注入文案可带上 `matched_topic`（当 known/partial 时），增强可解释性
- 不变式：仍绝不 throw；仍仅当 `context.agentId === 'researcher'` 时注入

**验收**：带 Hook 的真实 agent 回复中，对 `知识图谱` 类查询能看到
`coverage: unknown` 的注入（而非静默），对 `RAG` 类看到 known 注入。

**变更面**：`handler.ts` + `npm run build`（tsc → dist）。与 Python 侧解耦，
Python 已完成（第一步已提交）。

---

## 八、待 weNix 决策项

1. **批1 落库位置**：`ops.db.provider_agreement` 表（推荐）vs 保留 `provider_heatmap.json`？
2. **批3 时序**：是否在批1 完成后立即复核标注集（解锁阈值定标）？
3. **C2-B 显式需求目录**：`shared_knowledge/r1d3/learning_needs/` 由谁写？（R1D3 主动声明 vs 从对话推断）
4. **批0c 第二步时序**：Hook 消费四态（TS 改动 + 重编译）本期做还是下期？

---

_本计划基于 2026-10-01 v0.3.5 实测数据写成。_
_数据源：Neo4j（1429 节点）、queue.db（failed=17/pending=182）、_
_coverage_labelled_20.json、provider_heatmap 死管道核查。_
