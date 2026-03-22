# Curious Agent v0.2.3 — Phase 2：质量评估升级 & 元认知驱动

> **Phase 2 目标**：升级探索质量评估、引入能力追踪、将探索过程变为 Monitor-Generate-Verify 闭环
> 前置依赖：Phase 1（Agent-Behavior-Writer）| 设计者：weNix + R1D3-researcher
> 文档版本：v1.1 | 2026-03-21
>
> **v1.1 更新**：合并完整系统数据流、四个出口、Skill 生成、Reward 反馈等全部原始内容

---

## 1. 概述

### 与 Phase 1 的关系

| Phase | 目标 | 前置依赖 |
|-------|------|---------|
| Phase 1 | 打通行为闭环入口 | 依赖 v0.2.2 |
| **Phase 2（本文）** | 升级质量评估 + 元认知驱动探索 | 依赖 Phase 1 |

Phase 2 在 Phase 1 跑通后推进，目标是让 Curious Agent 的**探索决策质量更高**，探索过程有**自我纠错能力**。

### 四个核心任务

1. **Quality v2** — 信息增益版质量评估（替代关键词重叠率）
2. **CompetenceTracker** — 能力追踪器，追踪"我对什么领域不够好"
3. **select_next_v2** — 能力感知调度，优先探索能力缺口大的领域
4. **ThreePhaseExplorer** — Monitor-Generate-Verify 三阶段探索循环

---

## 2. 理论背景

### 2.1 当前 Quality 评估的问题

v0.2.2 的 quality 评估基于关键词重叠率：

```python
new_keywords = [k for k in current_keywords if k not in known_keywords]
new_discovery_rate = len(new_keywords) / max(len(current_keywords), 1)
```

**问题**：
- "metacognition" 和 "metacognitive monitoring" 词形不同但语义相近，被错误计为新发现
- 发现出现 1 次和 10 次没有区别
- 没有评估**信息密度**（一句话 vs 一篇论文的发现）

### 2.2 ICM 原版方法的缺失

ICM（Intrinsic Curiosity Module）的核心是**预测误差 = 内在奖励**：

```
内在动机 = f(预测误差)
预测误差 = || φ(s_t) + f(φ(s_t), a_t) - φ(s_{t+1}) ||
```

当前实现只做了"探索质量记录"，没有真正利用"预测误差"来驱动探索。

### 2.3 MUSE 的能力感知机制

MUSE 的核心贡献：Agent 需要知道"自己在哪些事情上做得好/差"，探索应该由**能力缺口**驱动，而非队列优先级。

```
探索触发 = f(能力置信度)
能力置信度低 → 探索价值高
```

---

## 3. Task 1：Quality v2（信息增益版评估）

### 3.1 三维度信息增益

```python
def assess_exploration_quality_v2(topic: str, findings: dict, knowledge_graph) -> float:
    """
    三个维度的信息增益评估：
    
    1. 语义新鲜度 (Semantic Novelty)
       - 用 LLM 评估当前理解 vs 探索发现的语义重叠度
       - 相似度 < 0.7 → 高新鲜度
    
    2. 置信度变化 (Confidence Delta)
       - 探索前 LLM 自评置信度 vs 探索后置信度
       - 差值越大 = 信息增益越大
    
    3. 图谱结构变化 (Graph Topology Change)
       - 探索后该话题在图谱中的邻居数变化
       - 建立了多少新连接 = 知识整合程度
    """
    
    # === Semantic Novelty ===
    prev_summary = knowledge_graph.get_topic_summary(topic) or ""
    new_summary = findings.get("summary", "")
    
    if prev_summary and new_summary:
        # 用 LLM 评估语义相似度
        similarity = llm.assess_similarity(prev_summary, new_summary)
        semantic_novelty = 1 - similarity  # 越不相似=越新鲜
    else:
        semantic_novelty = 1.0  # 冷启动，默认满分
    
    # === Confidence Delta ===
    prev_confidence = knowledge_graph.get_topic_confidence(topic) or 0.5
    post_confidence = llm.assess_confidence(new_summary)
    confidence_delta = max(0, post_confidence - prev_confidence)
    
    # === Graph Topology Change ===
    prev_neighbors = knowledge_graph.get_neighbor_count(topic)
    post_neighbors = knowledge_graph.get_neighbor_count(topic)  # 探索后更新
    graph_delta = min(1.0, (post_neighbors - prev_neighbors) / 5)  # 最多 5 个新邻居满分
    
    # 综合评分
    quality = (
        semantic_novelty * 0.40 +
        confidence_delta * 0.30 +
        graph_delta * 0.30
    ) * 10
    
    return round(quality, 1)
```

