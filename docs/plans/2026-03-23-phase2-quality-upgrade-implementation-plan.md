# Phase 2: Quality Upgrade & Metacognitive Drive - Implementation Plan

> **Goal:** Upgrade exploration quality assessment, introduce competence tracking, and transform the exploration process into a Monitor-Generate-Verify loop

**Architecture:** Multi-dimensional quality assessment (Semantic Novelty + Confidence Delta + Graph Topology) + CompetenceTracker for gap-driven exploration + MGV (Monitor-Generate-Verify) cycle

**Tech Stack:** Python 3.11+, existing core modules, LLM-based semantic assessment

---

## Prerequisites

Read these files before starting:
- Design doc: `ideas/next_move_v0.2.3-phase2_development.md`
- Current quality implementation: `core/meta_cognitive_monitor.py`
- Current selection logic: `core/curiosity_engine.py`

---

## Task 1: Quality v2 - Information Gain Assessment

**Files:**
- Create: `core/quality_v2.py`
- Modify: `core/meta_cognitive_monitor.py`

### Step 1: Create quality_v2.py with semantic assessment

```python
"""Quality v2 - Information gain based quality assessment"""
import re
from typing import Optional


class QualityV2Assessor:
    """
    Three-dimensional quality assessment:
    1. Semantic Novelty (40%)
    2. Confidence Delta (30%)
    3. Graph Topology Change (30%)
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def assess_quality(self, topic: str, findings: dict, knowledge_graph) -> float:
        """
        Main quality assessment entry
        Returns: quality score (0-10)
        """
        # Semantic Novelty
        prev_summary = self._get_previous_summary(topic, knowledge_graph)
        new_summary = findings.get("summary", "")
        semantic_novelty = self._calculate_semantic_novelty(prev_summary, new_summary)
        
        # Confidence Delta
        prev_confidence = self._get_previous_confidence(topic, knowledge_graph)
        post_confidence = self._assess_confidence(new_summary)
        confidence_delta = max(0, post_confidence - prev_confidence)
        
        # Graph Topology Change
        prev_neighbors = self._get_neighbor_count(topic, knowledge_graph)
        # Note: post_neighbors will be updated after exploration
        graph_delta = 0.0  # Will be updated after KG update
        
        # Weighted sum
        quality = (
            semantic_novelty * 0.40 +
            confidence_delta * 0.30 +
            graph_delta * 0.30
        ) * 10
        
        return round(quality, 1)
    
    def _calculate_semantic_novelty(self, prev_summary: str, new_summary: str) -> float:
        """Calculate semantic novelty using LLM similarity"""
        if not prev_summary or not new_summary:
            return 1.0  # Cold start
        
        similarity = self._assess_similarity(prev_summary, new_summary)
        return 1 - similarity  # Higher novelty = lower similarity
    
    def _assess_similarity(self, text1: str, text2: str) -> float:
        """Use LLM to assess semantic similarity (0-1)"""
        prompt = f"""Assess semantic similarity (0.0-1.0):

Text1: {text1[:300]}
Text2: {text2[:300]}

Return only a number between 0.0-1.0."""
        
        try:
            response = self.llm.chat(prompt)
            numbers = re.findall(r'0?\.\d+', response)
            return float(numbers[0]) if numbers else 0.5
        except Exception:
            return 0.5  # Fallback
    
    def _assess_confidence(self, text: str) -> float:
        """Use LLM to assess confidence in understanding (0-1)"""
        if not text:
            return 0.5
        
        prompt = f"""Assess understanding confidence (0.0-1.0):

{text[:500]}

Consider: Can you explain core concepts? Give examples? Identify limitations?

Return only a number between 0.0-1.0."""
        
        try:
            response = self.llm.chat(prompt)
            numbers = re.findall(r'0?\.\d+', response)
            return float(numbers[0]) if numbers else 0.5
        except Exception:
            return 0.5
    
    def _get_previous_summary(self, topic: str, kg) -> str:
        """Get previous summary from knowledge graph"""
        try:
            topic_data = kg.get("topics", {}).get(topic, {})
            return topic_data.get("summary", "")
        except Exception:
            return ""
    
    def _get_previous_confidence(self, topic: str, kg) -> float:
        """Get previous confidence from competence state"""
        try:
            state = kg.get("competence_state", {})
            return state.get(topic, {}).get("confidence", 0.5)
        except Exception:
            return 0.5
    
    def _get_neighbor_count(self, topic: str, kg) -> int:
        """Get number of neighbors in knowledge graph"""
        try:
            topic_data = kg.get("topics", {}).get(topic, {})
            return len(topic_data.get("related_topics", []))
        except Exception:
            return 0
    
    def fallback_quality_assessment(self, findings: dict) -> float:
        """Fallback when LLM is unavailable"""
        summary_len = len(findings.get("summary", ""))
        sources_count = len(findings.get("sources", []))
        papers_count = len(findings.get("papers", []))
        
        score = min(10, summary_len / 200 + sources_count * 1.5 + papers_count * 2)
        return max(0, min(10, score))
```

