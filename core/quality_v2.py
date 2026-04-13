"""Quality v2 - Information gain based quality assessment"""
import re
from typing import Optional


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

    def _assess_information_gain(self, topic: str, prev_summary: str, new_summary: str) -> float:
        """
        评估信息增益：相比之前的 summary，新 summary 提供了多少新信息。

        评分标准（0.0-1.0）：
        - 0.0: 新 summary 与旧 summary 完全相同或只是同义改写，无新信息
        - 0.3: 有少量新信息，但大部分内容与之前重复
        - 0.6: 有明显新内容，约一半信息与之前不同
        - 0.8: 有大量新信息，与之前总结互补
        - 1.0: 全新信息，与之前总结几乎无重叠
        """
        if not new_summary or not new_summary.strip():
            return 0.0
        
        # 如果没有之前的 summary，使用原始逻辑评估绝对信息增益
        if not prev_summary or not prev_summary.strip():
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
        else:
            # 有之前的 summary，评估相对信息增益（对比新旧）
            prompt = f"""你是知识质量评估专家。

Task: 评估这次探索相比上一次探索的信息增益。

Topic: {topic}

之前的发现:
{prev_summary[:500]}

新的发现:
{new_summary[:500]}

评估问题：新的发现相比之前的发现，增加了多少新信息？
- 0.0: 新发现与旧发现完全相同，只是改写了措辞，无任何新信息
- 0.3: 有少量新信息（约 20-30%），但大部分内容与之前重复
- 0.6: 有明显新内容（约 50%），与之前的发现互补
- 0.8: 有大量新信息（约 70-80%），显著扩展了对该话题的理解
- 1.0: 几乎全是新信息（>90%），与之前的发现几乎没有重叠

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
