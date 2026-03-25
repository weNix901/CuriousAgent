"""Quality v2 - Information gain based quality assessment"""
import re
from typing import Optional


class QualityV2Assessor:
    """
    Three-dimensional quality assessment:
    1. Semantic Novelty (40%)
    2. Information Gain (40%)
    3. Graph Topology Change (20%)
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def assess_quality(self, topic: str, findings: dict, knowledge_graph) -> float:
        """
        Main quality assessment entry
        Returns: quality score (0-10)
        """
        prev_summary = self._get_previous_summary(topic, knowledge_graph)
        new_summary = findings.get("summary", "")

        semantic_novelty = self._calculate_semantic_novelty(prev_summary, new_summary)
        information_gain = self._assess_information_gain(topic, new_summary)

        graph_delta = 0.0
        if not prev_summary:
            graph_delta = 0.5

        quality = (
            semantic_novelty * 0.40 +
            information_gain * 0.40 +
            graph_delta * 0.20
        ) * 10

        return round(quality, 1)
    
    def _calculate_semantic_novelty(self, prev_summary: str, new_summary: str) -> float:
        """Calculate semantic novelty using LLM similarity"""
        if not prev_summary or not new_summary:
            return 1.0
        
        similarity = self._assess_similarity(prev_summary, new_summary)
        return 1 - similarity
    
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
            return 0.5
    
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

    def _assess_information_gain(self, topic: str, new_summary: str) -> float:
        """
        评估信息增益：相比只知 topic 名称，探索获得了多少新知识。

        评分标准（0.0-1.0）：
        - 0.0: 总结 = topic 名称的同义改写，无任何新知识
        - 0.3: 知道基本定义，但无法解释如何运作/适用场景/局限性
        - 0.6: 有概念理解，能举出 1-2 个具体例子或方法名称
        - 0.8: 有较深理解，知道多种方法/框架/对比/局限性
        - 1.0: 获得可操作的详细知识，能解释具体原理/算法步骤/应用方式
        """
        if not new_summary or not new_summary.strip():
            return 0.0

        prompt = f"""你是知识质量评估专家。

Task: 评估这次探索相比"只知道 topic 名称"的信息增益。

Topic: {topic}

探索发现:
{new_summary[:800]}

评估问题：这次探索让你对"{topic}"的理解增加了多少？
- 0.0: 总结只是 topic 名称的重复或极度泛泛的描述（如"这是一个关于{topic}的领域"），没有提供任何具体知识
- 0.3: 知道是关于什么的，但无法解释如何运作、有什么方法、适用于什么场景
- 0.6: 有基本概念理解，能举出 1-2 个具体例子或方法名称
- 0.8: 有较深理解，知道多种方法/框架/对比/局限性
- 1.0: 获得可操作的详细知识，能解释具体原理、算法步骤或实际应用方式

Return only a number between 0.0-1.0."""

        try:
            response = self.llm.chat(prompt)
            numbers = re.findall(r'0?\.\d+', response)
            if numbers:
                return max(0.0, min(1.0, float(numbers[0])))
            return 0.5
        except Exception:
            return 0.5
    
    def _get_previous_summary(self, topic: str, kg) -> str:
        """Get previous summary from knowledge graph"""
        try:
            state = kg.get_state()
            topic_data = state.get("knowledge", {}).get("topics", {}).get(topic, {})
            return topic_data.get("summary", "")
        except Exception:
            return ""

    def _get_previous_confidence(self, topic: str, kg) -> float:
        """Get previous confidence from competence state"""
        try:
            state = kg.get_state()
            competence_state = state.get("competence_state", {})
            return competence_state.get(topic, {}).get("confidence", 0.5)
        except Exception:
            return 0.5

    def _get_neighbor_count(self, topic: str, kg) -> int:
        """Get number of neighbors in knowledge graph (children + parents)"""
        try:
            state = kg.get_state()
            topics = state.get("knowledge", {}).get("topics", {})
            topic_data = topics.get(topic, {})
            # 邻居数 = children 数 + 被哪些父节点引用
            children_count = len(topic_data.get("children", []))
            parent_count = sum(1 for t, v in topics.items() if topic in v.get("children", []))
            return children_count + parent_count
        except Exception:
            return 0
    
    def fallback_quality_assessment(self, findings: dict) -> float:
        """Fallback when LLM is unavailable"""
        summary_len = len(findings.get("summary", ""))
        sources_count = len(findings.get("sources", []))
        papers_count = len(findings.get("papers", []))
        
        score = min(10, summary_len / 200 + sources_count * 1.5 + papers_count * 2)
        return max(0, min(10, score))