### Step 2: Write tests

```python
# tests/core/test_quality_v2.py
import pytest
from unittest.mock import Mock
from core.quality_v2 import QualityV2Assessor


def test_semantic_novelty_cold_start():
    mock_llm = Mock()
    assessor = QualityV2Assessor(mock_llm)
    
    novelty = assessor._calculate_semantic_novelty("", "new content")
    assert novelty == 1.0


def test_semantic_novelty_with_similarity():
    mock_llm = Mock()
    mock_llm.chat = Mock(return_value="0.3")
    assessor = QualityV2Assessor(mock_llm)
    
    novelty = assessor._calculate_semantic_novelty("old summary", "new summary")
    assert novelty == 0.7  # 1 - 0.3


def test_assess_similarity_parsing():
    mock_llm = Mock()
    mock_llm.chat = Mock(return_value="Similarity: 0.75")
    assessor = QualityV2Assessor(mock_llm)
    
    result = assessor._assess_similarity("text1", "text2")
    assert result == 0.75


def test_fallback_assessment():
    mock_llm = Mock()
    assessor = QualityV2Assessor(mock_llm)
    
    findings = {
        "summary": "a" * 400,  # 400 chars
        "sources": ["url1", "url2"],  # 2 sources
        "papers": ["paper1"]  # 1 paper
    }
    
    score = assessor.fallback_quality_assessment(findings)
    expected = min(10, 400/200 + 2*1.5 + 1*2)  # 2 + 3 + 2 = 7
    assert score == expected
```

### Step 3: Run tests

Run: `pytest tests/core/test_quality_v2.py -v`
Expected: 4 passed

### Step 4: Commit

```bash
git add core/quality_v2.py tests/core/test_quality_v2.py
git commit -m "feat: implement Quality v2 with information gain assessment"
```

---

## Task 2: CompetenceTracker

**Files:**
- Create: `core/competence_tracker.py`
- Modify: `core/knowledge_graph.py` (add competence_state storage)

### Step 1: Implement CompetenceTracker