### 3.2 LLM 辅助方法

```python
def llm.assess_similarity(text1: str, text2: str) -> float:
    """用 LLM 评估两个文本的语义相似度（0-1）"""
    prompt = f"""评估以下两段文本的语义相似度（0.0-1.0，1.0=完全相同）：

文本1：{text1[:300]}
文本2：{text2[:300]}

只返回一个数字，0.0-1.0 之间。"""
    response = llm.chat(prompt)
    numbers = re.findall(r'0?\.\d+', response)
    return float(numbers[0]) if numbers else 0.5

def llm.assess_confidence(text: str) -> float:
    """用 LLM 评估对文本主题的理解置信度（0-1）"""
    prompt = f"""评估你对以下主题的理解置信度（0.0-1.0）：

{text[:500]}

考虑：
- 你能清晰解释核心概念吗？
- 你能举出具体例子吗？
- 你能指出潜在的限制或争议吗？

返回 0.0-1.0 的数字。"""
    response = llm.chat(prompt)
    numbers = re.findall(r'0?\.\d+', response)
    return float(numbers[0]) if numbers else 0.5
```

### 3.3 降级方案

如果 LLM 不可用（超时/失败），降级到统计方法：

```python
def fallback_quality_assessment(findings: dict, knowledge_graph) -> float:
    """降级方案：基于统计的特征评估"""
    summary_len = len(findings.get("summary", ""))
    sources_count = len(findings.get("sources", []))
    papers_count = len(findings.get("papers", []))
    
    score = min(10, summary_len / 200 + sources_count * 1.5 + papers_count * 2)
    return max(0, min(10, score))
```

---

## 4. Task 2：CompetenceTracker（能力追踪器）

### 4.1 核心概念

追踪 Curious Agent 在各领域的探索能力置信度。核心问题：

> "我对这个话题的理解，能让我做出好的决策吗？"

能力状态：

```python
# 存储在 state.json 中
competence_state = {
    "topic_name": {
        "confidence": 0.7,       # 0.0-1.0，置信度
        "level": "competent",    # novice / competent / expert
        "explore_count": 3,      # 探索次数
        "quality_history": [7.5, 8.0, 7.8],  # 质量历史
        "last_updated": "2026-03-21T12:00:00Z"
    }
}
```

### 4.2 实现

文件：`/root/dev/curious-agent/core/competence_tracker.py`

