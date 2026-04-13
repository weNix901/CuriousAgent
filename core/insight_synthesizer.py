from dataclasses import dataclass
from datetime import datetime


@dataclass
class Insight:
    id: str
    topic: str
    hypothesis: str
    type: str
    reasoning: str
    confidence: float
    supporting_snippets: list
    generated_by: str
    timestamp: str


@dataclass
class Pattern:
    pattern: str
    supporting_snippets: list
    related_sub_topics: list


@dataclass
class Hypothesis:
    hypothesis: str
    type: str
    reasoning: str
    supporting_snippets: list


class InsightSynthesizer:
    def __init__(self, llm_client=None):
        from core.llm_client import LLMClient
        self.llm = llm_client or LLMClient()

    def synthesize(self, topic: str, sub_topic_results: dict) -> list:
        all_snippets = []
        for sub_topic, results in sub_topic_results.items():
            all_snippets.extend(self._extract_snippets(results))

        patterns = self.cross_topic_patterns(topic, all_snippets)
        hypotheses = self.generate_hypotheses(patterns)

        scored_hypotheses = []
        for h in hypotheses:
            confidence = self.compute_confidence(h, all_snippets)
            if confidence >= 0.5:
                scored_hypotheses.append({**h.__dict__, "confidence": confidence})

        return [self._format_insight(h, topic) for h in scored_hypotheses]

    def cross_topic_patterns(self, topic: str, snippets: list) -> list:
        prompt = f"""
给定主题：{topic}
收集到的信息片段：
{self._format_snippets(snippets)}

任务：从这些片段中识别跨维度的模式。
输出 JSON 格式：
{{
  "patterns": [
    {{
      "pattern": "模式描述",
      "supporting_snippets": ["支撑片段1", "支撑片段2"],
      "related_sub_topics": ["相关的子话题列表"]
    }}
  ]
}}
"""
        try:
            response = self.llm.chat(prompt)
            return self._parse_patterns(response)
        except Exception as e:
            print(f"[InsightSynthesizer] Pattern recognition failed: {e}")
            return []

    def generate_hypotheses(self, patterns: list) -> list:
        if not patterns:
            return []

        prompt = f"""
基于以下跨维度模式，生成原创假设：

{self._format_patterns(patterns)}

要求：
1. 每个假设必须有推理过程（reasoning）
2. 假设应该超出原始信息的简单总结
3. 允许有一定推测性，但必须有片段支撑
4. 生成 3-5 个最具洞察力的假设

输出 JSON 格式：
{{
  "hypotheses": [
    {{
      "hypothesis": "假设内容",
      "type": "causal|correlation|contrast|deduction",
      "reasoning": "推理过程"
    }}
  ]
}}
"""
        try:
            response = self.llm.chat(prompt)
            return self._parse_hypotheses(response)
        except Exception as e:
            print(f"[InsightSynthesizer] Hypothesis generation failed: {e}")
            return []

    def compute_confidence(self, hypothesis: Hypothesis, snippets: list) -> float:
        support_count = len(hypothesis.supporting_snippets)
        diversity = self._compute_source_diversity(hypothesis.supporting_snippets)
        consistency = 0.8

        confidence = (
            min(support_count / 5, 1.0) * 0.4 +
            diversity * 0.3 +
            consistency * 0.3
        )
        return round(confidence, 2)

    def _extract_snippets(self, results: list) -> list:
        snippets = []
        for result in results:
            if isinstance(result, dict):
                snippet = result.get("snippet", result.get("summary", ""))
                if snippet:
                    snippets.append(snippet)
        return snippets

    def _format_snippets(self, snippets: list) -> str:
        return "\n".join([f"- {s[:200]}" for s in snippets[:10]])

    def _format_patterns(self, patterns: list) -> str:
        return "\n".join([f"- {p.pattern}" for p in patterns])

    def _parse_patterns(self, response: str) -> list:
        import json
        import re

        try:
            json_str = re.search(r'\{.*\}', response, re.DOTALL)
            if json_str:
                data = json.loads(json_str.group())
                patterns_data = data.get("patterns", [])
                return [Pattern(**p) for p in patterns_data]
        except Exception as e:
            print(f"[InsightSynthesizer] Failed to parse patterns: {e}")

        return []

    def _parse_hypotheses(self, response: str) -> list:
        import json
        import re

        try:
            json_str = re.search(r'\{.*\}', response, re.DOTALL)
            if json_str:
                data = json.loads(json_str.group())
                hypotheses_data = data.get("hypotheses", [])
                return [Hypothesis(**h) for h in hypotheses_data]
        except Exception as e:
            print(f"[InsightSynthesizer] Failed to parse hypotheses: {e}")

        return []

    def _compute_source_diversity(self, snippets: list) -> float:
        return min(len(set(snippets)) / max(len(snippets), 1), 1.0)

    def _format_insight(self, hypothesis: dict, topic: str) -> Insight:
        import uuid

        return Insight(
            id=f"ins_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
            topic=topic,
            hypothesis=hypothesis["hypothesis"],
            type=hypothesis["type"],
            reasoning=hypothesis["reasoning"],
            confidence=hypothesis["confidence"],
            supporting_snippets=hypothesis.get("supporting_snippets", []),
            generated_by="InsightSynthesizer",
            timestamp=datetime.now().isoformat()
        )