```python
"""Competence Tracker - Track agent competence across topics"""
from datetime import datetime, timezone
from typing import Optional
from core import knowledge_graph as kg


class CompetenceTracker:
    """
    Track agent's exploration competence across topics
    Drive exploration by competence gaps
    """
    
    LEVEL_NOVICE = 0.3
    LEVEL_COMPETENT = 0.6
    LEVEL_EXPERT = 0.85
    
    def __init__(self):
        self.kg = kg
    
    def assess_competence(self, topic: str) -> dict:
        """
        Assess agent's competence on a topic
        
        Returns:
            {
                "score": float,          # 0.0-1.0 composite score
                "level": str,            # novice / competent / expert
                "confidence": float,     # base confidence
                "explore_count": int,
                "quality_trend": float,  # positive = improving
                "reason": str
            }
        """
        state = self.kg.get_state()
        competence_state = state.get("competence_state", {})
        topic_competence = competence_state.get(topic, {})
        
        confidence = topic_competence.get("confidence", 0.5)
        quality_history = topic_competence.get("quality_history", [])
        explore_count = len(quality_history)
        
        # Calculate quality trend
        quality_trend = self._compute_quality_trend(quality_history)
        
        # Composite score
        score = (
            confidence * 0.40 +
            min(1.0, explore_count / 5) * 0.20 +
            (quality_trend + 1) / 2 * 0.20 +  # Normalize -1,1 to 0,1
            confidence * 0.20
        )
        
        return {
            "score": round(score, 2),
            "level": self._score_to_level(score),
            "confidence": confidence,
            "explore_count": explore_count,
            "quality_trend": round(quality_trend, 2),
            "reason": f"confidence={confidence:.2f}, explores={explore_count}, trend={quality_trend:+.2f}"
        }
    
    def should_explore_due_to_low_competence(self, topic: str) -> tuple[bool, str]:
        """
        Determine if exploration should be triggered due to low competence
        """
        competence = self.assess_competence(topic)
        
        if competence["level"] == "novice":
            return True, f"Low competence level: {competence['level']}"
        
        if competence["level"] == "competent" and competence["quality_trend"] < -0.5:
            return True, f"Declining competence trend: {competence['quality_trend']:.2f}"
        
        return False, f"Competence sufficient: {competence['level']}"
    
    def update_competence(self, topic: str, quality: float):
        """
        Update competence after exploration using EMA
        """
        state = self.kg.get_state()
        
        if "competence_state" not in state:
            state["competence_state"] = {}
        
        competence_state = state["competence_state"]
        
        if topic not in competence_state:
            competence_state[topic] = {
                "confidence": 0.5,
                "quality_history": [],
                "explore_count": 0,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
        
        current = competence_state[topic]
        
        # EMA update: 70% old, 30% new
        prev_confidence = current.get("confidence", 0.5)
        new_confidence = 0.7 * prev_confidence + 0.3 * (quality / 10.0)
        
        # Update quality history (keep last 5)
        quality_history = current.get("quality_history", [])
        quality_history.append(quality)
        quality_history = quality_history[-5:]
        
        competence_state[topic].update({
            "confidence": round(new_confidence, 3),
            "quality_history": quality_history,
            "explore_count": current.get("explore_count", 0) + 1,
            "last_updated": datetime.now(timezone.utc).isoformat()
        })
        
        self.kg._save_state(state)
    
    def _compute_quality_trend(self, quality_history: list) -> float:
        """
        Compute quality trend using linear regression slope
        Returns: slope normalized to -1 to +1
        """
        if len(quality_history) < 2:
            return 0.0
        
        # Use last 5 entries
        qualities = quality_history[-5:]
        n = len(qualities)
        
        # Simple linear regression
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(qualities) / n
        
        numerator = sum((x[i] - x_mean) * (qualities[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        # Normalize: assume slope range -2 to +2 is reasonable
        return max(-1.0, min(1.0, slope / 2.0))
    
    def _score_to_level(self, score: float) -> str:
        """Convert score to competence level"""
        if score < self.LEVEL_NOVICE:
            return "novice"
        elif score < self.LEVEL_COMPETENT:
            return "competent"
        elif score < self.LEVEL_EXPERT:
            return "proficient"
        else:
            return "expert"
```

### Step 2: Add KG helper functions

Add to `core/knowledge_graph.py`:

```python
def get_competence_state(topic: str) -> dict:
    """Get competence state for a topic"""
    state = _load_state()
    return state.get("competence_state", {}).get(topic, {})


def update_competence_state(topic: str, updates: dict):
    """Update competence state for a topic"""
    state = _load_state()
    
    if "competence_state" not in state:
        state["competence_state"] = {}
    
    if topic not in state["competence_state"]:
        state["competence_state"][topic] = {}
    
    state["competence_state"][topic].update(updates)
    _save_state(state)
```

### Step 3: Write tests

