"""批0 (v0.3.6): E1 substance-gate regression tests.

Locks the fix for the 2026-10-03 defect: semantic retrieval returned a GHOST
node (high quality, empty content) for a topic the KG has no node for, and the
four-state judge trusted it.

    '知识图谱'       → 'Knowledge Distillation' (quality=8.0, content="") → must be unknown
    'Knowledge Graph' → same ghost node                                     → must be unknown
    'video recommendation bias' → a real node with content → must NOT be downgraded

These are offline (ghost/real nodes are constructed in-memory), so they run
without Neo4j. The live behaviour was additionally verified against the real
KG on 2026-10-03.

Version note (test-file labelling convention, v0.3.6): file tagged 批0.
"""
import pytest

from core.api.topic_consistency import (
    check_match_substance,
    TRUSTWORTHY,
    EMPTY,
)


# --------------------------------------------------------------- unit: gate

def test_ghost_node_is_not_dependable():
    """The exact 知识图谱 case: quality high, content empty → reject."""
    ghost = {
        "topic": "Knowledge Distillation",
        "content": "",
        "quality": 8.0,
        "source_urls": [],
        "score": 0.7855,
    }
    v = check_match_substance(ghost, query="知识图谱")
    assert v.dependable is False
    assert v.verdict == EMPTY
    assert v.signals["has_content"] is False
    assert v.signals["node_quality"] == 8.0  # quality alone must not save it


def test_real_node_is_dependable():
    real = {
        "topic": "Simulating User Watch-Time to Investigate Bias in YouTube Shorts Recommendations",
        "content": "A simulation-based auditing approach that models user watch-time behavior...",
        "quality": 6.0,
        "source_urls": ["https://arxiv.org/abs/2507.04605"],
        "score": 0.7657,
    }
    v = check_match_substance(real, query="video recommendation bias")
    assert v.dependable is True
    assert v.verdict == TRUSTWORTHY


def test_definition_only_is_enough():
    """Definition/core non-empty (content empty) still counts as substance."""
    node = {"topic": "X", "content": "", "definition": "some definition",
            "quality": 5.0, "source_urls": []}
    assert check_match_substance(node, query="x").dependable is True


def test_core_only_is_enough():
    node = {"topic": "X", "content": "", "definition": "", "core": "core text",
            "quality": 5.0, "source_urls": []}
    assert check_match_substance(node, query="x").dependable is True


def test_sources_without_content_is_not_enough():
    """Sources alone give the judge nothing to read → still a ghost."""
    node = {"topic": "X", "content": "", "definition": "", "core": "",
            "quality": 7.0, "source_urls": ["http://example.com"]}
    assert check_match_substance(node, query="x").dependable is False


def test_whitespace_content_is_empty():
    node = {"topic": "X", "content": "   \n\t ", "quality": 9.0, "source_urls": []}
    assert check_match_substance(node, query="x").dependable is False


def test_no_match_is_not_dependable():
    assert check_match_substance(None, query="x").dependable is False


# ------------------------------------------------------ handler integration

def test_handler_downgrades_ghost_match_to_unknown():
    """End-to-end (mocked retrieval): ghost hit → coverage=unknown, conf=0."""
    from unittest.mock import Mock
    from core.api.host_agent_integration import KnowledgeConfidenceHandler

    repo = Mock()
    repo.query_knowledge_semantic_sync = Mock(return_value=[{
        "topic": "Knowledge Distillation",
        "content": "",
        "quality": 8.0,
        "source_urls": [],
        "score": 0.7855,
    }])
    h = KnowledgeConfidenceHandler()
    h._kg_repository = repo

    r = h.check_confidence("知识图谱")
    assert r["coverage"] == "unknown"
    assert r["confidence"] == 0.0
    assert r["rejected_match"] == "Knowledge Distillation"


def test_handler_keeps_real_match():
    """A real node must NOT be downgraded by the substance gate."""
    from unittest.mock import Mock
    from core.api.host_agent_integration import KnowledgeConfidenceHandler

    repo = Mock()
    repo.query_knowledge_semantic_sync = Mock(return_value=[{
        "topic": "Simulating User Watch-Time to Investigate Bias in YouTube Shorts Recommendations",
        "content": "A simulation-based auditing approach ...",
        "quality": 6.0,
        "source_urls": ["https://arxiv.org/abs/2507.04605"],
        "score": 0.90,
    }])
    h = KnowledgeConfidenceHandler()
    h._kg_repository = repo

    r = h.check_confidence("video recommendation bias")
    assert r["coverage"] in ("known", "partial")
    assert "rejected_match" not in r
    assert r["confidence"] > 0.0
