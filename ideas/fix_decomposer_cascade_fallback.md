# Fix: Decomposer 验证失败降级策略 + R1D3 澄清路由

> 文件：ideas/fix_decomposer_cascade_fallback.md
> 目标：解决 "no candidates passed provider validation" 导致的探索链断裂
> 问题发现：R1D3-researcher，2026-03-23

---

## 问题现象

```
[Decomposer] 'Enhancing LLM Reasoning' -> no candidates passed provider validation
[Decomposer] 'Streamlined Framework' -> no candidates passed provider validation
[Decomposer] 'Extending Classical Planning' -> no candidates passed provider validation
```

连续多轮都是同一个问题：LLM 生成的候选 sub-topics，没有任何 Provider 返回结果。

---

## 根因

候选验证门槛（`curiosity_decomposer.py`）：
- `provider_count >= 2`（至少 2 个 Provider 有结果）
- `total_count >= 10`（总结果数 >= 10 条）

**根因：LLM 生成的候选太窄或太抽象**。例如"Enhancing LLM Reasoning"分解出"Streamlined Framework"这类术语，搜索引擎几乎不收录。

---

## 澄清路由：Curious Agent → R1D3 → weNix

**原则**：Curious Agent 不直接通知用户，只告诉 R1D3。

```python
# curious_agent.py run_one_cycle()
except ClarificationNeeded as e:
    print(f"[Decomposer] Clarification needed for '{e.topic}': {e.reason}")
    kg.mark_topic_done(e.topic, f"Needs clarification: {e.reason}")
    return {
        "status": "clarification_needed",
        "topic": e.topic,
        "reason": e.reason,
    }
    # R1D3 通过检查 result["status"] == "clarification_needed" 获知需要澄清
    # R1D3 在对话中主动询问用户（weNix）
```

---

## 解决方案：三层降级

替换 `curious_decomposer.py` 第 63-68 行的 ClarificationNeeded：

```python
async def _cascade_fallback(self, topic: str, candidates: list[str]) -> list[dict]:
    """
    三层降级策略：
    Level 1: 扩大候选范围，重新生成更常见的 sub-topics
    Level 2: 降低门槛（1个Provider 或 total>=5）重新验证
    Level 3: 从 KG children 取候选，不验证，直接返回
    """

    # ===== Level 1: 扩大候选范围 =====
    print(f"[Decomposer] Level 1: Expanding candidate generation...")
    expanded = await self._llm_generate_candidates(topic, style="broad")
    if expanded:
        verified = await self._verify_with_providers(expanded)
        if verified:
            print(f"[Decomposer] Level 1 OK: {len(verified)} candidates")
            return verified

    # ===== Level 2: 降低门槛 =====
    print(f"[Decomposer] Level 2: Relaxing verification threshold...")
    original_threshold = self.config.get("verification_threshold", 2)
    original_min_results = self.config.get("min_total_results", 10)

    self.config["verification_threshold"] = 1
    self.config["min_total_results"] = 5

    try:
        verified = await self._verify_with_providers(candidates)
        if verified:
            print(f"[Decomposer] Level 2 OK: {len(verified)} candidates")
            return verified
    finally:
        self.config["verification_threshold"] = original_threshold
        self.config["min_total_results"] = original_min_results

    # ===== Level 3: KG children fallback =====
    print(f"[Decomposer] Level 3: Using KG children as fallback...")
    kg_children = self._get_kg_children(topic)
    if kg_children:
        return [{
            "sub_topic": c,
            "candidate": c,
            "provider_results": {},
            "total_count": 0,
            "provider_count": 0,
            "signal_strength": "kg_fallback",
            "verified": True,
            "source": "kg"
        } for c in kg_children]

    # 三层都失败 → 返回最强候选（不验证）
    best = max(candidates, key=lambda c: len(c)) if candidates else topic
    print(f"[Decomposer] Level 3 fallback: using '{best}' unverified")
    return [{
        "sub_topic": best,
        "candidate": best,
        "provider_results": {},
        "total_count": 0,
        "provider_count": 0,
        "signal_strength": "unverified",
        "verified": True,
        "source": "fallback"
    }]


async def decompose(self, topic: str) -> list[dict]:
    # ... Step 1: LLM generate candidates ...
    candidates = await self._llm_generate_candidates(topic)

    if not candidates:
        raise ClarificationNeeded(topic, reason="LLM generated no candidates")

    # Step 2: Verify with providers
    verified = await self._verify_with_providers(candidates)

    if not verified:
        # ===== 替换 ClarificationNeeded 为三层降级 =====
        print(f"[Decomposer] No candidates verified, starting cascade fallback...")
        verified = await self._cascade_fallback(topic, candidates)

        if not verified:
            raise ClarificationNeeded(
                topic=topic,
                reason="all candidates failed even with relaxed threshold"
            )

    # ... Step 3: KG augmentation ...
    enriched = self._kg_augment(topic, verified)
    return enriched
```

## Level 1 增强：生成更常见的候选

```python
async def _llm_generate_candidates(
    self, topic: str, style: str = "default"
) -> list[str]:
    """
    style: "default" | "broad"
    broad 模式：生成更常见的、被搜索引擎广泛收录的子话题
    """
    if style == "broad":
        prompt = f"""针对 "{topic}"，列出最常见的 3-5 个相关子领域。

要求：
- 只列出搜索量大的常见术语
- 不要学术化的罕见概念
- 格式：- term - 说明

示例（topic="AI Agent"）：
- agent memory - 记忆系统
- agent planning - 任务规划
- tool use - 工具使用
"""
    else:
        prompt = f"""针对 "{topic}"，识别它最常见的子领域或组成部分。

要求：
- 列出 3-7 个子话题
- 每个格式：[子话题名称] - [一句话说明]
- 优先列出技术领域相关的子话题

格式（直接输出列表，不要其他文字）：
- topic1 - 说明1
- topic2 - 说明2
- ..."""

    response = await self.llm.chat_async(prompt)
    return self._parse_candidates(response)
```

---

## 验收标准

```bash
# 测试1: 有候选通过降级
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
print(f'Subtopics: {len(result)}')
for r in result[:5]:
    print(f'  {r[\"sub_topic\"]} [{r.get(\"signal_strength\",\"?\")}]')
assert len(result) > 0, 'FAIL: no results'
print('PASS')
"

# 测试2: R1D3 收到 clarification_needed 状态
# 运行 --run，检查返回的 status 是否为 clarification_needed
```

---

## 文件改动清单

| 文件 | 改动 |
|------|------|
| `core/curiosity_decomposer.py` | 新增 `_cascade_fallback()` + `_llm_generate_candidates(..., style)` |
| `core/curiosity_decomposer.py` | `decompose()` 替换 ClarificationNeeded 为降级逻辑 |
| `curious_agent.py` | `except ClarificationNeeded` 返回状态字典，让 R1D3 感知 |
| `core/knowledge_graph.py` | 新增 `get_children(topic)` 辅助函数（Level 3 用）|
