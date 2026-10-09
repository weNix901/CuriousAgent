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

## 二、v0.3.7 四条主线（**按新顺序：D > A > B > C**）

```
主线 D：探索复活（修复 S1/S2 复发 — 实测证明发动机熄火）   ← 最高优先，直接决定"系统是否在自我进化"
主线 A：数据层防复发（输入可信 — D 的输入保障）
主线 B：测试基线重建（改动可拦 — A/D 的验证基础）
主线 C：发现消费实证（降级为 D 的验收手段，不是独立目标）
```

### 2.1 为什么重排（2026-10-09 实测依据）

前版三条主线（A/B/C）全部对齐 CA2.0 的**公理**，但**没有一条对齐 CA2.0 的核心症状 S1/S2/S3**。

**实测发现：CA2.0 的"发电"部分（C2 缺口→队列→探索→发现）根本没在转。**

| 实测事实 | 证据（2026-10-09 21:30） |
|---------|------------------------|
| Daemon 在跑但**探索空转** | `ExploreDaemon: queue empty, waiting...` 每 30s |
| **队列有 239 pending 却是"empty"** | 全部 `task_type: deep_read`，被 `exclude_task_type="deep_read"` 过滤 |
| **DeepReadDaemon 也空转** | `No TXT available for child_2_8 (pdf_path=None)` 每 30min |
| **DreamAgent 恒产 0** | `generated 0 topics in 164082ms` |
| **DreamAgent 构造错误** | `EmbeddingService.__init__() missing 1 required positional argument: 'config'` |
| C1 覆盖判定**是活的** | `/api/knowledge/check` → `coverage: known, 70%` |
| C2 缺口产出**很小** | `ops.db.gaps` 仅 7 行，多为 `unknown/0.0` |

**结论**：系统表面全绿（daemon alive / API up / hooks ready），**实际探索产出为 0**。
`queue empty` 是一句**假话**（队列有 239 条）——直接违反 CA2.0 §1.5 原则 6「失败必须可见」。

> **CA2.0 §2.2 原句**："组件存在但从未通电"。现在通电了，但**燃料进不去**（239 deep_read 堵塞）
> + **发动机故障**（DreamAgent Embedding 错误）。修完 A/B/C 而不修 D，
> 会得到一个"地基完美、管道干净、指标可读，但不发电"的系统。

### 2.2 优先级理由

- **D > A**：D 决定"系统是否在自我进化"（CA2.0 的存在意义）；A 是 D 的输入保障。
- **A > B**：A 保证 C1 四态机输入干净（否则判定全错）；B 是 A/D 的验证基础。
- **C 降级**：原 C 目标（算引用率）不推进 CA2.0，只是仪表盘美化；
  重定为"发现真的进入 R1D3 context 并被用上"（对齐 CA2.0 §八开放问题 3）。

---

## 三、主线 D — 探索复活（**最高优先**）

### 3.1 目标

让 CA2.0 的"发电链路"（C2 缺口 → 队列 → 探索 → 发现）**真正转动**，
修复实测发现的 S1/S2 复发形态。

### D-1 — `queue empty` 假话修复（**首修，违反"失败必须可见"**）

**现状**：239 条 pending 全是 `task_type: deep_read`，被 `ExploreDaemon` 显式排除；
日志却说 `queue empty`——**把"我不处理的任务"说成"队列空"**。

**任务**：
- 修正 `_tick` 日志语义：区分"无 pending" vs "有 pending 但全被排除"。
- 清点 239 条 deep_read：**判定哪些是垃圾**（`child_*` / `test trim` / `force-delete` 等测试残留），
  哪些是真实待读。
- 垃圾项：批量清理（可逆备份）。
- 真实项：确认 DeepReadDaemon 能否处理（见 D-2）。

**验收**：日志不再出现误导性 `queue empty`；清理后 pending 数反映真实待办。

**产出**：`scripts/audit_deep_read_queue.py`（只读审计）+ 清理动作。

### D-2 — DeepReadDaemon 失败路径修复

**现状**：`No TXT available for <topic> (pdf_path=None)`——每 30min 取一条 deep_read，
取不到文件就丢弃，**无限重复却无产出**。

**任务**：
- 判定 deep_read 条目何时应被标记 `failed`（而非重复尝试）。
- 加**降级路径**：无 TXT 时是否可走 web 抓取 / 或标记为不可读并退出队列。
- 失败必须带可见日志（当前是 DEBUG 级，等于无声）。

