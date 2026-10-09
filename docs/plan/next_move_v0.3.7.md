# next_move_v0.3.7 — 硬化与收口（Hardening & Consolidation）

> **版本**：v0.3.7
> **依据**：2026-10-08 v0.3.6 收尾审计 + 2026-10-09 KG 重复边/约束修复实测
> **决策者**：weNix（2026-10-09："把 0.3.7 的计划写一下"）
> **前置**：`docs/plan/next_move_v0.3.6.md`（批0–批8 全部 ✅）、
> `docs/plan/next_move_v0.3.6_SSOT.md`（SSOT-0..6 全部落地）

---

## 〇、一句话定位

> **v0.3.6 把"空转的管路"接通了；v0.3.7 做三件事：堵住数据层的复发口子、
> 重建可信任的测试基线、把 C3-D 反馈环的产出变成可观测指标。**

v0.3.6 解决的是「数据源唯一性」与「通路一致性」。
但 2026-10-09 发现 **数据层仍有会自我复发的隐患**（KG 重复边靠人工清理），
以及**测试基线仍是归档状态**（`legacy_tests_v026/`，95 failed）。
这两项不解决，后续任何功能都在流沙上盖楼。

---

## 一、v0.3.6 收尾状态（本计划的输入真值）

| 项 | 状态 | 证据 |
|----|------|------|
| 批0–批8 | ✅ 全部完成 | `git log`：`3d6920d` / `bbe7824` / `fcf4f71` 等 |
| SSOT-0..6 | ✅ 全部落地 | `c4433e7`（唯一真源收敛）、`a01b302`（exploration_history + 改名） |
| C3-D 重定向 | ✅ 已接入 R1D3 | `347df33` + `fcf4f71`（hook + skill） |
| 图谱 UI 关系类型 | ✅ 与 KG 完全对应 | `c5f55a0` |
| **KG 重复边** | ⚠️ **人工清理过一次**（36106→5027，降 86%） | 2026-10-09 实测 |
| **关系唯一约束** | ✅ **已加（本轮）** | `neo4j_client._init_relation_constraints()` |
| **测试基线** | ❌ **仍归档**（`legacy_tests_v026/`，95 failed / 995 passed） | `951e91a` + README |
| **health 端点 storage** | ✅ **已修（本轮）** | `curious_api.py:2839` |

### 1.1 本轮（2026-10-09）已完成的修复

| # | 修复 | 文件 | 验证 |
|---|------|------|------|
| F1 | Neo4j 关系唯一约束（防重复边复发） | `core/kg/neo4j_client.py` | `ConstraintValidationFailed` 挡下重复 CREATE ✅ |
| F2 | 写边带 `key` 属性（`<from>\|<type>\|<to>`） | `core/kg/kg_repository.py` | MERGE 幂等，边数不变 ✅ |
| F3 | 历史边回填脚本 | `scripts/backfill_relation_keys.py` | 5044 边全部打标，0 重复 ✅ |
| F4 | health 端点 KG 后端不可用改为响亮失败 | `curious_api.py` | 模拟不可用 → ERROR + 503；启动门禁 SystemExit(1) ✅ |
| F5 | **删除死代码 `json_kg_repository.py`** | `core/kg/` | 457 行删除，零残留引用 ✅ |
| F6 | 测试基线 rootdir 固化 | `conftest.py` + `tests/__init__.py` | 1106 tests collected，零 ImportError ✅ |

**F4 关键判断（weNix 2026-10-09）**：原方案是 `null` + `available`，但 weNix 指出
**应直接响亮失败**——静默降级（哪怕返回 `null`）仍是在"看起来合理地"掩盖故障。
后端不可用必须：① 打 ERROR 日志 ② 端点返回 503 ③ 启动时拒绝带病启动（SystemExit(1)）。
顺带修了一个隐藏杀手：全仓库此前**从未配过 logging handler**，ERROR 会被吞掉 = 又一个静默失败。

> **关键发现（写入纪律）**：这套 Neo4j（Kernel **2026.03.1 / Cypher 25**）
> **只接受属性级关系唯一约束**（`REQUIRE r.key IS UNIQUE`），
> 裸 `REQUIRE r IS UNIQUE` 语法报错。因此唯一性必须**建立在合成属性 `key` 上**，
> 不是靠 relationship-type 本身。这条要沉淀进 `数据源唯一性与通路一致性规范.md`。