```python
# core/competence_tracker.py

"""
CompetenceTracker — 能力追踪器
追踪 Curious Agent 在各领域的探索能力置信度
基于 MUSE 框架的 Competence Awareness 机制
"""

from typing import Optional
from core import knowledge_graph as kg


class CompetenceTracker:
    """
    追踪 Agent 在各话题上的探索能力
    能力评估用于驱动探索优先级
    """
    
    # 能力等级阈值
    LEVEL_NOVICE = 0.3
    LEVEL_COMPETENT = 0.6
    LEVEL_EXPERT = 0.85
    
    def __init__(self):
        self.kg = kg
    
    def assess_competence(self, topic: str) -> dict:
        """
        评估 Agent 在特定话题上的能力
        
        Returns:
            {
                "score": float,          # 0.0-1.0 综合评分
                "level": str,            # novice / competent / expert
                "confidence": float,     # 基础置信度
                "explore_count": int,
                "quality_trend": float,  # 质量趋势（正=上升）
                "reason": str
            }
        """
        topic_data = self.kg.get_topic(topic) or {}
        history = self.kg.get_topic_history(topic)
        
        # 基础置信度
        confidence = topic_data.get("confidence", 0.5)
        
        # 探索次数
        explore_count = len(history)
        
        # 质量趋势（最近 3 次的线性回归斜率）
        quality_trend = self._compute_quality_trend(history)
        
        # 综合评分
        score = (
            confidence * 0.40 +
            min(1.0, explore_count / 5) * 0.20 +
            (quality_trend + 1) / 2 * 0.20 +  # 趋势归一化到 0-1
            confidence * 0.20  # 自己对自己的评估权重
        )
        
        return {
            "score": round(score, 2),
            "level": self._score_to_level(score),
            "confidence": confidence,
            "explore_count": explore_count,
            "quality_trend": round(quality_trend, 2),
            "reason": f"置信度={confidence:.2f}, 探索={explore_count}次, 趋势={quality_trend:+.2f}"
        }
    
    def should_explore_due_to_low_competence(self, topic: str) -> tuple[bool, str]:
        """
        核心判断：能力置信度低时触发探索
        这让探索由"能力缺口"驱动，而非队列优先级
        """
        competence = self.assess_competence(topic)
        
        if competence["level"] == "novice":
            return True, f"能力等级={competence['level']}，需要探索"
        
        if competence["level"] == "competent" and competence["quality_trend"] < -0.5:
            return True, f"能力趋势下降（{competence['quality_trend']:.2f}），需要刷新"
        
        return False, f"能力充足（{competence['level']}），暂不探索"
    
    def update_competence(self, topic: str, quality: float):
        """
        探索完成后更新能力记录
        使用指数移动平均更新置信度
        """
        state = self.kg.get_state()
        current = state.get("competence_state", {}).get(topic, {})
        
        prev_confidence = current.get("confidence", 0.5)
        # EMA 更新：旧值权重 0.7，新值权重 0.3
        new_confidence = 0.7 * prev_confidence + 0.3 * (quality / 10.0)
        
        # 更新质量历史（保留最近 5 次）
        quality_history = current.get("quality_history", [])
        quality_history.append(quality)
        quality_history = quality_history[-5:]
        
        if "competence_state" not in state:
            state["competence_state"] = {}
        
        state["competence_state"][topic] = {
            "confidence": round(new_confidence, 3),
            "quality_history": quality_history,
            "explore_count": current.get("explore_count", 0) + 1,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        self.kg._save_state(state)
    
    def _compute_quality_trend(self, history: list) -> float:
        """
        计算质量趋势
        返回斜率：正=上升，负=下降，0=平稳
        """
        if len(history) < 2:
            return 0.0
        
        qualities = [h.get("quality", 5.0) for h in history[-5:]]
        n = len(qualities)
        
        # 简单线性回归斜率
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(qualities) / n
        
        numerator = sum((x[i] - x_mean) * (qualities[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        # 归一化到 -1 到 +1（假设斜率在 -2 到 +2 之间合理）
        return max(-1.0, min(1.0, slope / 2.0))
    
    def _score_to_level(self, score: float) -> str:
        if score < self.LEVEL_NOVICE:
            return "novice"
        elif score < self.LEVEL_COMPETENT:
            return "competent"
        elif score < self.LEVEL_EXPERT:
            return "proficient"
        else:
            return "expert"
```

---

## 5. Task 3：select_next_v2（能力感知调度）

### 5.1 能力感知的选择逻辑

替换 `CuriosityEngine.select_next()`：

```python
def select_next_v2(self) -> Optional[dict]:
    """
    能力感知的选择逻辑：
    
    1. 过滤：剔除能力已充足的领域（避免重复探索）
    2. 优先级：低能力 + 高重要性 = 优先探索
    3. 动态调整：根据 competence 调整 alpha（能力低→更依赖人工信号）
    """
    candidates = self.kg.list_pending()
    if not candidates:
        return None
    
    scored = []
    for item in candidates:
        topic = item["topic"]
        competence = self.competence_tracker.assess_competence(topic)
        
        # 能力已充足的跳过
        if competence["level"] == "expert" and item.get("status") == "done":
            continue
        
        # 探索价值 = 话题分数 × (1 - 能力分数) × 重要性
        # 能力越低、话题越重要 → 探索价值越高
        exploration_value = (
            item.get("score", 5.0) *
            (1 - competence["score"]) *
            item.get("relevance", 5.0) / 10.0
        )
        
        # 动态 alpha：能力低时更依赖人工指导
        if competence["score"] < 0.3:
            dynamic_alpha = 0.7  # 偏人工
        elif competence["score"] > 0.6:
            dynamic_alpha = 0.3  # 偏自主
        else:
            dynamic_alpha = 0.5  # 平衡
        
        scored.append({
            **item,
            "exploration_value": round(exploration_value, 2),
            "competence": competence,
            "dynamic_alpha": dynamic_alpha
        })
    
    # 按探索价值排序
    scored.sort(key=lambda x: x["exploration_value"], reverse=True)
    return scored[0] if scored else None
```

