"""批0b (v0.3.6): quality=0 must not masquerade as knowledge.

Risk R-v0.3.5-1: the soft modulator `similarity * (0.5 + 0.5*q/10)` had a 0.5
floor, so a quality=0 node still scored 0.45 at sim=0.9 — close enough to a
real low-quality node (quality=4.5 → ~0.44) to be indistinguishable. 批0b
tightens this without disturbing the C0-B fix.

Fix (option B, segmented modulator):
    quality == 0 → factor 0.2   (still NON-zero → C0-B holds)
    quality  > 0 → factor 0.5 + 0.5*q/10   (C0-B curve, byte-identical)

Option D (test-only, no formula change) was measured first and REJECTED: it
kept quality=0 at 0.413 vs quality=4.5 at 0.442 — a 0.029 gap, i.e. no usable
separation. Option A (reweight .25/.75) was rejected too: it dragged down
quality>0 rows as well (RAG .712→.694).

These tests are offline (mocked retrieval) so they need no Neo4j.

Version note (test-file labelling convention, v0.3.6): file tagged 批0b.
"""
from unittest.mock import Mock

import pytest


def _handler(rows):
    from core.api.host_agent_integration import KnowledgeConfidenceHandler
    repo = Mock()
    repo.query_knowledge_semantic_sync = Mock(return_value=rows)
    h = KnowledgeConfidenceHandler()
    h._kg_repository = repo
    h._kg_factory = repo
    return h


def _node(topic, sim, quality, sources, content="body"):
    return {
        "topic": topic,
        "content": content,
        "quality": quality,
        "source_urls": ["https://s"] * sources,
        "score": sim,
    }


# ------------------------------------------------------- 批0b: zero quality

@pytest.mark.parametrize("topic,sim,src", [
    ("LTKD", 0.826, 0),
    ("agent 上下文管理", 0.874, 0),
])
def test_quality_zero_is_not_known_and_stays_beginner(topic, sim, src):
    """Acceptance: quality=0 node never gets `known`; level stays beginner."""
    h = _handler([_node(topic, sim, 0.0, src)])
    r = h.check_confidence(topic)
    assert r["coverage"] != "known"
    assert r["level"] == "beginner"


@pytest.mark.parametrize("topic,sim", [("LTKD", 0.826), ("agent 上下文管理", 0.874)])
def test_quality_zero_confidence_is_low(topic, sim):
    """A zero-quality node must score clearly low (< 0.25), not ~0.41."""
    h = _handler([_node(topic, sim, 0.0, 0)])
    r = h.check_confidence(topic)
    assert r["confidence"] < 0.25


def test_zero_quality_separated_from_low_quality():
    """quality=0 must be numerically distinct from a real low-quality node."""
    h0 = _handler([_node("LTKD", 0.826, 0.0, 0)])
    c0 = h0.check_confidence("LTKD")["confidence"]

    h45 = _handler([_node("LLM", 0.752, 4.5, 1)])
    c45 = h45.check_confidence("LLM")["confidence"]

    assert c45 - c0 > 0.2, (
        f"quality=0 ({c0}) must be well below quality=4.5 ({c45}) — "
        "this is the 0b separation requirement"
    )


# ------------------------------------------------- C0-B protection (must hold)

def test_c0b_quality_zero_not_erased_to_zero():
    """C0-B: strong similarity with quality=0 must stay NON-zero."""
    h = _handler([_node("LTKD", 0.83, 0.0, 0)])
    r = h.check_confidence("LTKD")
    assert r["confidence"] > 0.0


@pytest.mark.parametrize("sim,quality,expected", [
    (0.750, 9.0, 0.712),   # RAG
    (0.753, 7.0, 0.640),   # transformer attention
    (0.752, 4.5, 0.545),   # LLM
    (0.750, 9.6, 0.735),   # embedding
])
def test_quality_positive_formula_unchanged(sim, quality, expected):
    """批0b must NOT alter the C0-B curve for quality>0."""
    h = _handler([_node("T", sim, quality, 2)])
    r = h.check_confidence("T")
    assert abs(r["confidence"] - expected) < 0.005, (
        f"quality={quality} changed: {r['confidence']} != {expected}"
    )


def test_quality_positive_monotonic():
    """C0-B monotonicity for quality>0 is preserved."""
    prev = -1.0
    for q in [1.0, 4.5, 7.0, 9.0, 10.0]:
        h = _handler([_node("T", 0.8, q, 2)])
        c = h.check_confidence("T")["confidence"]
        assert c >= prev, f"not monotonic at quality={q}"
        prev = c
