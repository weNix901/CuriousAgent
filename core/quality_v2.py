"""Quality v2 - Information gain based quality assessment"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class QualityV2Assessor:
    """
    Three-dimensional quality assessment:
    1. Semantic Novelty (40%)
    2. Information Gain (40%)
    3. Graph Topology Change (20%)
    
    v0.2.8: Dual-channel evaluation with KnowledgeAssertionEvaluator
    """
    
    def __init__(self, llm_client, embedding_service=None, 
                 assertion_index=None, knowledge_graph=None):
        self.llm = llm_client
        self.embedding_service = embedding_service
        self.assertion_index = assertion_index
        self.kg = knowledge_graph
        self.assertion_evaluator = None
        
        if embedding_service and assertion_index and knowledge_graph:
            from core.knowledge_assertion_evaluator import KnowledgeAssertionEvaluator
            self.assertion_evaluator = KnowledgeAssertionEvaluator(
                llm_client, embedding_service, assertion_index, knowledge_graph
            )
    
    def assess_quality(self, topic: str, findings: dict, knowledge_graph) -> float:
        """
        Main quality assessment with dual-channel evaluation.
        
        Channel 1: Knowledge Assertion Evaluation (Primary)
        Channel 2: Legacy Information Gain (Fallback/Reference)
        
        Returns: quality score (0-10)
        """
        assertion_result = None
        legacy_quality = None
        
        if self.assertion_evaluator:
            try:
                assertion_result = self.assertion_evaluator.assess_quality(
                    topic, findings
                )
                print(f"[QualityV2] Assertion quality: {assertion_result['quality']}")
            except Exception as e:
                print(f"[QualityV2] Assertion evaluation failed: {e}")
        
        try:
            legacy_quality = self._calculate_legacy_quality(topic, findings, knowledge_graph)
            print(f"[QualityV2] Legacy quality: {legacy_quality}")
        except Exception as e:
            print(f"[QualityV2] Legacy evaluation failed: {e}")
        
        return self._aggregate_quality(assertion_result, legacy_quality)
    
    def _aggregate_quality(self, assertion_result: Optional[dict], 
                          legacy_quality: Optional[float]) -> float:
        """
        Aggregate quality scores using smart consensus.
        
        Rules:
        1. If both agree on low quality (< 3.0), return low
        2. If assertion says 0.0 but legacy says high (> 6.0), trust legacy
        3. If assertion says high but legacy says very low, trust assertion
        4. Default: prefer assertion when reasonable
        """
        if assertion_result is None and legacy_quality is None:
            print("[QualityV2] Both evaluations failed, returning neutral 5.0")
            return 5.0
        
        if assertion_result is None:
            print("[QualityV2] Using legacy only")
            return round(legacy_quality, 1) if legacy_quality is not None else 5.0
        
        assertion_quality = assertion_result['quality']
        
        if legacy_quality is None:
            print("[QualityV2] Using assertion only")
            return assertion_quality
        
        if assertion_quality < 3.0 and legacy_quality < 3.0:
            result = min(assertion_quality, legacy_quality)
            print(f"[QualityV2] Consensus low: {result}")
            return round(result, 1)
        
        if assertion_quality == 0.0 and legacy_quality > 6.0:
            print(f"[QualityV2] Warning: Assertion 0.0 but legacy {legacy_quality}, using legacy")
            return round(legacy_quality, 1)
        
        if assertion_quality > 7.0 and legacy_quality < 3.0:
            blended = assertion_quality * 0.7 + legacy_quality * 0.3
            print(f"[QualityV2] High assertion, low legacy: blended {blended}")
            return round(blended, 1)
        
        if assertion_quality > 0:
            print(f"[QualityV2] Using assertion: {assertion_quality}")
            return assertion_quality
        
        print(f"[QualityV2] Fallback to legacy: {legacy_quality}")
        return round(legacy_quality, 1)
    
    def _calculate_legacy_quality(self, topic: str, findings: dict, 
                                   knowledge_graph) -> float:
        """Calculate legacy quality score (existing logic)"""
        prev_summary = self._get_previous_summary(topic, knowledge_graph)
        new_summary = findings.get("summary", "")
        
        semantic_novelty = self._calculate_semantic_novelty(prev_summary, new_summary)
        information_gain = self._assess_information_gain(topic, prev_summary, new_summary)
        
        graph_delta = 0.0 if prev_summary else 0.5
        
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
        prompt = f"""Assess semantic overlap between two texts about the same or related topic (0.0-1.0).