### 5.2 修改 CuriosityEngine

在 `CuriosityEngine.__init__` 中初始化 CompetenceTracker：

```python
from core.competence_tracker import CompetenceTracker

class CuriosityEngine:
    def __init__(self, config=None):
        self.state = kg.get_state()
        self.config = config or {}
        self.competence_tracker = CompetenceTracker()  # 新增
        # ... 其他初始化
```

---

## 6. Task 4：marginal_return_v2（边际递减曲线）

### 6.1 当前问题

```python
# 当前：线性差值
marginal = current_quality - avg_previous
```

问题：不知道递减速度，无法判断"还值得继续吗"。

### 6.2 指数衰减模型

```python
def compute_marginal_return_v2(topic: str, quality_history: list, current_quality: float) -> float:
    """
    用指数衰减建模边际递减：
    
    模型：value_n = base * decay^(n-1)
    
    如果当前 quality 超过预测曲线 → 高价值（超预期）
    如果当前 quality 低于预测曲线 → 低价值（边际递减加速）
    """
    import math
    
    if len(quality_history) < 2:
        return 1.0  # 首次探索，无法比较
    
    # 用已有数据拟合衰减曲线
    # y = base * decay^x
    # log(y) = log(base) + x * log(decay)
    
    try:
        n = len(quality_history)
        x = list(range(1, n + 1))
        log_y = [math.log(max(q, 0.1)) for q in quality_history]
        
        # 线性回归求斜率
        x_mean = sum(x) / n
        y_mean = sum(log_y) / n
        
        num = sum((x[i] - x_mean) * (log_y[i] - y_mean) for i in range(n))
        den = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if den == 0:
            decay_rate = 0.8
        else:
            slope = num / den
            decay_rate = math.exp(slope)
            decay_rate = max(0.5, min(0.95, decay_rate))  # 限制范围
    except:
        decay_rate = 0.8  # 默认衰减率
    
    # 预测第 n+1 次的质量
    predicted_next = quality_history[-1] * decay_rate
    
    # 实际 vs 预测 = 超额回报
    if predicted_next > 0:
        marginal_return = (current_quality - predicted_next) / predicted_next
    else:
        marginal_return = 1.0
    
    return round(marginal_return, 2)  # 正数=超预期，负数=低于预期
```

---

## 7. Task 5：ThreePhaseExplorer（Monitor-Generate-Verify）

### 7.1 架构

将探索过程从线性流程改为三阶段循环：

```
Phase 1: Monitor
  → 评估当前理解状态，识别知识缺口

Phase 2: Generate
  → 根据缺口制定探索计划

Phase 3: Verify
  → 执行计划并验证缺口是否填补
```

### 7.2 实现

文件：`/root/dev/curious-agent/core/three_phase_explorer.py`

