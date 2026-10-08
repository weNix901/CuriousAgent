# C3-D 重定向设计 — 反馈回好奇（方向级）

> **版本**：v0.3.6-C3D-R（重定向，替换原批6 方案 B）
> **日期**：2026-10-08
> **决策者**：weNix（2026-10-08：做 C3-D 重定向）
> **前置**：SSOT 批次 + C2 修复 + C2b 通路收敛（地基已干净）
> **依据**：CA2.0 §4.3 «发现回流» 原文 + §1.3 公理

---

## 〇、一句话：为什么要重定向

> **原 C3-D 用「被动查询（R1D3 检索）」去驱动「主动探索（CA 缺口提权）」——
> 因果方向接反了，违反 CA2.0 §1.3 公理，会让系统系统性遗忘自己主动探过的方向。**

重定向后，C3-D 的作用从「**收窄探索面**」改为「**扩大消费面**」。

---

## 一、原方案的两个病（实测证据）

### 病 1：因果方向接反

原实现（`feedback_store.feedback_lookup`）：

```
被 R1D3 检索过的发现 → 找同方向缺口 → 提权 → CA 优先探索该方向
```

R1D3 的检索来自**用户当下想问什么**（被动）。
CA 的探索应来自**系统觉得该知道什么**（主动）。
两者被接成 `被动 → 主动`。

后果：**用户没问过的方向，越探索越少。**

这直接违反 CA2.0 §1.3 中已固化的公理：

> `可解性` 仅用于排序，不参与缺口价值计算。
> 理由：难探索的领域往往是最重要的未知区域。若参与价值计算，系统会系统性压制这些区域，
> **退化为"搜索引擎的复读机"**，与"知道自己不知道"的目标相悖。

原 C3-D 是同一 bug 换了面具（把"可解性"换成"被检索性"，抑制机制相同）。

### 病 2：「发现」与「引用率」口径是噪声

`discovery_reference_rate()` = `被检索的行为库条目 / 行为库总数(360)`。

但行为库 360 条的**真身**（2026-10-08 实测）：

| 项 | 实测 |
|----|------|
| `### 📌` 条目数 | 360 |
| 其中含失败/空内容 | ≥5 条（`does not contain information` 等） |
| 命名空间样例 | `mlcommons related research`、`apdex related research`、`1Introduction`、`Author Services` |
| 条目内容 | 爬虫落下的网页标题 + 一句话摘要，**非结构化发现** |

→ 用 R1D3 的真实查询去匹配这种命名空间，交集必然极低。
**"引用率 0.92%" 不是"用户没用"，是"分母根本不是发现"。**

---

## 二、重定向后的正确语义

### 2.1 CA2.0 §4.3 原文（回归）

```
缺口ID → CA探索 → discovery → 加工 → 进入 context → R1D3 可检索 → 输出变化
   ▲                                                                    │
   └──────────── 回填：该 discovery 被查询过 → 提高同类缺口优先级 ◄──────┘
```

原文说的"同类"是**已结案发现的方向**，**不是用户查询的方向**。

### 2.2 重定向后的数据流

```
【旧】被动 → 主动（错）
   用户检索方向 → 提权同方向缺口 → 探索 → ...（收窄）

【新】发现 → 消费（对）
   已结案发现（CA 自己探出来的） 
        │  用 embedding 找同方向
        ▼
   同方向中【仍是缺口】的 topic
        │
        ├─► ① 消费面扩大：告知 R1D3「你可能需要这个」（注入 context / 主动分享）
        │
        └─► ② 探索面【保持独立】：缺口优先级仍由 C2 三因子决定
              （覆盖度 × 相关性[real_seen]），C3-D 不额外提权
```

**关键变化**：C3-D **不再修改缺口优先级**。它只做「**发现 → 消费提示**」这一件事。

### 2.3 「方向」的定义（保留原验证）

用 **KG 节点 content embedding**（1024 维）算余弦相似度，阈值 `DIRECTION_THRESHOLD=0.6`。

保持原实现的 embedding 聚类（已验证有效：KD×LLM=0.607 同向；FlashAttention×知识图谱=0.443 异向）。

---

## 三、新实现结构

### 3.1 保留（已验证有效，不推倒）

| 组件 | 处置 |
|------|------|
| `resolved_topics()` | ✅ 保留 —— 已结案发现识别 |
| `direction_neighbors()` | ✅ 保留 —— embedding 方向聚类 |
| `_load_embeddings()` | ✅ 保留 —— Neo4j embedding 拉取 |
| `DIRECTION_THRESHOLD=0.6` | ✅ 保留 —— 已验证阈值 |

### 3.2 移除

| 组件 | 原因 |
|------|------|
| `feedback_lookup()` 的**提权语义** | 因果反了 —— 不再改缺口优先级 |
| `gap_calculator` 的 `feedback_lookup` 参数 | 同上，移除提权通路 |
| `discovery_reference_rate()` 的**旧分母** | 分母是噪声；改为真实发现集 |

