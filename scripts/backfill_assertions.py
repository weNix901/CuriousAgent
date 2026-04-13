"""
对 KG 里所有已有 topics 生成断言并建立索引。
冷启动脚本：解决 assertions.db 为空的问题。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge_graph import get_state
from core.assertion_generator import AssertionGenerator
from core.assertion_index import AssertionIndex
from core.embedding_service import EmbeddingService
from core.llm_client import LLMClient
from core.config import EmbeddingConfig


def backfill():
    kg_state = get_state()
    topics = kg_state.get("knowledge", {}).get("topics", {})

    if not topics:
        print("[Backfill] No topics found in KG, nothing to backfill.")
        return

    print(f"[Backfill] Found {len(topics)} topics in KG")

    llm = LLMClient()
    generator = AssertionGenerator(llm)
    embedding_config = EmbeddingConfig()
    embedding_service = EmbeddingService(embedding_config)
    index = AssertionIndex()

    total_assertions = 0
    processed_topics = 0

    for topic_name, topic_data in topics.items():
        summary = topic_data.get("summary", "")
        if not summary or summary.strip() == "":
            print(f"[Backfill] Skipping '{topic_name}': no summary")
            continue

        findings = {"summary": summary, "sources": topic_data.get("sources", [])}

        try:
            assertions = generator.generate(topic_name, findings, num_assertions=3)

            for assertion in assertions:
                try:
                    emb = embedding_service.embed(assertion)[0]
                    index.insert(assertion, emb, source_topic=topic_name)
                    total_assertions += 1
                except Exception as e:
                    print(f"[Backfill] Failed to embed assertion for '{topic_name}': {e}")

            processed_topics += 1
            print(f"[Backfill] Processed '{topic_name}': {len(assertions)} assertions")

        except Exception as e:
            print(f"[Backfill] Failed to generate assertions for '{topic_name}': {e}")

    stats = index.get_stats()
    print(f"\n[Backfill] Complete!")
    print(f"  Topics processed: {processed_topics}/{len(topics)}")
    print(f"  Total assertions: {total_assertions}")
    print(f"  Index stats: {stats}")


if __name__ == "__main__":
    backfill()
