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
        prev_summary = self._get_previous_summary(topic, knowledge_graph)
        new_summary = findings.get("summary", "")
        
        semantic_novelty = self._calculate_semantic_novelty(prev_summary, new_summary)
        
        prev_confidence = self._get_previous_confidence(topic, knowledge_graph)
        post_confidence = self._assess_confidence(new_summary)
        confidence_delta = max(0, post_confidence - prev_confidence)
        
        prev_neighbors = self._get_neighbor_count(topic, knowledge_graph)
        graph_delta = 0.0
        
        if not prev_summary:
            confidence_delta = max(confidence_delta, 0.5)
            graph_delta = 0.5
        
        quality = (
            semantic_novelty * 0.40 +
            confidence_delta * 0.30 +
            graph_delta * 0.30
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
