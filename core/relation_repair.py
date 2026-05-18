"""RelationRepairService - Periodic relation repair for isolated nodes.

Scans KG for nodes without relations and attempts to find/establish
connections based on semantic similarity and LLM verification.
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class RelationRepairService:
    """Scan isolated nodes and attempt to establish missing relations."""

    def __init__(self, llm_client=None, config: Optional[dict] = None):
        self.llm = llm_client
        self.config = config or {}
        self.min_quality = self.config.get("repair_min_quality", 5.0)
        self.max_repairs_per_cycle = self.config.get("max_repairs_per_cycle", 10)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.5)

    def scan_and_repair(self) -> Dict[str, int]:
        """Main entry point: scan for isolated nodes and repair relations.

        Returns:
            {"scanned": int, "orphan_found": int, "relations_created": int, "relations_verified": int}
        """
        from core.kg.repository_factory import get_kg_factory

        kg_factory = get_kg_factory()
        all_nodes = kg_factory.get_all_nodes_sync(limit=500)

        stats = {
            "scanned": 0,
            "orphan_found": 0,
            "relations_created": 0,
            "relations_verified": 0,
        }

        for node in all_nodes:
            topic = node.get("topic", "")
            quality = node.get("quality", 0.0)
            status = node.get("status", "pending")

            if not topic or (quality or 0) < self.min_quality:
                continue

            stats["scanned"] += 1

            # Check if node has any relations
            relations = self._get_relations_count(topic)
            if relations > 0:
                continue

            stats["orphan_found"] += 1

            if stats["relations_created"] >= self.max_repairs_per_cycle:
                break

            # Try to find candidate relations
            candidates = self._find_relation_candidates(topic, all_nodes)
            for candidate in candidates:
                if stats["relations_created"] >= self.max_repairs_per_cycle:
                    break

                # Verify relation with LLM
                if self._verify_relation(topic, candidate["topic"], candidate["similarity"]):
                    stats["relations_verified"] += 1
                    try:
                        kg_factory.create_relation_sync(
                            from_topic=topic,
                            to_topic=candidate["topic"],
                            relation_type=candidate.get("relation_type", "RELATED_TO"),
                        )
                        stats["relations_created"] += 1
                        logger.info(
                            f"[RelationRepair] Created relation: "
                            f"{topic} --{candidate.get('relation_type', 'RELATED_TO')}--> {candidate['topic']}"
                        )
                    except Exception as e:
                        logger.warning(f"[RelationRepair] Failed to create relation: {e}")

        logger.info(f"[RelationRepair] Stats: {stats}")
        return stats

    def _get_relations_count(self, topic: str) -> int:
        """Get relation count for a topic."""
        from core import knowledge_graph_compat as kg

        return kg.get_relations_count(topic)

    def _find_relation_candidates(self, topic: str, all_nodes: list) -> list:
        """Find potential relation targets using concept similarity.

        Returns list of dicts: {"topic": str, "similarity": float, "relation_type": str}
        """
        from core.concept_normalizer import get_default_normalizer

        normalizer = get_default_normalizer()
        candidates = []

        for node in all_nodes:
            other_topic = node.get("topic", "")
            if not other_topic or other_topic == topic:
                continue

            # Skip if other node is also low quality
            if (node.get("quality", 0.0) or 0) < self.min_quality:
                continue

            similarity, match_type = normalizer.compute_concept_similarity(topic, other_topic)

            if similarity >= self.similarity_threshold or match_type in (
                "naming_variant",
                "translated_concept",
            ):
                # Determine relation type based on match type
                if match_type in ("naming_variant", "translated_concept"):
                    relation_type = "RELATED_TO"
                else:
                    relation_type = "RELATED_TO"

                candidates.append(
                    {
                        "topic": other_topic,
                        "similarity": similarity,
                        "relation_type": relation_type,
                    }
                )

        # Sort by similarity descending
        candidates.sort(key=lambda c: c["similarity"], reverse=True)
        return candidates[:5]  # Top 5 candidates

    def _verify_relation(self, topic_a: str, topic_b: str, similarity: float) -> bool:
        """Verify a potential relation using LLM.

        For high similarity (>0.8) or naming variants, skip LLM verification.
        For lower similarity, ask LLM if the relation makes sense.
        """
        # High confidence: skip LLM
        if similarity >= 0.8:
            return True

        if not self.llm:
            # No LLM available: only accept high similarity
            return similarity >= 0.7

        prompt = f"""Determine if these two knowledge topics are related and should have a connection in a knowledge graph.

Topic A: {topic_a}
Topic B: {topic_b}

Reply with only "yes" or "no"."""

        try:
            response = self.llm.chat(prompt).strip().lower()
            return response.startswith("yes")
        except Exception as e:
            logger.warning(f"[RelationRepair] LLM verification failed: {e}")
            return similarity >= 0.7