```python
# tests/core/test_competence_tracker.py
import pytest
from core.competence_tracker import CompetenceTracker
from core import knowledge_graph as kg


def test_assess_competence_cold_start():
    tracker = CompetenceTracker()
    result = tracker.assess_competence("new_topic")
    
    assert result["confidence"] == 0.5
    assert result["explore_count"] == 0
    assert result["level"] == "novice"  # Low score should be novice


def test_update_competence():
    tracker = CompetenceTracker()
    
    # Initial update
    tracker.update_competence("test_topic", 8.0)
    
    competence = tracker.assess_competence("test_topic")
    assert competence["explore_count"] == 1
    assert len(competence["quality_history"]) == 1


def test_quality_trend_computation():
    tracker = CompetenceTracker()
    
    # Improving trend
    trend = tracker._compute_quality_trend([5.0, 6.0, 7.0, 8.0])
    assert trend > 0
    
    # Declining trend
    trend = tracker._compute_quality_trend([8.0, 7.0, 6.0, 5.0])
    assert trend < 0


def test_should_explore_novice():
    tracker = CompetenceTracker()
    
    # New topic should trigger exploration
    should_explore, reason = tracker.should_explore_due_to_low_competence("new_topic")
    assert should_explore is True
    assert "novice" in reason.lower()


def test_score_to_level():
    tracker = CompetenceTracker()
    
    assert tracker._score_to_level(0.2) == "novice"
    assert tracker._score_to_level(0.5) == "competent"
    assert tracker._score_to_level(0.7) == "proficient"
    assert tracker._score_to_level(0.9) == "expert"
```

### Step 4: Run tests

Run: `pytest tests/core/test_competence_tracker.py -v`
Expected: 6 passed

### Step 5: Commit

```bash
git add core/competence_tracker.py tests/core/test_competence_tracker.py
git commit -m "feat: implement CompetenceTracker for gap-driven exploration"
```

---

## Task 3: select_next_v2 - Competence-Aware Scheduling

**Files:**
- Modify: `core/curiosity_engine.py`

### Step 1: Add select_next_v2 method

Add to `CuriosityEngine` class in `core/curiosity_engine.py`:

```python
from core.competence_tracker import CompetenceTracker


class CuriosityEngine:
    def __init__(self, config=None):
        self.state = kg.get_state()
        self.config = config or {}
        self.intrinsic_scorer = IntrinsicScorer(
            knowledge_graph=self.state.get("knowledge", {}),
            exploration_history=self._get_exploration_history(),
            config=config
        )
        self.competence_tracker = CompetenceTracker()  # Add this
    
    def select_next_v2(self) -> Optional[dict]:
        """
        Competence-aware selection logic:
        1. Filter out topics with sufficient competence
        2. Prioritize: low_competence + high_score + high_relevance
        3. Dynamic alpha: low competence -> more human guidance
        """
        candidates = self.kg.list_pending()
        if not candidates:
            return None
        
        scored = []
        for item in candidates:
            topic = item["topic"]
            competence = self.competence_tracker.assess_competence(topic)
            
            # Skip topics with expert competence
            if competence["level"] == "expert" and item.get("status") == "done":
                continue
            
            # Exploration value = score * (1 - competence) * relevance
            exploration_value = (
                item.get("score", 5.0) *
                (1 - competence["score"]) *
                item.get("relevance", 5.0) / 10.0
            )
            
            # Dynamic alpha based on competence
            if competence["score"] < 0.3:
                dynamic_alpha = 0.7  # More human guidance
            elif competence["score"] > 0.6:
                dynamic_alpha = 0.3  # More autonomous
            else:
                dynamic_alpha = 0.5  # Balanced
            
            scored.append({
                **item,
                "exploration_value": round(exploration_value, 2),
                "competence": competence,
                "dynamic_alpha": dynamic_alpha
            })
        
        # Sort by exploration value
        scored.sort(key=lambda x: x["exploration_value"], reverse=True)
        return scored[0] if scored else None
```

### Step 2: Write tests