---

## 二、v0.3.7 三条主线

```
主线 A：数据层防复发（让"清理"变成"不可能再脏"）
主线 B：测试基线重建（从 95 failed 到可信任的干净基线）
主线 C：C3-D 反馈环观测化（把"发现引用率"从定义变成数字）
```

**依赖**：A 与 C 无依赖可并行；B 是 A/C 的验收基础设施（建议先起 B 的隔离）。

---

## 三、主线 A — 数据层防复发

### 3.1 背景：为什么"清理过了"还不够

2026-10-09 修复前，KG 有 **36106 条边**，去重后应约 5027 条。
根因：Neo4j **无关系唯一约束** + 部分写入路径历史用 `CREATE`。
本轮已加约束 + 写 key，但仍有**未覆盖的写入点**需清点：

| 写入点 | 现状 | 待办 |
|--------|------|------|
| `kg_repository.add_relation` | ✅ 带 key + 约束 | 无 |
| `kg_repository.update_kg_relation(add)` | ✅ 带 key + 约束 | 无 |
| `kg_repository.py:486` `FOREACH MERGE` 批量路径 | ⚠️ **未带 key** | **A-1** |
| `scripts/migrate_state_to_neo4j.py:72,77` | ⚠️ 直接 `execute_write` | **A-2**（迁移脚本，见下） |
| `json_kg_repository.py:110` | ⚠️ JSON fallback 后端 | **A-3**（key 是否含 relation_type） |
| `dream_agent._create_rel` | 经 factory → `add_relation` | ✅ 间接覆盖 |

### A-0 — 全量写入点清点（只读，先做）

**任务**：`grep -rn 'MERGE\|CREATE ('` + `add_relation\|create_relation` 全仓扫描，
产出**唯一写入路径清单**，确认每条路径都经过带 key 的 `add_relation`。
**产出**：`docs/plan/v0.3.7_kg_write_paths.md`。
**验收**：清单里每条路径都标注「带 key ✅ / 不带 key ❌」，❌ 项变成 A-1..A-3。

### A-1 — 批量 MERGE 路径补 key

**改动**：`core/kg/kg_repository.py:486` 的 `FOREACH MERGE` 加 `key` 属性。
**验收**：批量路径写入后，重复次写不增边（对比边数）。

### A-2 — 迁移/回填脚本规范化

**改动**：
- `scripts/migrate_state_to_neo4j.py` 的关系创建补 key（或直接改调 `add_relation`）。
- `scripts/backfill_relation_keys.py` 增加 `--verify` 模式（只读校验所有边都有 key）。
**验收**：`--verify` 在干净库上返回 "all edges have key"。

### A-3 — ~~JSON fallback 后端 key 一致性~~ ✅ **已随本轮完成（2026-10-09）**

**决策变更**：原计划是"确认 JSON 后端 key 含 relation_type"，但核查后确认
**JSON 后端是死代码**（`JSONKGRepository` 全仓库零实例化，无 fallback 切换到它）。
weNix 决策：**直接删除，不留后患**。

**实际执行**：
- 删除 `core/kg/json_kg_repository.py`（445 行）
- 清理 `scripts/verify_ssot.py` 的 skip 引用 + doc/ARCHITECTURE 文件树条目
- 验证：`*.py` 零残留引用，`import core.kg.repository_factory` OK

→ 该批**无需再做**；原"key 含 relation_type"的历史 bug 随文件删除一并消失。
commit `33cd302`。

### A-4 — 约束基线固化 + 启动自检

**任务**：
- 把 4 条约束的期望名/类型写入 `数据源唯一性与通路一致性规范.md`（真源裁定表补一行）。
- `connect()` 的约束创建失败时**升级为 WARNING + 计数**（当前只 warning，不汇总）。
- 加一个只读健康检查：`GET /api/system/health` 的 `kg` 增加 `constraints_ok: bool`。
**验收**：删掉一条约束后重启，health 显示 `constraints_ok: false`，且 `connect()` 自动补回。

### A-5 — 重复边巡检（周期性护栏）