**验收**：deep_read 条目要么被处理，要么被明确标记 failed + 原因，不再静默重复。

### D-3 — DreamAgent Embedding 故障修复（**发动机故障**）

**现状**：`EmbeddingService.__init__() missing 1 required positional argument: 'config'`
→ Phase2 embedding / Phase4 LLM verification 全部失败 → **每次恒产 0 topics**。

**任务**：修 `EmbeddingService` 实例化（传 config），对齐 `repository_factory._ensure_connected()`
里的 embedding 初始化模式。

**验收**：DreamAgent 一次 tick 产出 > 0 topics（或明确"无可做梦素材"而非因构造错误）。

### D-4 — C2 缺口 → 队列 闭环实证

**现状**：`ops.db.gaps` 仅 7 行，多为 `unknown/0.0`；需确认缺口是否真喂给探索。

**任务**：
- 验证 `_enqueue_gaps()` 是否在队列"真空"时真的入队。
- 判定 gap value 全为 0.0 的根因（相关性/覆盖度因子是否缺输入）。

**验收**：对齐 CA2.0 Phase 3——**无人工植入下，队列自动出现合理任务（≥1 例）**。

### D-5 — 端到端追溯链（对齐 CA2.0 Phase 4）

**任务**：造一条可查的追溯链：
`缺口 → 队列 → 探索 → 发现（KG 新节点）→ 进入 R1D3 context → 输出变化`。

**验收**：对齐 CA2.0 Phase 4——**完整文件级追溯链 ≥ 1 例**。

---

## 四、主线 A — 数据层防复发

### 4.1 背景：为什么"清理过了"还不够

2026-10-09 修复前，KG 有 **36106 条边**，去重后应约 5027 条。
根因：Neo4j **无关系唯一约束** + 部分写入路径历史用 `CREATE`。
本轮已加约束 + 写 key，但仍有**未覆盖的写入点**需清点：

| 写入点 | 现状 | 待办 |
|--------|------|------|
| `kg_repository.add_relation` | ✅ 带 key + 约束 | 无 |
| `kg_repository.update_kg_relation(add)` | ✅ 带 key + 约束 | 无 |
| `kg_repository.py:486` `FOREACH MERGE` 批量路径 | ⚠️ **未带 key** | **A-1** |
| `scripts/migrate_state_to_neo4j.py:72,77` | ⚠️ 直接 `execute_write`（脚本已无源，state.json 已退场） | **A-2** |
| ~~`json_kg_repository.py:110`~~ | ✅ **已删除**（本轮） | 无 |
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

## 五、主线 B — 测试基线重建

### 5.1 背景

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

## 六、主线 C — 发现消费实证（**降级为 D 的验收手段**）

### 6.1 背景校正（2026-10-09 实测）

原计划假设 C3-D 反馈环"定义了指标但尚未产出数字"。实测发现**这个假设已过期**：

| 原计划假设 | 实测真相 | 证据 |
|-----------|---------|------|
| 方向级反馈 = "被检索 → 提权缺口" | ❌ **已废除**（C3D-R，2026-10-08）：因果方向接反，违反 CA2.0 §1.3 | `gap_calculator.py:364` 注释 |
| 发现引用率"尚未产出" | ❌ **已实现**：`discovery_reference_rate()` + `_v2()` 均已存在 | `feedback_store.py:132,437` |
| C3-D 未接入 R1D3 | ❌ **已接入**：hook + skill 两消费方 | `fcf4f71` |
| 需要新建 `/api/metrics/c3d` | ⚠️ 指标函数有，**无端点暴露** | grep 零命中 |

**实测运行**：
```
reference_rate_v2: {discovered_total: 814, referenced: 3, rate: 0.0037}
reference_rate_v1: {discovered_total: 347, referenced: 3, rate: 0.0086}
```
→ 说明 v1/v2 **两个口径并存**（v1 分母=行为库，v2 分母=KG quality≥7）。

### C-1 — ✅ **已存在**（仅需确认口径）

`feedback_store.discovery_reference_rate_v2()` 已产出 0–1 实数。
**待办**：
- 决定 **v1/v2 哪个是正式口径**（v2 分母更合理：KG quality≥7 才是"真发现"）。
- 若定 v2，则给 v1 加 `@deprecated` 标注 + 文档说明，避免两口径混用（违反"唯一真源"）。
**验收**：`docs` + docstring 明确唯一口径；另一口径标注废弃或删除。

### C-2 — ⚠️ **机制已废除，改为"消费面观测"**