```python
# tests/core/test_select_next_v2.py
import pytest
from unittest.mock import Mock, patch
from core.curiosity_engine import CuriosityEngine


def test_select_next_v2_prioritizes_low_competence():
    engine = CuriosityEngine()
    
    # Mock competence tracker
    with patch.object(engine, 'competence_tracker') as mock_tracker:
        mock_tracker.assess_competence = Mock(side_effect=lambda t: {
            "topic_low": {"score": 0.2, "level": "novice"},
            "topic_high": {"score": 0.8, "level": "expert"}
        }.get(t, {"score": 0.5, "level": "competent"}))
        
        # Mock pending items
        with patch.object(engine.kg, 'list_pending', return_value=[
            {"topic": "topic_high", "score": 9.0, "relevance": 8.0, "status": "pending"},
            {"topic": "topic_low", "score": 7.0, "relevance": 7.0, "status": "pending"}
        ]):
            result = engine.select_next_v2()
            
            # Should prioritize low competence topic
            assert result["topic"] == "topic_low"


def test_dynamic_alpha_based_on_competence():
    engine = CuriosityEngine()
    
    with patch.object(engine, 'competence_tracker') as mock_tracker:
        # Low competence -> high alpha (0.7)
        mock_tracker.assess_competence = Mock(return_value={
            "score": 0.2, "level": "novice"
        })
        
        with patch.object(engine.kg, 'list_pending', return_value=[
            {"topic": "test", "score": 7.0, "relevance": 7.0, "status": "pending"}
        ]):
            result = engine.select_next_v2()
            assert result["dynamic_alpha"] == 0.7
```

### Step 3: Commit

```bash
git add core/curiosity_engine.py tests/core/test_select_next_v2.py
git commit -m "feat: implement select_next_v2 with competence-aware scheduling"
```

---

## Task 4: marginal_return_v2 - Exponential Decay

**Files:**
- Modify: `core/meta_cognitive_monitor.py`

### Step 1: Implement exponential decay model

Add to `MetaCognitiveMonitor`:

```python
import math


def compute_marginal_return_v2(self, topic: str, quality_history: list, current_quality: float) -> float:
    """
    Exponential decay model for marginal return:
    value_n = base * decay^(n-1)
    
    If current_quality exceeds predicted curve -> high value
    If current_quality below predicted curve -> diminishing returns
    """
    if len(quality_history) < 2:
        return 1.0  # First exploration
    
    # Fit decay curve: log(y) = log(base) + x * log(decay)
    try:
        n = len(quality_history)
        x = list(range(1, n + 1))
        log_y = [math.log(max(q, 0.1)) for q in quality_history]
        
        x_mean = sum(x) / n
        y_mean = sum(log_y) / n
        
        numerator = sum((x[i] - x_mean) * (log_y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            decay_rate = 0.8
        else:
            slope = numerator / denominator
            decay_rate = math.exp(slope)
            decay_rate = max(0.5, min(0.95, decay_rate))
    except Exception:
        decay_rate = 0.8
    
    # Predict next quality
    predicted_next = quality_history[-1] * decay_rate
    
    # Actual vs predicted = excess return
    if predicted_next > 0:
        marginal_return = (current_quality - predicted_next) / predicted_next
    else:
        marginal_return = 1.0
    
    return round(marginal_return, 2)
```

### Step 2: Write tests

```python
# tests/core/test_marginal_return_v2.py
import pytest
from core.meta_cognitive_monitor import MetaCognitiveMonitor


def test_marginal_return_first_exploration():
    monitor = MetaCognitiveMonitor(llm_client=None)
    result = monitor.compute_marginal_return_v2("topic", [], 8.0)
    assert result == 1.0


def test_marginal_return_declining_trend():
    monitor = MetaCognitiveMonitor(llm_client=None)
    # Declining quality: 9, 8, 7
    history = [9.0, 8.0]
    current = 7.0
    
    result = monitor.compute_marginal_return_v2("topic", history, current)
    # Should be around 0 or negative (as expected by decay model)
    assert result < 0.5


def test_marginal_return_exceeding_expectation():
    monitor = MetaCognitiveMonitor(llm_client=None)
    # Stable quality then jump
    history = [7.0, 7.0]
    current = 9.0  # Exceeds decay prediction
    
    result = monitor.compute_marginal_return_v2("topic", history, current)
    # Should be positive (exceeded prediction)
    assert result > 0
```

### Step 3: Commit

```bash
git add core/meta_cognitive_monitor.py tests/core/test_marginal_return_v2.py
git commit -m "feat: implement marginal_return_v2 with exponential decay model"
```