```python
# core/three_phase_explorer.py

"""
ThreePhaseExplorer — Monitor-Generate-Verify 探索循环
基于 Flavell's Metacognitive Framework (arXiv:2510.16374)
"""

from typing import Optional
from core import knowledge_graph as kg


class ThreePhaseExplorer:
    """
    三阶段探索循环：
    
    1. Monitor：评估当前理解状态，识别知识缺口
    2. Generate：根据缺口制定探索计划
    3. Verify：执行计划并验证缺口是否填补
    """
    
    def __init__(self, explorer, monitor, llm_client):
        self.explorer = explorer      # 原有 Explorer 实例
        self.monitor = monitor        # MetaCognitiveMonitor 实例
        self.llm = llm_client
    
    def explore(self, curiosity_item: dict) -> dict:
        """
        执行三阶段探索
        """
        topic = curiosity_item["topic"]
        depth = curiosity_item.get("depth", "medium")
        
        # ===== Phase 1: Monitor =====
        monitor_result = self._phase1_monitor(topic)
        if monitor_result.get("already_known"):
            return {
                "status": "already_known",
                "confidence": monitor_result["confidence"],
                "reason": monitor_result.get("reason", "")
            }
        
        knowledge_gaps = monitor_result.get("knowledge_gaps", [])
        
        # ===== Phase 2: Generate =====
        exploration_plan = self._phase2_generate(
            topic, knowledge_gaps, depth
        )
        
        # ===== Phase 3: Verify =====
        findings = self._phase3_execute(topic, exploration_plan)
        verification_result = self._verify_knowledge_gaps(
            knowledge_gaps, findings
        )
        
        if verification_result["score"] < 0.3:
            # 缺口未填补，触发二次探索（用不同策略）
            findings = self._explore_with_alternative_approach(
                topic, knowledge_gaps
            )
            verification_result = self._verify_knowledge_gaps(
                knowledge_gaps, findings
            )
        
        return {
            "status": "success",
            "findings": findings,
            "verification_score": verification_result["score"],
            "gaps_filled": verification_result["gaps_filled"],
            "plan_used": exploration_plan,
            "knowledge_gaps": knowledge_gaps
        }
    
    def _phase1_monitor(self, topic: str) -> dict:
        """
        Phase 1: Monitor
        评估当前理解状态，识别知识缺口
        """
        # 评估当前置信度
        confidence = self.monitor._compute_user_relevance(topic)
        
        if confidence > 0.8:
            return {
                "already_known": True,
                "confidence": confidence,
                "reason": f"置信度 {confidence:.2f} > 0.8，知识充足"
            }
        
        # 识别知识缺口
        knowledge_gaps = self._identify_knowledge_gaps(topic)
        
        return {
            "already_known": False,
            "confidence": confidence,
            "knowledge_gaps": knowledge_gaps
        }
    
    def _identify_knowledge_gaps(self, topic: str) -> list:
        """
        用 LLM 识别该话题的知识缺口
        """
        prompt = f"""分析"{topic}"这个话题，识别当前知识图谱中可能的知识缺口。

考虑以下维度：
1. 技术定义是否清晰？（no_technical_definition）
2. 是否有实证结果/benchmark数据？（no_empirical_results）
3. 是否有实际应用案例？（no_applications）
4. 与其他概念的关系是否清晰？（no_relations）
5. 优缺点/局限性是否明确？（no_limitations）

返回 JSON 格式：
{{
    "gaps": [
        {{"type": "no_empirical_results", "description": "缺少定量评估数据", "priority": 0.8}},
        ...
    ]
}}"""
        try:
            response = self.llm.chat(prompt)
            import json
            result = json.loads(response)
            return result.get("gaps", [])
        except:
            return [{"type": "general", "description": "需要更多信息", "priority": 0.5}]
    
    def _phase2_generate(self, topic: str, knowledge_gaps: list, depth: str) -> list:
        """
        Phase 2: Generate
        根据缺口制定探索计划
        """
        plans = []
        for gap in knowledge_gaps:
            gap_type = gap.get("type", "general")
            priority = gap.get("priority", 0.5)
            
            if gap_type == "no_technical_definition":
                plans.append({
                    "action": "find_paper",
                    "target": "technical_implementation",
                    "priority": priority,
                    "depth": "deep" if priority > 0.7 else "medium"
                })
            elif gap_type == "no_empirical_results":
                plans.append({
                    "action": "find_benchmark",
                    "target": "quantitative_evaluation",
                    "priority": priority,
                    "depth": "deep"
                })
            elif gap_type == "no_applications":
                plans.append({
                    "action": "find_usecase",
                    "target": "practical_applications",
                    "priority": priority,
                    "depth": "medium"
                })
            elif gap_type == "no_limitations":
                plans.append({
                    "action": "find_critique",
                    "target": "limitations_and_drawbacks",
                    "priority": priority,
                    "depth": "medium"
                })
            else:
                plans.append({
                    "action": "general_explore",
                    "target": "overview",
                    "priority": priority,
                    "depth": depth
                })
        
        # 按优先级排序
        plans.sort(key=lambda x: x["priority"], reverse=True)
        return plans
    
    def _phase3_execute(self, topic: str, exploration_plan: list) -> dict:
        """
        Phase 3: Execute
        执行探索计划，收集发现
        """
        # 用原有 Explorer 执行
        curiosity_item = {
            "topic": topic,
            "depth": exploration_plan[0].get("depth", "medium") if exploration_plan else "medium"
        }
        
        result = self.explorer.explore(curiosity_item)
        return result
    
    def _verify_knowledge_gaps(self, knowledge_gaps: list, findings: dict) -> dict:
        """
        验证知识缺口是否被填补
        """
        summary = findings.get("summary", "")
        
        if not knowledge_gaps or not summary:
            return {"score": 0.5, "gaps_filled": []}
        
        # 用 LLM 评估缺口填补情况
        prompt = f"""给定以下知识缺口和探索发现，评估每个缺口是否被填补。

知识缺口：
{chr(10).join([f"- {g.get('type')}: {g.get('description', '')}" for g in knowledge_gaps])}

探索发现摘要：
{summary[:500]}

对每个缺口返回是否填补（yes/no），并给出简要理由。"""
        
        try:
            response = self.llm.chat(prompt)
            # 简单解析（实际应用中需要更 robust 的解析）
            gaps_filled = []
            score = 0.0
            
            for gap in knowledge_gaps:
                gap_type = gap.get("type", "")
                if gap_type.lower() in response.lower():
                    gaps_filled.append(gap_type)
                    score += 1.0
            
            if knowledge_gaps:
                score = score / len(knowledge_gaps)
            
            return {"score": score, "gaps_filled": gaps_filled}
        except:
            return {"score": 0.5, "gaps_filled": []}
    
    def _explore_with_alternative_approach(self, topic: str, knowledge_gaps: list) -> dict:
        """
        用替代策略二次探索（当第一次验证分数 < 0.3 时）
        """
        # 换用不同的探索深度和来源
        curiosity_item = {
            "topic": topic,
            "depth": "deep"  # 强制深度探索
        }
        return self.explorer.explore(curiosity_item)
```

