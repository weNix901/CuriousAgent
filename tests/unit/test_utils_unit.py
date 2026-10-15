"""Unit test: pure logic sanity (v0.3.7 B-3 layer smoke).

Offline only. Proves tests/unit/ runs green with no Neo4j / no production DB.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_rel_key_composition():
    """Relation key format is <from>|<rel>|<to> (single source of truth)."""
    key = f"{'a'}|{'CITES'}|{'b'}"
    assert key == "a|CITES|b"


def test_residue_guard_offline():
    """Residue guard is a pure function — callable with zero DB."""
    from core.knowledge_graph_compat import _is_residue_topic
    assert _is_residue_topic("TestTopicE2E") is True
    assert _is_residue_topic("Mixture of Experts routing") is False


def test_tmp_db_fixture_isolated(tmp_db):
    """The tmp_db fixture points somewhere temp, not production."""
    assert "knowledge/ops.db" not in tmp_db
    assert "knowledge/queue.db" not in tmp_db