### 3.3 新增

| 组件 | 作用 |
|------|------|
| `related_discoveries(topic)` | 给定 topic → 返回同方向已结案发现（供 R1D3 消费提示） |
| `discovery_reference_rate()` **v2** | 分母改为「KG 中 quality≥θ 且被检索过的节点」 |

---

## 四、实施批次

### C3D-R1 — 移除提权通路（因果纠正）

- `gap_calculator.rank_gaps()`：删除 `feedback_lookup` 参数与提权分支
- `gap_calculator.compute_from_store()`：删除 `with_feedback` 调用
- 保留 `feedback_store` 的方向聚类函数（供 R1D3 消费用）

**验收**：`rank_gaps()` 结果与「不接 feedback」完全一致（无提权）；
缺口优先级只由 C2 三因子决定。

### C3D-R2 — 新增消费提示接口

- `feedback_store.related_discoveries(topic, k=5)`：
  给定一个 topic（用户正在问的），返回同方向的**已结案发现**列表
- 用途：R1D3 回答时可附「我探过的相关内容」（**扩大消费面**，非收窄探索面）

**验收**：给定 `FlashAttention` → 返回与其同方向的已结案发现（若存在）。

### C3D-R3 — 修正发现引用率口径

- `discovery_reference_rate()` v2：
  - 分子 = 被检索过的**真实发现**（KG 节点 quality≥7 且出现在 retrieval_events）
  - 分母 = 真实发现总数
  - 行为库降级为辅助信号（不再作为分母）

**验收**：指标口径改变，能在文档中说明新旧差异。

---

## 五、验收标准

| # | 标准 | 验证 |
|---|------|------|
| 1 | 缺口优先级不再受检索反馈影响 | `rank_gaps` 无 feedback 分叉，数值一致 |
| 2 | 方向聚类仍有效 | `related_discoveries(FlashAttention)` 返回合理结果 |
| 3 | 消费面接口可用 | 给定 topic 能取到同方向已结案发现 |
| 4 | 引用率口径修正 | v2 指标可计算，文档说明新旧差异 |
| 5 | 公理一致 | C3-D 不再压制任何方向 |
| 6 | **已接入 R1D3（2026-10-08）** | hook + skill 真实调用，2s 预算内返回 |

---

## 五之二、R1D3 接入（C3D-R2 落地，2026-10-08）

重定向后必须接入，否则又是"建好没人用"（重演旧 C3-D 空转）。

### 接入点（两个消费方，同一端点）

| 消费方 | 文件 | 接入方式 |
|--------|------|----------|
| Hook | `openclaw-hooks/plugins/knowledge-gate/hooks/knowledge-gate/handler.ts` | `beforeAgentReplyHook` 并行查询，注入 `[相关发现]` 块 |
| Skill | `~/.openclaw/skills/knowledge-query/scripts/query.py` | `query()` 附 `related_discoveries` 到输出 |

### 新端点

```
GET /api/kg/related_discoveries/<topic>?k=3
→ {"success": true, "topic": ..., "discoveries": [{topic, similarity}]}
```

### 性能约束与解法（关键）

**问题**：端点首次实现耗时 **2.7s**（embedding 加载 806 节点 2.25s），
超过 hook/skill 的 **2s 预算** → 消费方超时拿到空。

**解法**：`feedback_store` 加进程内 **30s TTL 缓存**（resolved + 预归一化向量）：

```
首次（预热）: 2.80s
缓存命中    : 0.048s   ← 后续请求
```

不引入新真源：缓存仅加速器，失效后重算（真源仍是 Neo4j）。

### 实测验证

```
skill query.py "FlashAttention"
→ discoveries: [FlashAttention-3(0.85), FlashAttention-2(0.84), FlashAttention-3(0.83)]
```

聚类精准：查 FlashAttention → 返回 FlashAttention-2/3 论文。

---

## 六、与旧方案的差异声明

| 项 | 旧（批6 方案 B） | 新（C3D-R） |
|----|----------------|------------|
| 作用对象 | 缺口优先级（提权） | 消费提示（告知 R1D3） |
| 因果方向 | 被动→主动 ❌ | 发现→消费 ✅ |
| 是否收窄探索面 | 是 ❌ | 否 ✅ |
| 引用率分母 | 行为库 360 条（噪声） | 真实发现集 |
| 公理一致性 | 违反 §1.3 | 符合 §1.3 |

---

_本档基于 2026-10-08 全量代码核查 + 行为库实测写成。_
_相关：`docs/plan/next_move_v0.3.6.md` 批6、`CA2.0_high_level_plan.md` §4.3/§1.3。_
_更新 2026-10-08：C3D-R2 已接入 R1D3（hook + skill，含 30s 缓存）。_
