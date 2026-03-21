"""
Meta-cognitive monitor - Pure monitoring module
Responsible for evaluating exploration quality, computing marginal returns, recording exploration history
"""
import re
import json
from typing import Optional
from core import knowledge_graph as kg


class MetaCognitiveMonitor:
    """Meta-cognitive monitor - read-only queries and quality evaluation"""

    def __init__(self, llm_client=None):
        self.kg = kg
        self.llm = llm_client

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
        """
        Three-dimensional quality scoring (0-10)
        - new_discovery_rate × 0.35
        - depth_improvement × 0.35
        - user_relevance × 0.30
        """
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
            except Exception:
                pass

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
            user_interests = get_config().user_interests
        except:
            user_interests = []

        if not user_interests:
            return 0.5

        if self.llm:
            prompt = f"""Evaluate relevance of topic to user interests (0.0-1.0):

User interests: {', '.join(user_interests)}
Topic to evaluate: {topic}

Return only a number between 0.0 and 1.0, nothing else."""
            try:
                response = self.llm.chat(prompt)
                numbers = re.findall(r'\d+\.?\d*', response)
                if numbers:
                    score = float(numbers[0])
                    return max(0.0, min(1.0, score))
            except Exception:
                pass

        topic_words = set(topic.lower().split())
        interest_words = set(' '.join(user_interests).lower().split())
        if not topic_words:
            return 0.5
        overlap = len(topic_words & interest_words) / len(topic_words)
        return min(1.0, overlap)

    def _fallback_quality(self, topic: str, findings: dict) -> float:
        """Fallback evaluation when main assessment fails"""
        summary_len = len(findings.get("summary", ""))
        sources_count = len(findings.get("sources", []))

        score = min(10, summary_len / 200 + sources_count * 2)
        return max(0, min(10, score))