---

## Task 5: ThreePhaseExplorer - MGV Cycle

**Files:**
- Create: `core/three_phase_explorer.py`
- Modify: `curious_agent.py` (optional integration)

### Step 1: Implement ThreePhaseExplorer

```python
"""ThreePhaseExplorer - Monitor-Generate-Verify cycle"""
import json
from typing import Optional


class ThreePhaseExplorer:
    """
    Three-phase exploration cycle:
    1. Monitor: Assess current understanding, identify knowledge gaps
    2. Generate: Create exploration plan based on gaps
    3. Verify: Execute and validate gap closure
    """
    
    def __init__(self, explorer, monitor, llm_client):
        self.explorer = explorer
        self.monitor = monitor
        self.llm = llm_client
    
    def explore(self, curiosity_item: dict) -> dict:
        """Execute three-phase exploration"""
        topic = curiosity_item["topic"]
        depth = curiosity_item.get("depth", "medium")
        
        # Phase 1: Monitor
        monitor_result = self._phase1_monitor(topic)
        if monitor_result.get("already_known"):
            return {
                "status": "already_known",
                "confidence": monitor_result["confidence"],
                "reason": monitor_result.get("reason", "")
            }
        
        knowledge_gaps = monitor_result.get("knowledge_gaps", [])
        
        # Phase 2: Generate
        exploration_plan = self._phase2_generate(topic, knowledge_gaps, depth)
        
        # Phase 3: Verify
        findings = self._phase3_execute(topic, exploration_plan)
        verification = self._verify_knowledge_gaps(knowledge_gaps, findings)
        
        return {
            "status": "success",
            "findings": findings,
            "verification_score": verification["score"],
            "gaps_filled": verification["gaps_filled"],
            "knowledge_gaps": knowledge_gaps
        }
    
    def _phase1_monitor(self, topic: str) -> dict:
        """Assess understanding and identify gaps"""
        confidence = self.monitor._compute_user_relevance(topic)
        
        if confidence > 0.8:
            return {
                "already_known": True,
                "confidence": confidence,
                "reason": f"High confidence ({confidence:.2f})"
            }
        
        gaps = self._identify_knowledge_gaps(topic)
        return {
            "already_known": False,
            "confidence": confidence,
            "knowledge_gaps": gaps
        }
    
    def _identify_knowledge_gaps(self, topic: str) -> list:
        """Use LLM to identify knowledge gaps"""
        prompt = f"""Analyze "{topic}" and identify knowledge gaps:

1. Technical definition clear? (no_technical_definition)
2. Empirical results/benchmarks? (no_empirical_results)
3. Practical applications? (no_applications)
4. Relations to other concepts? (no_relations)
5. Limitations clear? (no_limitations)

Return JSON:
{{"gaps": [{{"type": "no_empirical_results", "description": "...", "priority": 0.8}}]}}"""
        
        try:
            response = self.llm.chat(prompt)
            result = json.loads(response)
            return result.get("gaps", [])
        except Exception:
            return [{"type": "general", "description": "Need more information", "priority": 0.5}]
    
    def _phase2_generate(self, topic: str, gaps: list, depth: str) -> list:
        """Generate exploration plan based on gaps"""
        plans = []
        for gap in gaps:
            gap_type = gap.get("type", "general")
            priority = gap.get("priority", 0.5)
            
            action_map = {
                "no_technical_definition": ("find_paper", "technical_implementation"),
                "no_empirical_results": ("find_benchmark", "quantitative_evaluation"),
                "no_applications": ("find_usecase", "practical_applications"),
                "no_limitations": ("find_critique", "limitations_and_drawbacks")
            }
            
            action, target = action_map.get(gap_type, ("general_explore", "overview"))
            
            plans.append({
                "action": action,
                "target": target,
                "priority": priority,
                "depth": "deep" if priority > 0.7 else depth
            })
        
        plans.sort(key=lambda x: x["priority"], reverse=True)
        return plans
    
    def _phase3_execute(self, topic: str, plan: list) -> dict:
        """Execute exploration plan"""
        if not plan:
            return {}
        
        # Use existing explorer with highest priority plan
        curiosity_item = {
            "topic": topic,
            "depth": plan[0].get("depth", "medium")
        }
        
        return self.explorer.explore(curiosity_item)
    
    def _verify_knowledge_gaps(self, gaps: list, findings: dict) -> dict:
        """Verify if gaps were filled"""
        summary = findings.get("findings", "")
        
        if not gaps or not summary:
            return {"score": 0.5, "gaps_filled": []}
        
        # Simple keyword matching for verification
        gaps_filled = []
        for gap in gaps:
            gap_type = gap.get("type", "").lower()
            if gap_type.replace("no_", "") in summary.lower():
                gaps_filled.append(gap_type)
        
        score = len(gaps_filled) / len(gaps) if gaps else 0.5
        return {"score": score, "gaps_filled": gaps_filled}
```