**任务**：仿 SSOT-0 的"读源护栏"思路，加一个**周期性重复边自检**——
每 N 次 daemon tick（或每日）统计 `count(r) vs count(DISTINCT r.key)`，
不等则告警。
**产出**：`core/kg/edge_integrity.py`（只读检查）+ daemon tick 接线。
**验收**：人为制造一条重复边（绕过约束不可能，改测 key 缺失）→ 告警触发。

---

## 四、主线 B — 测试基线重建

### 4.1 背景

v0.3.6 把旧测试整体归档（`951e91a`），状态 **95 failed / 995 passed / 1106 collected**。
归档 README 记录了失效根因。v0.3.7 要把基线**重建为可信任的**：
不是"让数字好看"，是"让 CI 能拦住回归"。

### B-0 — 归档用例三分类（先做，只读）

**任务**：把 `legacy_tests_v026/` 的用例按三类打标：

| 类别 | 处理 |
|------|------|
| **仍有效** | 迁入新 `tests/`，修 fixture |
| **测旧行为**（指向已废弃链路，如 CuriosityDecomposer） | **删除**（同 `abf7fcb` 纪律） |
| **flaky / 依赖外部** | 隔离到 `tests/integration/`（标记 `@pytest.mark.integration`） |

**产出**：`legacy_tests_v026/TRIAGE.md`（用例 → 类别 → 去向）。
**验收**：三类总和 = 1106，无遗漏。

### B-1 — 修 `tests` 包名冲突（阻塞项）

**根因（批0 记录）**：`PYTHONPATH` 中 `/root/dev/dualLoopAgent/openharness`
使 `import tests` 解析到**另一个仓库**，导致 `ImportError: unknown location`。
**修法（需 weNix 确认）**：二选一——
- 在仓库内加 `tests/__init__.py` + 用 `conftest.py` 固化 rootdir；
- 或从 `PYTHONPATH` 移除 `dualLoopAgent/openharness`。
**验收**：`pytest --collect-only` 无 ImportError。

### B-2 — 重建隔离 fixture

**任务**：建立 `tests/fixtures/`——
- 内存/临时 Neo4j 或 mock client（参照 `legacy_tests_v026/core/kg/test_neo4j_client.py` 的 patch 模式）；
- 临时 queue.db / ops.db；
- **禁止**测试写生产 `knowledge/ops.db`。
**验收**：`tests/` 下所有用例可离线运行（无真实 Neo4j 依赖）。

### B-3 — 分层测试套件

**任务**：
- `tests/unit/` — 纯逻辑（打分、质量、缺口计算、key 生成）。
- `tests/integration/` — 需真实 Neo4j（本地起容器）。
- `tests/e2e/` — daemon tick 冒烟。
**验收**：`pytest tests/unit -q` 全绿且 < 30s。

### B-4 — CI red line

**任务**：把 `tests/unit` 接入提交前检查（hook 或 CI），**失败即拦**。
**验收**：故意引入一个失败用例，提交被拦。

---

## 五、主线 C — C3-D 反馈环观测化

### 5.1 背景

批6（C3-D）已实现方向级反馈（`IS_CHILD_OF` 找同方向 → 提权缺口），
并定义了「发现引用率 = 被检索过的行为库条目数 / 343」。
但**指标尚未产出为可观测数字**，验收里"产出发现引用率"仍是 TODO。

### C-1 — 发现引用率指标落库

**任务**：
- 从行为库（`curious-agent-behaviors.md`，343 条）取 topic 集合；
- 从 `retrieval_events` 取被检索过的 `matched_topic`；
- 计算 `referenced / 343`，落 `ops.db.metrics`（或 runtime_kv）。
**产出**：`core/metrics.py` 新增 `discovery_reference_rate()`。
**验收**：调用返回 0–1 的实数；行为库/事件为空时返回 0（不报错）。

### C-2 — 反馈生效可观测

**任务**：记录每次 C3-D 提权的前后 diff——
`gap.priority` 改前/改后 + 触发它的被引用 discovery。
**产出**：`ops.db.c3d_feedback_log` 表（改前/改后/触发源/时间）。
**验收**：至少 1 例可查（对齐批6 验收："同类缺口优先级实际上升，可观测 diff"）。

### C-3 — 指标面板

**任务**：`GET /api/metrics/c3d` 返回：
`{reference_rate, boosted_gaps_recent, last_feedback_at}`。
**验收**：curl 返回非空结构；UI 可选展示（不阻塞）。

---

