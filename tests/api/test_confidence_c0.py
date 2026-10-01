"""C0 regression tests (v0.3.5) — confidence formula + four-state coverage.

Covers the two defects found by reverse-challenge on 2026-10-01:

C0-A  short-query retrieval: acronyms like "RAG"/"LTKD" embed into the
      semantic centroid and missed the 0.75 vector threshold even though an
      exact node existed. The keyword channel recovers them.

C0-B  confidence formula: the old `similarity * (quality/10)` zeroed the
      whole score whenever quality=0, even at similarity 0.83 (LTKD).
      Quality is now a soft modulator in [0.5, 1.0].

These tests are offline (mock the KG repository) so they run without Neo4j,
plus a formula-level check that needs no dependencies at all.
"""
import pytest
from unittest.mock import Mock


# ---------------------------------------------------------------- C0-B formula

def _new_confidence(similarity: float, quality: float) -> float:
    """Mirror of the production formula in host_agent_integration."""
    quality_factor = 0.5 + 0.5 * (max(0.0, min(quality, 10.0)) / 10.0)
    return similarity * quality_factor


def test_c0b_quality_zero_no_longer_zeroes_confidence():
    # LTKD scenario: strong similarity, quality=0 → must NOT be zero.
    assert _new_confidence(0.83, 0.0) > 0.3


def test_c0b_high_quality_not_suppressed():
    assert _new_confidence(0.90, 10.0) > 0.85


def test_c0b_zero_similarity_stays_zero():
    # No hit must stay zero regardless of quality.
    assert _new_confidence(0.0, 9.0) == 0.0


def test_c0b_monotonic_in_quality():
    prev = -1.0
    for q in range(0, 11):
        c = _new_confidence(0.8, float(q))
        assert c >= prev, "confidence must be non-decreasing in quality"
        prev = c


# --------------------------------------------------------- C0-A / C1-A handler

def _handler_with(results):
    from core.api.host_agent_integration import KnowledgeConfidenceHandler
    repo = Mock()
    repo.query_knowledge_semantic_sync = Mock(return_value=results)
    h = KnowledgeConfidenceHandler()
    h._kg_repository = repo
    h._kg_factory = repo
    return h


def test_c0a_short_query_recovered_returns_nonzero():
    # Simulates the keyword channel having recovered the "RAG" node.
    h = _handler_with([{
        "topic": "Retrieval-Augmented Generation (RAG) | Pinecone",
        "score": 0.75, "quality": 9.0, "source_urls": [],
    }])
    r = h.check_confidence("RAG")
    assert r["confidence"] > 0.0
    assert r["matched_topic"].startswith("Retrieval-Augmented")


def test_c1a_known_when_quality_and_sources_ok():
    h = _handler_with([{
        "topic": "Some Topic", "score": 0.9, "quality": 8.0,
        "source_urls": ["https://a", "https://b"],
    }])
    r = h.check_confidence("some topic")
    assert r["coverage"] == "known"
    assert r["source_count"] == 2


def test_c1a_partial_when_sources_missing():
    h = _handler_with([{
        "topic": "Some Topic", "score": 0.75, "quality": 9.0,
        "source_urls": [],
    }])
    r = h.check_confidence("some topic")
    assert r["coverage"] == "partial"


def test_c1a_unknown_when_no_match():
    h = _handler_with([])
    r = h.check_confidence("不存在的话题")
    assert r["confidence"] == 0.0
    assert r.get("coverage") == "unknown"


def test_backward_compat_legacy_fields_present():
    h = _handler_with([{
        "topic": "T", "score": 0.8, "quality": 7.0, "source_urls": [],
    }])
    r = h.check_confidence("t")
    for legacy in ("confidence", "level", "quality", "similarity", "gaps", "topic"):
        assert legacy in r, f"legacy field '{legacy}' must be preserved"
