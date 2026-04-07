# core/knowledge_assertion_evaluator.py
"""Knowledge assertion-based quality evaluator"""
from typing import Dict, List, Optional

from core.embedding_service import EmbeddingService
from core.assertion_index import AssertionIndex
from core.assertion_generator import AssertionGenerator


class KnowledgeAssertionEvaluator:
    """Evaluate exploration quality using knowledge assertion novelty."""
    
    def __init__(self, llm_client, embedding_service: EmbeddingService,
                 assertion_index: AssertionIndex, knowledge_graph):
        self.llm = llm_client
        self.embedding_service = embedding_service
        self.index = assertion_index
        self.kg = knowledge_graph
        self.generator = AssertionGenerator(llm_client)
    
    def assess_quality(self, topic: str, findings: Dict) -> Dict:
        """Assess quality using knowledge assertion method."""
        assertions = self.generator.generate(topic, findings, num_assertions=3)
        
        if not assertions:
            return {
                'quality': 0.0,
                'new_assertions': [],
                'known_assertions': [],
                'details': {'error': 'No valid assertions generated'}
            }
        
        new_assertions = []
        known_assertions = []
        
        for assertion in assertions:
            is_new = self._is_assertion_new(assertion)
            
            if is_new:
                new_assertions.append(assertion)
            else:
                known_assertions.append(assertion)
            
            self._index_assertion(assertion, topic)
        
        quality = (len(new_assertions) / len(assertions)) * 10
        
        return {
            'quality': round(quality, 1),
            'new_assertions': new_assertions,
            'known_assertions': known_assertions,
            'details': {
                'total_assertions': len(assertions),
                'new_ratio': len(new_assertions) / len(assertions),
                'assertion_texts': assertions
            }
        }
    
    def _is_assertion_new(self, assertion: str) -> bool:
        """Check if assertion is new."""
        embedding = self.embedding_service.embed(assertion)[0]
        similar = self.index.search_similar(embedding, k=1, threshold=0.82)
        
        if similar:
            print(f"[KnowledgeAssertionEvaluator] Found similar assertion: {similar[0][0][:50]}...")
            return False
        
        if self._assertion_in_kg(assertion):
            return False
        
        return True
    
    def _assertion_in_kg(self, assertion: str) -> bool:
        """Check if assertion content exists in KG summaries"""
        try:
            state = self.kg.get_state()
            topics = state.get("knowledge", {}).get("topics", {})
            
            assertion_lower = assertion.lower()
            assertion_words = set(assertion_lower.split())
            
            for topic_name, topic_data in topics.items():
                summary = topic_data.get("summary", "").lower()
                if not summary:
                    continue
                
                summary_words = set(summary.split())
                if assertion_words:
                    overlap = len(assertion_words & summary_words) / len(assertion_words)
                    if overlap > 0.7:
                        print(f"[KnowledgeAssertionEvaluator] Found in KG topic '{topic_name}'")
                        return True
            
            return False
        except Exception as e:
            print(f"[KnowledgeAssertionEvaluator] KG check error: {e}")
            return False
    
    def _index_assertion(self, assertion: str, source_topic: str):
        """Index assertion for future deduplication"""
        try:
            embedding = self.embedding_service.embed(assertion)[0]
            self.index.insert(
                text=assertion,
                embedding=embedding,
                source_topic=source_topic
            )
        except Exception as e:
            print(f"[KnowledgeAssertionEvaluator] Failed to index assertion: {e}")