## 六、执行顺序与依赖

```
B-1 修包名冲突（阻塞，先做）
   │
   ├─► B-0 三分类 → B-2 fixture → B-3 分层 → B-4 CI
   │
A-0 写入点清点（只读，可并行）
   │
   ├─► A-1 批量 MERGE key
   ├─► A-2 迁移脚本规范化
   ├─► A-3 JSON fallback key
   ├─► A-4 约束自检 + health.constraints_ok
   └─► A-5 重复边巡检

C-1 引用率指标
   ├─► C-2 反馈 diff 日志
   └─► C-3 指标面板
```

| 主线 | 批 | 依赖 | 风险 |
|------|----|------|------|
| B | B-1 包名冲突 | 无（阻塞项） | 🟡 环境改动 |
| B | B-0..B-4 | B-1 | 🟢 |
| A | A-0 清点 | 无 | 🟢 只读 |
| A | A-1..A-3 写入点 | A-0 | 🟡 涉 KG 写入 |
| A | A-4/A-5 护栏 | A-1 | 🟢 |
| C | C-1..C-3 | 无 | 🟢 |

---

## 七、整体验收标准

| # | 标准 | 验证方式 |
|---|------|---------|
| 1 | **重复边零复发** | A-5 巡检跑 N 轮 tick，`count(r) == count(DISTINCT r.key)` 恒成立 |
| 2 | **写入点全覆盖** | A-0 清单中所有路径带 key；grep 无裸 MERGE 关系写入 |
| 3 | **约束自愈** | 删约束 → 重启 → 自动补回 + health 先报 false 后 true |
| 4 | **测试基线可信任** | `pytest tests/unit -q` 全绿 < 30s；CI 能拦住回归 |
| 5 | **无包名污染** | `pytest --collect-only` 零 ImportError |
| 6 | **发现引用率可算** | `discovery_reference_rate()` 返回 0–1 实数 |
| 7 | **C3-D 可观测** | `ops.db.c3d_feedback_log` ≥1 条真实提权记录 |

---

## 八、风险与纪律

| # | 风险 | 缓解 |
|---|------|------|
| R1 | A 系列改写入路径引入新 bug | 每改一处配反向验证（改前脏/改后净），同本轮 F1–F3 |
| R2 | B 系列删旧用例可能删掉"隐性规格" | 三分类先只读；删除项必须写明"测的是哪条废弃链路" |
| R3 | C 系列指标口径漂移 | 引用率分子分母定义**写死**（行为库 topic ∩ retrieval_events.matched_topic），不 LLM 臆断 |
| R4 | 双写复发（同 SSOT R4） | 禁止双写；写入点清单（A-0）即为唯一真源裁定 |

**纪律（承接 AGENTS.md + SSOT）**：
- 每个改动必须**有反向验证**（改前失效、改后生效），不接受"看起来对了"。
- 静默失败 = 最贵的失败；新增路径必须配告警（A-4/A-5 即此原则落地）。
- **可行性判断必须实测**：本轮 F1 证明"加唯一约束"不能想当然（方言只认属性级），
  后续任何"应该能/应该不行"的判断，先跑一条实测再说。

---

## 九、与 v0.3.6 的关系

```
v0.3.6：接通路（数据源唯一性 + 通路一致性 + C3-D 重定向）  ✅
   │
   ▼
v0.3.7：硬化与收口
   ├─ A 数据层防复发（把"人工清理"变成"结构上不可能脏"）
   ├─ B 测试基线重建（从归档 95 failed → 可信任干净基线）
   └─ C C3-D 观测化（从"定义了指标"→"产出了数字"）
```

**为什么是"硬化"而非"新功能"**：
v0.3.6 刚把 C2→C3→C3-D 链路接通，此刻**最该做的是让它跑得稳、可验证、
可拦回归**，而不是叠新功能。功能可以等，地基不能。

---

_本档基于 2026-10-08 v0.3.6 收尾审计 + 2026-10-09 KG 修复实测写成。_
_数据源：`core/kg/neo4j_client.py`、`core/kg/kg_repository.py`、_
_`core/kg/json_kg_repository.py`、`scripts/backfill_relation_keys.py`、_
_`legacy_tests_v026/README.md`、`docs/plan/next_move_v0.3.6*.md`、`knowledge/ops.db`。_