原 C3D-R 已删除"提权 diff 日志"需求（机制本身废除）。
**改为**：观测"发现→消费"通路的实际使用——`related_discoveries` 端点被调用次数 / 返回非空次数。
**产出**：`ops.db.runtime_kv` 记 `c3d_consume_events`（或轻量计数）。
**验收**：skill/hook 调用一次 → 计数 +1（可查）。

### C-3 — 指标端点（**本主线唯一实质待办**）

**任务**：`GET /api/metrics/c3d` 返回：
```json
{"reference_rate": 0.0037, "denominator": "kg_quality_ge_7",
 "discovered_total": 814, "referenced": 3, "referenced_topics": [...]}
```
（直接包 `discovery_reference_rate_v2()`，不新造逻辑。）
**验收**：curl 返回非空结构；口径与 C-1 决定一致。

> **结论**：主线 C 原本的三批里，C-1 已存在、C-2 机制被废除，**只剩 C-3（暴露端点）
> + 口径统一**是真实待办。工作量远小于原估计。

---

## 七、执行顺序与依赖

```
主线 D（最高优先，先做）—— 探索复活
   ├─► D-1 queue empty 假话修复 + 239 deep_read 清理
   ├─► D-2 DeepReadDaemon 失败路径
   ├─► D-3 DreamAgent Embedding 修复
   ├─► D-4 C2 缺口 → 队列 实证
   └─► D-5 端到端追溯链

主线 A（D 的输入保障，与 D 部分并行）
   ├─► A-0 写入点清点（只读）
   ├─► A-1 批量 MERGE key
   ├─► A-2 迁移脚本规范化
   ├─► A-4 约束自检 + health.constraints_ok
   └─► A-5 重复边巡检

主线 B（A/D 的验证基础）
   ├─► B-0 三分类 → B-2 fixture → B-3 分层 → B-4 CI

主线 C（D 的验收手段，最后收口）
   └─► C-1 口径统一 → C-3 指标端点；C-2 消费观测
```

| 主线 | 批 | 依赖 | 风险 |
|------|----|------|------|
| **D** | D-1 假话修复 | 无（**首修**） | 🟡 涉队列清理 |
| **D** | D-2 DeepRead 失败路径 | 无 | 🟡 |
| **D** | D-3 Embedding 修复 | 无 | 🟢 |
| **D** | D-4 缺口闭环 | D-1..D-3 | 🟡 |
| **D** | D-5 追溯链 | D-4 | 🟡 |
| A | A-0 清点 | 无 | 🟢 只读 |
| A | A-1..A-2 写入点 | A-0 | 🟡 涉 KG 写入 |
| A | A-3 | ✅ 本轮已完成（删除死代码） | — |
| A | A-4/A-5 护栏 | A-1 | 🟢 |
| B | B-1 包名冲突 | 无（✅ 本轮已完成） | 🟢 |
| B | B-0..B-4 | B-1 | 🟢 |
| C | C-1/C-3 口径+端点 | D 完成后 | 🟢 |
| C | C-2 消费观测 | 无 | 🟢 |

---

## 八、整体验收标准

| # | 标准 | 验证方式 | 主线 |
|---|------|---------|------|
| 1 | **queue 日志不再说假话** | `queue empty` 仅在真空时出现；有被排除项时显式报告 | D |
| 2 | **探索真在产出** | daemon 一轮 tick 后有 KG 新节点 / DreamAgent 产 >0 | D |
| 3 | **缺口自动入队** | 无人工植入下队列自动出现合理任务（≥1 例） | D |
| 4 | **端到端追溯链** | 缺口→队列→探索→发现→context→输出 完整 ≥1 例 | D |
| 5 | **重复边零复发** | A-5 巡检跑 N 轮 tick，`count(r) == count(DISTINCT r.key)` 恒成立 | A |
| 6 | **写入点全覆盖** | A-0 清单中所有路径带 key；grep 无裸 MERGE 关系写入 | A |
| 7 | **约束自愈** | 删约束 → 重启 → 自动补回 + health 先报 false 后 true | A |
| 8 | **测试基线可信任** | `pytest tests/unit -q` 全绿 < 30s；CI 能拦住回归 | B |
| 9 | **无包名污染** | `pytest --collect-only` 零 ImportError | B |
| 10 | **发现引用率口径唯一** | 只剩一个正式口径（v2），另一个废弃/删除 | C |
| 11 | **C3-D 可观测** | `/api/metrics/c3d` 返回非空结构；消费事件可计数 | C |