---

## 8. 实施检查清单

### Task 1: Quality v2
- [ ] 修改 `MetaCognitiveMonitor.assess_exploration_quality`
- [ ] 实现 `llm.assess_similarity` 和 `llm.assess_confidence`
- [ ] 实现降级方案（LLM 不可用时）
- [ ] 验证：新旧评分在样本上有合理差异

### Task 2: CompetenceTracker
- [ ] 创建 `core/competence_tracker.py`
- [ ] 实现 `assess_competence`
- [ ] 实现 `update_competence`
- [ ] 实现 `_compute_quality_trend`
- [ ] 修改 state.json 结构，新增 `competence_state`

### Task 3: select_next_v2
- [ ] 在 `CuriosityEngine.__init__` 中初始化 CompetenceTracker
- [ ] 实现 `select_next_v2`
- [ ] 修改 `run_one_cycle` 使用 select_next_v2
- [ ] 验证：能力低的 topic 优先级确实更高

### Task 4: marginal_return_v2
- [ ] 修改 `MetaCognitiveMonitor.compute_marginal_return`
- [ ] 实现指数衰减拟合
- [ ] 验证：边际回报在多次探索后递减

### Task 5: ThreePhaseExplorer
- [ ] 创建 `core/three_phase_explorer.py`
- [ ] 实现 `_phase1_monitor`
- [ ] 实现 `_phase2_generate`
- [ ] 实现 `_verify_knowledge_gaps`
- [ ] 在 `curious_agent.py` 中集成（可选，作为 Phase 2 的高级特性）

---

## 9. 技术指标

| 指标 | Phase 1 现状 | Phase 2 目标 |
|------|-------------|-------------|
| Quality 评估方式 | 关键词重叠率 | 信息增益 + LLM 语义评估 |
| 探索触发机制 | 队列优先级 | 能力缺口驱动 |
| 边际回报计算 | 线性差值 | 指数衰减曲线 |
| 探索过程 | 线性 | Monitor-Generate-Verify |

---

## 10. 完整系统数据流

### 10.1 当前架构问题