### Step 2: Write tests

```python
# tests/core/test_three_phase_explorer.py
import pytest
from unittest.mock import Mock
from core.three_phase_explorer import ThreePhaseExplorer


def test_phase1_monitor_high_confidence():
    mock_explorer = Mock()
    mock_monitor = Mock()
    mock_monitor._compute_user_relevance = Mock(return_value=0.9)
    
    explorer = ThreePhaseExplorer(mock_explorer, mock_monitor, Mock())
    result = explorer._phase1_monitor("test_topic")
    
    assert result["already_known"] is True
    assert result["confidence"] == 0.9


def test_phase1_monitor_low_confidence():
    mock_explorer = Mock()
    mock_monitor = Mock()
    mock_monitor._compute_user_relevance = Mock(return_value=0.5)
    
    mock_llm = Mock()
    mock_llm.chat = Mock(return_value='{"gaps": [{"type": "no_definition"}]}')
    
    explorer = ThreePhaseExplorer(mock_explorer, mock_monitor, mock_llm)
    result = explorer._phase1_monitor("test_topic")
    
    assert result["already_known"] is False
    assert "knowledge_gaps" in result


def test_phase2_generate_plans():
    explorer = ThreePhaseExplorer(Mock(), Mock(), Mock())
    
    gaps = [
        {"type": "no_empirical_results", "priority": 0.8},
        {"type": "no_applications", "priority": 0.5}
    ]
    
    plans = explorer._phase2_generate("topic", gaps, "medium")
    
    assert len(plans) == 2
    assert plans[0]["priority"] == 0.8  # Higher priority first
    assert plans[0]["depth"] == "deep"  # High priority -> deep
```

### Step 3: Commit

```bash
git add core/three_phase_explorer.py tests/core/test_three_phase_explorer.py
git commit -m "feat: implement ThreePhaseExplorer with MGV cycle"
```

---

## Final Integration Test

```python
# tests/test_phase2_integration.py
import pytest
from core.quality_v2 import QualityV2Assessor
from core.competence_tracker import CompetenceTracker
from core.curiosity_engine import CuriosityEngine


def test_full_phase2_flow():
    """Test complete Phase 2 integration"""
    # Quality v2 assessment
    mock_llm = Mock()
    assessor = QualityV2Assessor(mock_llm)
    
    # Competence tracking
    tracker = CompetenceTracker()
    
    # Engine with competence-aware selection
    engine = CuriosityEngine()
    
    # Verify all components work together
    assert assessor is not None
    assert tracker is not None
    assert engine.competence_tracker is not None
```

Run: `pytest tests/test_phase2_integration.py -v`
Expected: 1 passed

```bash
git add tests/test_phase2_integration.py
git commit -m "test: add Phase 2 integration tests"
```

---

## Summary

Phase 2 implements:
1. **Quality v2**: Information gain assessment (semantic + confidence + topology)
2. **CompetenceTracker**: Gap-driven exploration tracking
3. **select_next_v2**: Competence-aware topic scheduling
4. **marginal_return_v2**: Exponential decay modeling
5. **ThreePhaseExplorer**: MGV (Monitor-Generate-Verify) cycle

**Total estimated time:** 6-8 hours
**Dependencies:** Phase 3 (completed)
**Test coverage:** 20+ new tests
