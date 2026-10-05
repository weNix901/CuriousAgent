"""Host Agent (R1D3) integration - KG confidence queries and topic injection."""
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class KnowledgeConfidenceHandler:
    
    def __init__(self, kg_repository=None):
        if kg_repository is not None:
            self._kg_repository = kg_repository
        else:
            from core.kg.repository_factory import get_kg_factory
            self._kg_factory = get_kg_factory()
            self._kg_repository = None
    
    def check_confidence(self, topic: str) -> dict:
        if self._kg_repository is not None:
            semantic_results = self._kg_repository.query_knowledge_semantic_sync(
                query_text=topic,
                top_k=3,
                threshold=0.75,
                status_filter="done"
            )
        else:
            semantic_results = self._kg_factory.query_knowledge_semantic_sync(
                query_text=topic,
                top_k=3,
                threshold=0.75,
                status_filter="done"
            )
        
        if not semantic_results:
            # C1-A: no node matched → `unknown` (search may still answer) or
            # `void` (no match AND prior failed exploration). The early-return
            # branch previously omitted coverage fields entirely; add them so
            # every response carries the four-state label.
            failed = self._topic_has_failed_exploration(topic)
            return {
                "confidence": 0.0,
                "explore_count": 0,
                "gaps": ["No matching knowledge found"],
                "level": "novice",
                "topic": topic,
                "coverage": "void" if failed else "unknown",
                "coverage_reason": (
                    "no node and prior exploration failed" if failed
                    else "no matching node"
                ),
                "source_count": 0,
                "explore_failed": failed,
            }
        
        best_match = semantic_results[0]
        matched_topic = best_match["topic"]
        similarity_score = best_match["score"]
        quality = best_match.get("quality", 0.0) or 0.0
        source_count = best_match.get("source_count")
        if source_count is None:
            srcs = best_match.get("source_urls")
            source_count = len(srcs) if isinstance(srcs, (list, tuple)) else 0

        # 批0 (v0.3.6) E1: substance gate. A retrieval hit is not automatically
        # usable knowledge. Ghost nodes (content/definition/core all empty)
        # carry high quality but nothing to read — e.g. '知识图谱' →
        # 'Knowledge Distillation' (quality=8.0, content=""). Trusting such a
        # node corrupts the four-state verdict. When the gate fails we treat it
        # exactly like "no matching node": downgrade to unknown/void. This runs
        # BEFORE the coverage resolver so the wrong node's quality never leaks
        # into the four-state judgment.
        from core.api.topic_consistency import check_match_substance
        substance = check_match_substance(best_match, query=topic, matched_topic=matched_topic)
        if not substance.dependable:
            failed = self._topic_has_failed_exploration(topic)
            logger.info(
                "E1 substance gate: rejecting matched node %r for query %r (%s)",
                matched_topic, topic, substance.reason,
            )
            return {
                "confidence": 0.0,
                "explore_count": 0,
                "gaps": ["Matched node carries no content"],
                "level": "novice",
                "topic": topic,
                "coverage": "void" if failed else "unknown",
                "coverage_reason": (
                    "matched node is a ghost (empty content)"
                    + ("; prior exploration failed" if failed else "")
                ),
                "source_count": 0,
                "explore_failed": failed,
                "rejected_match": matched_topic,
                "rejected_similarity": similarity_score,
                "match_verdict": substance.verdict,
                "match_reason": substance.reason,
            }

        # E2 (批0 residuals, v0.3.6): topic consistency. The E1 gate above only
        # catches GHOST nodes (empty content). A node can carry substance and
        # still be the WRONG topic — e.g. query "LLM" → 'TypeLLM/TypeLLM'
        # (token-substring absorption). Trusting such a node feeds the wrong
        # quality/sources into the four-state judge. Like E1, a failed check is
        # treated exactly as "no usable match": downgrade to unknown/void.
        from core.api.topic_consistency import check_topic_consistency
        consistency = check_topic_consistency(topic, matched_topic)
        if not consistency.consistent:
            failed = self._topic_has_failed_exploration(topic)
            logger.info(
                "E2 consistency gate: rejecting matched node %r for query %r (%s)",
                matched_topic, topic, consistency.reason,
            )
            return {
                "confidence": 0.0,
                "explore_count": 0,
                "gaps": ["Matched node is a different topic (token absorption)"],
                "level": "novice",
                "topic": topic,
                "coverage": "void" if failed else "unknown",
                "coverage_reason": (
                    "matched node is a different topic (token-substring absorption)"
                    + ("; prior exploration failed" if failed else "")
                ),
                "source_count": 0,
                "explore_failed": failed,
                "rejected_match": matched_topic,
                "rejected_similarity": similarity_score,
                "match_verdict": consistency.verdict,
                "match_reason": consistency.reason,
            }

        # Confidence formula history (two fixes must coexist):
        #
        # C0-B (v0.3.5): old `similarity * (quality/10)` zeroed the whole score
        # whenever quality=0, even at similarity 0.83 (LTKD). Quality became a
        # soft modulator in [0.5, 1.0] so a hit is never fully erased.
        #
        # 0b (v0.3.6): the old modulator had a 0.5 FLOOR, so a quality=0 node
        # still scored 0.45 at sim=0.9 — nearly indistinguishable from a real
        # low-quality node (quality=4.5 → 0.44). 0b asks that a zero-quality
        # node not masquerade as "some knowledge". Measured on the labelled
        # set: option A (reweight to .25/.75) dragged down ALL quality>0 rows
        # too (RAG .712→.694, LLM .545→.442) — out-of-scope collateral. Option
        # B (segmented) leaves quality>0 rows byte-identical and only damps
        # quality==0, so it satisfies 0b without touching the C0-B fix.
        #
        # Segmented modulator: quality==0 → 0.2 (still NON-zero, so C0-B holds),
        # quality>0 → original [0.5, 1.0] curve (C0-B behaviour unchanged).
        # NB: real node quality is 0 or >=4 in practice, so the seam is not
        # exercised by live data.
        if quality <= 0.0:
            quality_factor = 0.2
        else:
            quality_factor = 0.5 + 0.5 * (max(0.0, min(quality, 10.0)) / 10.0)
        confidence = similarity_score * quality_factor

        # C1-A (v0.3.5): four-state coverage via the standalone resolver.
        # Thresholds θ₁/θ₂ live in coverage_resolver and are calibrated
        # against the 20-question labelled set (see calibrate()).
        from core.api.coverage_resolver import resolve_coverage
        verdict = resolve_coverage(
            similarity=similarity_score,
            quality=quality,
            source_count=source_count,
            matched_topic=matched_topic,
            explore_failed=False,
        )

        if confidence >= 0.8:
            level = "expert"
        elif confidence >= 0.5:
            level = "intermediate"
        else:
            level = "beginner"

        return {
            "confidence": confidence,
            "matched_topic": matched_topic,
            "similarity": similarity_score,
            "quality": quality,
            "level": level,
            "gaps": [],
            "topic": topic,
            "coverage": verdict.coverage,
            "coverage_reason": verdict.reason,
            "source_count": source_count,
        }
    
    def _topic_has_failed_exploration(self, topic: str) -> bool:
        """C1-A: has this topic a recorded failed exploration in the queue?

        Drives the `void` vs `unknown` distinction: no KG node + no failed
        history = `unknown` (search may still answer); no node + prior failure
        = `void` (system-level no-basis). Best-effort: any error → False.
        """
        try:
            from core.tools.queue_tools import QueueStorage
            qs = QueueStorage()
            qs.initialize()
            conn = qs._get_connection()
            row = conn.execute(
                "SELECT count(*) FROM queue WHERE status='failed' AND topic = ?",
                (topic,),
            ).fetchone()
            return bool(row and row[0] > 0)
        except Exception:
            return False

    def _confidence_to_level(self, confidence: float) -> str:
        if confidence < 0.3:
            return "novice"
        elif confidence < 0.6:
            return "competent"
        elif confidence < 0.85:
            return "proficient"
        else:
            return "expert"
    
    def _identify_gaps(self, explore_count: int, topic_data: dict) -> list:
        gaps = []
        if explore_count < 3:
            gaps.append("Limited exploration depth")
        status = topic_data.get("status", "partial")
        if status != "complete":
            gaps.append("Topic not fully explored")
        return gaps

    def inject_topic(self, topic: str, context: str = "",
                    depth: str = "medium", source: str = "host_agent") -> dict:
        from core.knowledge_graph_compat import add_curiosity
        
        add_curiosity(topic, reason=f"Host agent injection ({source})", relevance=8.0, depth=7.0)
        
        return {
            "status": "success",
            "topic_id": f"topic_{abs(hash(topic)) % 10000}",
            "queue_position": 0,
            "priority": source == "r1d3"
        }

    def _inject_with_priority(self, topic: str, context: str, depth: str,
                             priority_config: dict) -> dict:
        boost_score = priority_config.get("boost_score", 2.0)
        
        return {
            "status": "success",
            "topic_id": f"topic_{abs(hash(topic)) % 10000}",
            "queue_position": 1,
            "priority": True,
            "boosted_score": 5.0 + boost_score
        }

    def _inject_to_queue(self, topic: str, context: str, depth: str) -> dict:
        return {
            "status": "success",
            "topic_id": f"topic_{abs(hash(topic)) % 10000}",
            "queue_position": -1,
            "priority": False
        }

    def _get_config(self) -> dict:
        try:
            from core.config import get_config
            config = get_config()
            return config.__dict__ if hasattr(config, '__dict__') else {}
        except Exception as e:
            logger.warning(f"Failed to load config: {e}", exc_info=True)
            return {}