```
[User Input / Autonomous Discovery]
        ↓
[CuriosityEngine: 什么值得探索？]
        ↓
[Explorer: 探索并收集信息]
        ↓
[MetaCognitiveMonitor: 评估探索质量]
        ↓
[Knowledge Graph: 知识入库]
        ↓
[Notification: 告诉用户]  ← 终点
```

**出口只有一个：用户通知**。探索发现只到达了"人"，没有到达"Agent 的行为空间"。

### 10.2 Phase 1 + Phase 2 目标架构

```
用户输入 / 自主发现
       ↓
┌─────────────────────────────────────┐
│ CuriosityEngine + CompetenceTracker │ ← 能力感知调度
│ select_next_v2() → 动态 alpha       │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│ ThreePhaseExplorer                  │ ← Monitor-Generate-Verify
│ Phase 1: Monitor → 评估理解状态      │
│ Phase 2: Generate → 制定计划        │
│ Phase 3: Verify → 验证缺口填补      │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│ MetaCognitiveMonitor (增强版)          │
│ - assess_exploration_quality_v2()   │ ← 信息增益评估
│ - compute_marginal_return_v2()       │ ← 边际递减建模
│ - CompetenceTracker.update()         │
└────────────────┬────────────────────┘
                 ↓
    ┌────────────┬────────────┬────────────┐
    ↓            ↓            ↓            ↓
  知识库     Agent-      触发器      Reward
 更新     BehaviorWriter 规则更新   信号反馈
    │            │            │            │
    ↓            ↓            ↓            ↓
 知识图谱   curious-    Agent决策   Adaptive
 更新     agent-        路由信息   IntrinsicScorer
          behaviors.md              (权重自适应)
    │            │
    └─────┬──────┘
          ↓
   memory/curious/
   (#behavior-rule 标签)
          ↓
   R1D3-researcher
   memory_search 检索
          ↓
   下游 Agent / R1D3-researcher 行为改变
```

### 10.3 四个出口

| 出口 | Phase 1 覆盖 | Phase 2 覆盖 |
|------|-------------|-------------|
| 知识库更新 | ✅ 已有 | ✅ 增强（图谱结构变化） |
| 行为写入 | ✅ Agent-Behavior-Writer | 🔲 CompetenceTracker 驱动 |
| 触发器更新 | 🔲 基础版 | ✅ 能力感知版 |
| Reward 信号反馈 | 🔲 无 | ✅ AdaptiveIntrinsicScorer |

### 10.4 触发器规则增强（MetaCognitiveController）

Phase 2 扩展 `should_explore` / `should_continue`：

```python
should_explore(topic) → {
  allowed: bool,
  trigger_reason: str,          # 为什么触发/不触发
  urgency: float,                # 0-10 紧迫度
  suggested_depth: str,          # shallow / medium / deep
  expected_marginal: float,     # 预估边际回报
  related_agents: list[str]     # 可能受益的下游 Agent 列表
}
```

---

## 11. Skill 生成层（Phase 2 扩展）

### 11.1 三类生成构件

**类型 A：反思模板（Reflection Template）**

```python
{
    "type": "reflection_template",
    "trigger": "当遇到 {topic} 相关问题时自动激活",
    "prompt_fragment": "在回答前，先思考：这个问题的核心概念是 {core_concept}..."
}
```

**类型 B：能力规则（Competence Rule）**

```python
{
    "type": "competence_rule",
    "condition": "task_type == 'multi_step_reasoning' AND confidence < 3",
    "action": "触发主动探索而非直接回答",
}
```

**类型 C：自检清单（Self-Checklist）**

```python
{
    "type": "self_checklist",
    "checklist": [
        "我已经识别了问题的核心约束",
        "我对每个推理步骤标注了置信度",
    ]
}
```

### 11.2 SkillSynthesizer 实现

```python
class SkillSynthesizer:
    def synthesize(self, topic: str, findings: dict, quality: float) -> list[dict]:
        if quality < 6.0:
            return []
        
        skills = []
        core_concepts = self._extract_core_concepts(findings["summary"])
        
        if core_concepts:
            skills.append(self._generate_reflection_template(topic, core_concepts, findings))
        
        rule = self._infer_competence_rule(topic, core_concepts, findings)
        if rule:
            skills.append(rule)
        
        skills.append(self._generate_self_checklist(topic, findings))
        return skills
```

