"""
Meta-cognitive monitor - Pure monitoring module
Responsible for evaluating exploration quality, computing marginal returns, recording exploration history
"""
import logging
import re
from core import knowledge_graph_compat as kg

logger = logging.getLogger(__name__)


class MetaCognitiveMonitor:
    """Meta-cognitive monitor - read-only queries and quality evaluation"""

    def __init__(self, llm_client=None):
        self.kg = kg
        self.llm = llm_client
        from .quality_v2 import QualityV2Assessor
        self.quality_v2 = QualityV2Assessor(llm_client)

    def get_explore_count(self, topic: str) -> int:
        """Get exploration count for topic"""
        return kg.get_topic_explore_count(topic)

    def get_marginal_returns(self, topic: str) -> list[float]:
        """Get marginal return history for topic"""
        return kg.get_topic_marginal_returns(topic)

    def get_last_quality(self, topic: str) -> float:
        """Get last exploration quality for topic"""
        state = kg.get_state()
        mc = state.get("meta_cognitive", {})
        return mc.get("last_quality", {}).get(topic, 0.0)

    def is_topic_blocked(self, topic: str) -> bool:
        """Check if topic is blocked from exploration"""
        return kg.is_topic_completed(topic)

    def assess_exploration_quality(self, topic: str, findings: dict) -> float:
        try:
            v2_quality = self.quality_v2.assess_quality(topic, findings, kg)
            if v2_quality > 0:
                return v2_quality
        except Exception as e:
            print(f"[MetaCognitiveMonitor] QualityV2 failed, falling back: {e}")

        try:
            current_keywords = self._extract_keywords(findings.get("summary", ""))
            known_keywords = set(kg.get_topic_keywords(topic))
            new_keywords = [k for k in current_keywords if k not in known_keywords]
            new_discovery_rate = len(new_keywords) / max(len(current_keywords), 1)

            prev_depth = kg.get_topic_depth(topic)
            depth_score = self._assess_depth_score(findings)
            depth_improvement = min(1.0, depth_score / max(prev_depth + 1, 1))

            user_relevance = self._compute_user_relevance(topic)

            quality = (new_discovery_rate * 0.35 +
                      depth_improvement * 0.35 +
                      user_relevance * 0.30) * 10

            return round(quality, 1)
        except Exception as e:
            print(f"[MetaCognitiveMonitor] Error assessing quality: {e}")
            return 5.0

    def compute_marginal_return(self, topic: str, current_quality: float) -> float:
        """Compute marginal return (change in quality vs historical average)"""
        returns = self.get_marginal_returns(topic)

        if not returns:
            return 1.0

        recent_returns = returns[-3:] if len(returns) >= 3 else returns
        avg_previous = sum(recent_returns) / len(recent_returns)

        marginal = (current_quality / 10.0) - avg_previous

        return round(marginal, 2)

    def record_exploration(self, topic: str, quality: float,
                          marginal_return: float, notified: bool) -> None:
        """Record exploration result to state.json"""
        kg.update_meta_exploration(topic, quality, marginal_return, notified)

    def _extract_keywords(self, text: str) -> list:
        """Extract keywords from text (5-10), prefer LLM, fail-fast to rules"""
        if self.llm and text:
            prompt = f"""Extract 5-10 core concept keywords from the following text (comma-separated):

{text[:500]}

Return only keywords, nothing else."""
            try:
                response = self.llm.chat(prompt)
                keywords = [k.strip().lower() for k in response.split(",") if k.strip()]
                if len(keywords) >= 3:
                    return keywords[:10]
            except Exception as e:
                logger.warning(f"Failed to extract keywords via LLM: {e}", exc_info=True)

        words_with_numbers = re.findall(r'\b[a-z]*\d+[a-z]*\b', text.lower())
        words_only_letters = re.findall(r'\b[a-z]{4,}\b', text.lower())
        all_words = list(set(words_with_numbers + words_only_letters))
        stopwords = {
            'that', 'this', 'with', 'from', 'have', 'been', 'will', 'would',
            'could', 'their', 'they', 'them', 'than', 'only', 'also', 'when',
            'where', 'what', 'which', 'while', 'during', 'before', 'after'
        }
        filtered = [w for w in all_words if w not in stopwords]

        from collections import Counter
        word_counts = Counter(filtered)
        return [word for word, _ in word_counts.most_common(10)]

    def _assess_depth_score(self, findings: dict) -> float:
        """Assess exploration depth score (0-10)"""
        summary = findings.get("summary", "")
        sources = findings.get("sources", [])
        papers = findings.get("papers", [])

        summary_score = min(1.0, len(summary) / 1000)
        source_score = min(1.0, len(sources) / 5)
        paper_score = min(1.0, len(papers) / 3)

        return (summary_score * 0.4 + source_score * 0.3 + paper_score * 0.3) * 10

    def _compute_user_relevance(self, topic: str) -> float:
        """Compute relevance to user interests (0-1)"""
        try:
            from core.config import get_config
            user_interests = get_config().behavior.get("user_interests", [])
        except:
            user_interests = []

        if not user_interests:
            return 0.7

        if self.llm:
            prompt = f"""Evaluate how relevant this topic is to the user's interests (0.0-1.0).

User interests: {', '.join(user_interests)}
Topic: {topic}

Scoring guide:
- 0.0-0.2: Topic is in a completely different domain from user interests
- 0.3-0.5: Topic shares a few keywords but is not central to user interests
- 0.6-0.8: Topic is directly related to one or more user interests
- 0.9-1.0: Topic is a core component of the user's main research focus

Return only a number."""
            try:
                response = self.llm.chat(prompt)
                numbers = re.findall(r'\d+\.?\d*', response)
                if numbers:
                    score = float(numbers[0])
                    return max(0.0, min(1.0, score))
            except Exception as e:
                logger.warning(f"Failed to compute user relevance for '{topic}': {e}", exc_info=True)

        topic_words = set(topic.lower().split())
        interest_words = set(' '.join(user_interests).lower().split())
        if not topic_words:
            return 0.7
        overlap = len(topic_words & interest_words) / len(topic_words)
        return min(1.0, overlap + 0.3)

    def _fallback_quality(self, topic: str, findings: dict) -> float:
        """Fallback evaluation when main assessment fails"""
        summary_len = len(findings.get("summary", ""))
        sources_count = len(findings.get("sources", []))

        score = min(10, summary_len / 200 + sources_count * 2)
        return max(0, min(10, score))

    # === v0.2.6 MetaCognitive Enhancements (F12) ===

    def get_confidence_interval(self, topic: str) -> tuple[float, float]:
        """Get confidence interval for a topic.

        Returns:
            (confidence_low, confidence_high) tuple
        """
        state = kg.get_state()
        topic_data = state["knowledge"]["topics"].get(topic, {})

        low = topic_data.get("confidence_low", 0.3)
        high = topic_data.get("confidence_high", 0.7)

        return (low, high)

    def update_node_confidence(self, topic: str, delta_evidence: int = 0,
                               delta_contradiction: int = 0):
        """Update topic confidence based on new evidence.

        Args:
            topic: Topic to update
            delta_evidence: Number of supporting evidence (+)
            delta_contradiction: Number of contradicting evidence (-)
        """
        from core.node_lock_registry import NodeLockRegistry

        with NodeLockRegistry.global_write_lock():
            state = kg.get_state()
            topic_data = state["knowledge"]["topics"].setdefault(topic, {})

            # Initialize defaults
            if "confidence_low" not in topic_data:
                topic_data["confidence_low"] = 0.3
            if "confidence_high" not in topic_data:
                topic_data["confidence_high"] = 0.7
            if "evidence_count" not in topic_data:
                topic_data["evidence_count"] = 0
            if "contradiction_count" not in topic_data:
                topic_data["contradiction_count"] = 0

            # Update
            topic_data["confidence_low"] = min(
                1.0, topic_data["confidence_low"] + delta_evidence * 0.1
            )
            topic_data["confidence_high"] = max(
                0.0, topic_data["confidence_high"] - delta_contradiction * 0.2
            )
            topic_data["evidence_count"] = topic_data.get("evidence_count", 0) + delta_evidence
            topic_data["contradiction_count"] = topic_data.get("contradiction_count", 0) + delta_contradiction

            kg._save_state(state)

    def detect_frontier(self) -> list[dict]:
        """Detect knowledge frontier.

        Frontier nodes are explored nodes with no children
        (leaf nodes with known=True).

        Returns:
            List of frontier descriptors
        """
        frontiers = []
        state = kg.get_state()

        for topic, data in state["knowledge"]["topics"].items():
            if not data.get("known"):
                continue

            children = data.get("children", [])
            if not children:
                frontiers.append({
                    "from_node": topic,
                    "frontier_type": "explicit",
                    "uncertainty": "high"
                })

        return frontiers

    def recommend_exploration_from_frontier(self) -> list[str]:
        """Recommend topics to explore from frontier.

        Returns:
            List of topic names, sorted by priority
        """
        frontiers = self.detect_frontier()

        # Sort by uncertainty (high first)
        sorted_frontiers = sorted(frontiers, key=lambda f: (
            {"high": 0, "medium": 1, "low": 2}.get(f["uncertainty"], 2)
        ))

        return [f["from_node"] for f in sorted_frontiers[:3]]

    def get_calibration_error(self) -> float:
        """Calculate Brier score for predictions.

        Brier score = mean((predicted - actual)^2)
        Lower is better (0 = perfect calibration).

        Returns:
            Brier score (0-1)
        """
        from core.exploration_history import ExplorationHistory

        history = ExplorationHistory()
        predictions = history.get_all_predictions()

        if not predictions:
            return 0.0

        scored = [p for p in predictions if p.get("actual_outcome") is not None]

        if not scored:
            return 0.0

        brier = sum(
            (p["predicted_confidence"] - (1.0 if p["actual_outcome"] else 0.0)) ** 2
            for p in scored
        ) / len(scored)

        return round(brier, 4)

    def get_topic_calibration(self, topic: str) -> dict:
        """Get calibration info for specific topic.

        Returns:
            Calibration details dict
        """
        from core.exploration_history import ExplorationHistory

        history = ExplorationHistory()
        pred = history.get_prediction(topic)

        if not pred:
            return {"topic": topic, "verdict": "no_prediction_recorded"}

        if pred.get("actual_outcome") is None:
            return {"topic": topic, "verdict": "pending"}

        error = abs(pred["predicted_confidence"] - (1.0 if pred["actual_outcome"] else 0.0))

        if error < 0.2:
            verdict = "well_calibrated"
        elif pred["predicted_confidence"] > 0.7:
            verdict = "overconfident"
        else:
            verdict = "underconfident"

        return {
            "topic": topic,
            "predicted": pred["predicted_confidence"],
            "actual_outcome": pred["actual_outcome"],
            "error": round(error, 3),
            "verdict": verdict
        }
