# Buglist v0.2.8 — 知识断言评估未激活

> 核对时间：2026-04-08 04:00（Asia/Shanghai）
> 核对人：R1D3-researcher
> 状态：P0 未修复

---

## 问题概览

v0.2.8 的代码文件已实现，但 **wiring 断路 + 冷启动未执行**，断言评估通道从未被激活，系统实际仍运行在 legacy QualityV2 上。

---

## Bug #1 — Wiring 断路：断言评估器从未初始化（P0）

**根因**：`QualityV2Assessor.__init__` 需要 `embedding_service` + `assertion_index` 两个参数才初始化 `assertion_evaluator`，但三个调用点全部只传了 `llm`。

**影响**：断言评估通道永远不激活，v0.2.8 Solution C 完全失效。

### 调用点诊断

#### 1. `core/async_explorer.py:28`

```python
# 当前代码
_quality_assessor_instance = QualityV2Assessor(llm)
```

```python
# 应该改为
from core.embedding_service import EmbeddingService
from core.assertion_index import AssertionIndex
embedding_service = EmbeddingService()
assertion_index = AssertionIndex()
_quality_assessor_instance = QualityV2Assessor(
    llm,
    embedding_service=embedding_service,
    assertion_index=assertion_index,
    knowledge_graph=kg_module
)
```

**同时**：第 44 行调用时也要确保 `kg_module` 传入：
```python
quality = quality_assessor.assess_quality(
    topic=topic,
    findings=findings_dict,
    knowledge_graph=kg_module  # ← 确认这里传入的是 kg_module，不是 None
)
```

#### 2. `core/spider_agent.py:162`

```python
# 当前代码
quality_assessor = QualityV2Assessor(llm)
```

需要补充 embedding_service、assertion_index、knowledge_graph。

#### 3. `core/explorer.py:153`

```python
# 当前代码
quality_assessor = QualityV2Assessor(llm_client)
```

同样需要补充三个参数。

---

## Bug #2 — 冷启动未执行（P1）

**根因**：assertions.db 为空（`SELECT COUNT(*) → 0`），FAISS 索引无数据。

**影响**：
- `_is_assertion_new()` 第一次总是返回 `True`（索引空，无相似度可查）
- 即使 wiring 修复，第一个断言会被误判为"新知识"
- 随着索引增长，去重能力才逐渐正常，但冷启动阶段质量不可信

### 修复方案

写一个冷启动脚本 `scripts/backfill_assertions.py`：

```python
"""
对 KG 里所有已有 topics 生成断言并建立索引。
"""
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.kg_graph import get_state
from core.assertion_generator import AssertionGenerator
from core.assertion_index import AssertionIndex
from core.embedding_service import EmbeddingService
from core.llm_client import LLMClient

def backfill():
    kg_state = get_state()
    topics = kg_state.get("knowledge", {}).get("topics", {})
    
    llm = LLMClient()
    generator = AssertionGenerator(llm)
    embedding_service = EmbeddingService()
    index = AssertionIndex()
    
    for topic_name, topic_data in topics.items():
        findings = {"summary": topic_data.get("summary", "")}
        assertions = generator.generate(topic_name, findings, num_assertions=3)
        
        for assertion in assertions:
            emb = embedding_service.embed(assertion)[0]
            index.insert(assertion, emb, source_topic=topic_name)
    
    print(f"Backfill complete: {index.get_stats()}")

if __name__ == "__main__":
    backfill()
```

---

## Bug #3 — Legacy 信息增益判断不对比 prev_summary（P2）

**根因**：`_calculate_legacy_quality` 调用 `_assess_information_gain(topic, new_summary)`，只传新 summary，没有与 `prev_summary` 对比。

**影响**：任何写得好的 summary（即使与之前重复）都能得高分，无法识别"实质无新内容"的情况。

### 当前代码（explorer.py）

```python
# explorer.py:158
quality = quality_assessor.assess_quality(topic, quality_findings, kg)
```

### 问题定位

`quality_v2.py` 的 `_assess_information_gain` 签名：

```python
def _assess_information_gain(self, topic: str, new_summary: str) -> float:
    # 只看 new_summary 本身，没有 prev_summary 对比
```

**正确做法**：信息增益应该是 `new_summary vs prev_summary`，而不是 `new_summary 本身`。

---

## Bug #4 — async_explorer.py 调用时传入 kg_module 为 None（已修复）

在 Bug #1 的诊断过程中发现，G4-Fix 已确保传入 `kg_module`：

```python
quality = quality_assessor.assess_quality(
    topic=topic,
    findings=findings_dict,
    knowledge_graph=kg_module  # ✅ 已修复
)
```

---

## 文件清单

| 文件 | 行数 | 状态 |
|------|------|------|
| `core/assertion_generator.py` | 137 | ✅ 存在 |
| `core/assertion_index.py` | 149 | ✅ 存在（FAISS 索引） |
| `core/knowledge_assertion_evaluator.py` | 109 | ✅ 存在 |
| `core/quality_v2.py` | 255 | ✅ 存在（双通道聚合） |
| `shared_knowledge/assertion_index/assertions.db` | — | ⚠️ 空 |

---

## 修复优先级

| 优先级 | Bug | 修复方式 |
|--------|-----|---------|
| **P0** | Bug #1（Wiring） | 修改三个调用点的 `QualityV2Assessor` 初始化，补充参数 |
| **P1** | Bug #2（冷启动） | 写 `scripts/backfill_assertions.py` 并执行 |
| **P2** | Bug #3（Legacy bug） | 修改 `_assess_information_gain` 对比 prev vs new |

---

## 验收标准

1. `QualityV2Assessor.__init__` 能成功初始化 `assertion_evaluator`（日志出现 `[QualityV2] Assertion quality: X.X`）
2. `assertions.db` 有 > 0 条记录
3. 同一 topic 重复探索时，第二个的 assertion quality 应显著低于第一个（去重生效）