---

## 12. Reward 信号反馈闭环（Phase 2 扩展）

### 12.1 当前缺失

```
探索结果 quality=8 → 记录 → 结束
                    ↓
            没有反馈到 IntrinsicScorer 的信号权重
```

### 12.2 AdaptiveIntrinsicScorer

```python
class AdaptiveIntrinsicScorer(IntrinsicScorer):
    def update_weights(self, topic: str, predicted_quality: float, actual_quality: float):
        for signal_name in ["pred_error", "graph_density", "novelty"]:
            predicted_signal = self.last_scores.get(signal_name, 5.0)
            signal_error = abs(predicted_signal - actual_quality / 2)
            
            self.signal_accuracy[signal_name]["total"] += 1
            if signal_error < 2.0:
                self.signal_accuracy[signal_name]["correct"] += 1
        
        self._recompute_weights()
    
    def _recompute_weights(self):
        total_correct = sum(s["correct"] for s in self.signal_accuracy.values())
        if total_correct == 0:
            return
        
        new_weights = {}
        for name, stats in self.signal_accuracy.items():
            accuracy = stats["correct"] / max(stats["total"], 1)
            new_weights[name] = accuracy
        
        total = sum(new_weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in new_weights.items()}
```

---

## 13. 实现优先级

### Phase 1（已完成设计）
- ✅ Agent-Behavior-Writer（安全版，不修改核心文件）

### Phase 2（本文档）

| 任务 | 优先级 | 依赖 |
|------|--------|------|
| Task 1: Quality v2 | P0 | 无 |
| Task 2: CompetenceTracker | P0 | Task 1 |
| Task 3: select_next_v2 | P0 | Task 2 |
| Task 4: marginal_return_v2 | P1 | Task 1 |
| Task 5: ThreePhaseExplorer | P1 | Task 2, Task 3 |
| SkillSynthesizer | P2 | Task 1 |
| AdaptiveIntrinsicScorer | P2 | Task 1, Task 2 |

### Phase 3（后续版本）
- 下游 Agent 的 Action Space 集成
- 多 Agent 路由

---

## 14. 关键技术指标

| 指标 | v0.2.2 现状 | Phase 2 目标 |
|------|-------------|-------------|
| Quality 评估方式 | 关键词重叠率 | 信息增益 + LLM 语义评估 |
| Marginal Return | 线性差值 | 指数衰减曲线 |
| 探索触发机制 | 队列优先级 | 能力缺口驱动 |
| Skill 生成 | 无 | 自动生成 3 类构件 |
| Reward 反馈 | 无 | 权重自适应 |

---

## 15. 风险与注意事项

1. **Skill 生成质量门槛**：必须设置 quality >= 6.0 的门槛，避免低质量 Skills 污染下游
2. **能力追踪的数据稀疏**：新话题没有历史数据，需要冷启动策略（默认 0.5 置信度）
3. **Monitor-Generate-Verify 循环成本**：三阶段比线性流程多 1-2 次 LLM 调用，需要评估延迟
4. **权重自适应的稳定性**：频繁调整权重可能导致震荡，需要加入动量/平滑机制
5. **知识-行为映射的精度**：Skill 生成依赖 LLM 的推理质量，可能产生错误的规则映射

---

## 16. 依赖关系

```
Quality v2 ──→ CompetenceTracker（能力评估需要更准确的质量）
     │
     └──→ select_next_v2（能力感知调度需要 CompetenceTracker）

select_next_v2 ──→ ThreePhaseExplorer（需要能力评估前置）
```

---

## 17. 参考资料

- [arXiv:2411.13537](https://arxiv.org/abs/2411.13537) — MUSE: Metacognition for Unknown Situations
- [arXiv:2510.16374](https://arxiv.org/abs/2510.16374) — Monitor-Generate-Verify in LLMs
- [arXiv:2509.09675](https://arxiv.org/abs/2509.09675) — CDE: Curiosity-Driven Exploration for LLM RL
- [arXiv:1705.05363](https://arxiv.org/abs/1705.05363) — ICM: Intrinsic Curiosity Module
- `next_move_v0.2.3.md` — 完整架构背景
- `next_move_v0.2.3-phase1.md` — Phase 1 任务说明