---

## 九、风险与纪律

| # | 风险 | 缓解 |
|---|------|------|
| R1 | D-1 清理 239 deep_read 可能误删真实待读 | 先只读审计（`audit_deep_read_queue.py`）+ 可逆备份 |
| R2 | D-3 修 Embedding 后 DreamAgent 产出仍为 0 | 先只读验证构造，再看 tick 输出；区分"无素材"vs"构造错" |
| R3 | A 系列改写入路径引入新 bug | 每改一处配反向验证（改前脏/改后净），同本轮 F1–F3 |
| R4 | B 系列删旧用例可能删掉"隐性规格" | 三分类先只读；删除项必须写明"测的是哪条废弃链路" |
| R5 | C 系列指标口径漂移 | 引用率分子分母定义**写死**（v2: 分子=KG quality≥7 ∩ retrieval_events，分母=KG quality≥7）；v1 标废弃 |

**纪律（承接 AGENTS.md + SSOT）**：
- 每个改动必须**有反向验证**（改前失效、改后生效），不接受"看起来对了"。
- 静默失败 = 最贵的失败；**D-1 是本轮首修，因为 `queue empty` 正是一句掩盖 239 条积压的假话**。
- **可行性判断必须实测**：本轮 F1 证明"加唯一约束"不能想当然（方言只认属性级）；
  D-1..D-3 同样是**实测发现的运行故障**，不是推测。

---

## 十、与 v0.3.6 的关系

```
v0.3.6：接通路（数据源唯一性 + 通路一致性 + C3-D 重定向）  ✅
   │
   ▼
v0.3.7：地基硬化 + 发动机复活
   ├─ D 探索复活（S1/S2 复发修复 — 实测证明发动机熄火）  ← 最高优先
   ├─ A 数据层防复发（把"人工清理"变成"结构上不可能脏"）
   ├─ B 测试基线重建（从归档 95 failed → 可信任干净基线）
   └─ C 发现消费实证（从"算指标"→"证用上了"）
```

**为什么新增主线 D、且排最前**：
v0.3.6 把 C2→C3→C3-D 链路接通后，实测发现**发动机仍熄火**——
239 条 pending 却报 `queue empty`、DreamAgent 恒产 0、DeepReadDaemon 空转。
A/B/C 三条都是"把地基修结实"，但**地基之上不发电**。
不先修 D，得到的是一个"地基完美、管道干净、指标可读，但不自我进化"的系统。

---

## 十一、本轮已提前完成的项（更新 2026-10-09 晚）

| 原计划项 | 状态 | 说明 |
|---------|------|------|
| B-1 包名冲突 | ✅ **已完成** | conftest.py + tests/__init__.py；1106 tests 零 ImportError |
| A-3 JSON 后端 | ✅ **已完成** | 直接删除死代码（457 行），非"改 key" |
| F4 health 响亮失败 | ✅ **已完成** | ERROR + 503 + 启动门禁 |
| C-1 引用率指标 | ⚠️ **已存在** | `discovery_reference_rate_v2()` 已在跑，仅需定口径 |

**剩余真实待办（按新顺序）**：
1. **主线 D**（最高优先）：D-1 queue 假话 / D-2 DeepRead 失败路径 / D-3 Embedding / D-4 缺口闭环 / D-5 追溯链
2. **主线 A**：A-0/A-1/A-2/A-4/A-5
3. **主线 B**：B-0/B-2/B-3/B-4
4. **主线 C**（收口）：C-1 口径统一 / C-2 / C-3

---

_本档基于 2026-10-08 v0.3.6 收尾审计 + 2026-10-09 KG 修复实测写成。_
_数据源：`core/kg/neo4j_client.py`、`core/kg/kg_repository.py`、_
_`core/api/feedback_store.py`、`core/daemon/explore_daemon.py`、_
_`scripts/backfill_relation_keys.py`、`legacy_tests_v026/README.md`、_
_`docs/plan/next_move_v0.3.6*.md`、`knowledge/ops.db`、`logs/agent.log`。_

_**2026-10-09 晚校准**：本档经历两次按实测重写：_
_- 第一次：主线 C 原假设"C3-D 尚未观测化"已过期（机制已废除、函数已实现、已接入 R1D3）；_
_- 第二次：新增主线 D——实测发现 C2→队列→探索 发电链路熄火，_ 
_  且三条原主线**均未覆盖 CA2.0 核心症状 S1/S2**，故重排为 D > A > B > C。_