Text1: {text1[:300]}
Text2: {text2[:300]}

Scoring guide:
- 0.0-0.2: Completely different sub-topics or contradictory claims
  (e.g., Text1 about RL, Text2 about NLP, or Text1 agrees Text2 disagrees)
- 0.3-0.5: Same general domain but different specific aspects or methods
  (e.g., both about AI Agents but one about planning, one about memory)
- 0.6-0.7: Same sub-topic, similar conclusions but different evidence or examples
- 0.8-1.0: Same specific claim, same evidence, only reworded

Return only a number between 0.0-1.0."""

        try:
            response = self.llm.chat(prompt)
            numbers = re.findall(r'0?\.\d+', response)
            return float(numbers[0]) if numbers else 0.5
        except Exception as e:
            logger.warning(f"Failed to assess similarity: {e}", exc_info=True)
            return 0.5
    
    def _assess_information_gain(self, topic: str, prev_summary: str, new_summary: str) -> float:
        """Assess information gain between previous and new summary"""
        if not new_summary or not new_summary.strip():
            return 0.0
        
        if not prev_summary or not prev_summary.strip():
            prompt = f"""Assess information gain from exploring topic '{topic}'.

New findings:
{new_summary[:800]}

Score 0.0-1.0 based on:
- 0.0: No substantive information
- 0.3: Basic concepts mentioned
- 0.6: Clear explanations with examples
- 0.8: Deep understanding with methods/limitations
- 1.0: Comprehensive actionable knowledge

Return only a number between 0.0-1.0."""
        else:
            prompt = f"""Assess information gain compared to previous findings.

Topic: {topic}

Previous findings:
{prev_summary[:500]}

New findings:
{new_summary[:500]}

Score 0.0-1.0 based on:
- 0.0: Same content, just reworded
- 0.3: ~20-30% new information
- 0.6: ~50% new content, complementary
- 0.8: ~70-80% new information
- 1.0: >90% new information

Return only a number between 0.0-1.0."""

        try:
            response = self.llm.chat(prompt)
            numbers = re.findall(r'0?\.\d+', response)
            if numbers:
                return max(0.0, min(1.0, float(numbers[0])))
            return 0.5
        except Exception as e:
            logger.warning(f"Failed to assess information gain for '{topic}': {e}", exc_info=True)
            return 0.5
    
    def _get_previous_summary(self, topic: str, kg) -> str:
        """Get previous summary from knowledge graph"""
        try:
            state = kg.get_state()
            topic_data = state.get("knowledge", {}).get("topics", {}).get(topic, {})
            return topic_data.get("summary", "")
        except Exception as e:
            logger.warning(f"Failed to get previous summary for '{topic}': {e}", exc_info=True)
            return ""

    def _get_previous_confidence(self, topic: str, kg) -> float:
        """Get previous confidence from competence state"""
        try:
            state = kg.get_state()
            competence_state = state.get("competence_state", {})
            return competence_state.get(topic, {}).get("confidence", 0.5)
        except Exception as e:
            logger.warning(f"Failed to get previous confidence for '{topic}': {e}", exc_info=True)
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
        except Exception as e:
            logger.warning(f"Failed to get neighbor count for '{topic}': {e}", exc_info=True)
            return 0
    
    def fallback_quality_assessment(self, findings: dict) -> float:
        """Fallback when LLM is unavailable"""
        summary_len = len(findings.get("summary", ""))
        sources_count = len(findings.get("sources", []))
        papers_count = len(findings.get("papers", []))
        
        score = min(10, summary_len / 200 + sources_count * 1.5 + papers_count * 2)
        return max(0, min(10, score))
