#!/usr/bin/env python3
"""Migrate existing KG summaries to assertion index."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.kg_graph import KGGraph
from core.knowledge_assertion_evaluator import KnowledgeAssertionEvaluator
from core.assertion_index import AssertionIndex
from core.embedding_service import EmbeddingService, EmbeddingConfig
from core.llm_client import LLMClient

def migrate_existing_kg():
    print("Initializing components...")
    kg = KGGraph()
    llm = LLMClient()
    config = EmbeddingConfig(provider="volcengine")
    embedding = EmbeddingService(config)
    index = AssertionIndex()
    evaluator = KnowledgeAssertionEvaluator(llm, embedding, index, kg)
    
    state = kg.get_state()
    topics = state.get("knowledge", {}).get("topics", {})
    print(f"Found {len(topics)} topics to migrate\n")
    
    success_count = 0
    error_count = 0
    
    for i, (topic_name, topic_data) in enumerate(topics.items(), 1):
        summary = topic_data.get("summary", "")
        if not summary or len(summary) < 50:
            print(f"  [{i}/{len(topics)}] ⏭️  Skipping '{topic_name}' (no substantial summary)")
            continue
        
        findings = {
            "summary": summary,
            "sources": topic_data.get("sources", []),
            "papers": topic_data.get("papers", [])
        }
        
        try:
            result = evaluator.assess_quality(topic_name, findings)
            print(f"  [{i}/{len(topics)}] ✓ {topic_name}: {result['quality']:.1f} "
                  f"({len(result['new_assertions'])} new, {len(result['known_assertions'])} known)")
            success_count += 1
        except Exception as e:
            print(f"  [{i}/{len(topics)}] ✗ {topic_name}: Failed - {e}")
            error_count += 1
    
    print(f"\n✅ Migration complete: Success: {success_count}/{len(topics)}, Errors: {error_count}/{len(topics)}")
    stats = index.get_stats()
    print(f"\n📊 Final index stats: {stats}")

if __name__ == "__main__":
    migrate_existing_kg()
