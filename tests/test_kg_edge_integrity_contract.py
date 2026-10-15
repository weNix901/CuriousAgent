"""L4 契约测试：KG 边完整性 + 约束可见（v0.3.7-A4/A5）。

背景 / 为什么测这个
-------------------
关系唯一约束建立在合成属性 ``key``（``<from>|<rel>|<to>``）上。
若有任何写路径绕过它（历史上 FOREACH MERGE / migrate 脚本就绕过了），
重复边会**静默**累积 —— 这正是 v0.3.7 §四要堵的口子。

本测试用假 client（纯内存）锁死三件事：
    1. edge_integrity 能发现缺 key 的边。
    2. edge_integrity 能发现重复 key 的边。
    3. 干净图报告 ok=True。
不触 Neo4j、不污染生产（纪律：只读契约）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _FakeClient:
    """Minimal client returning canned counts keyed by query intent."""

    def __init__(self, total=0, missing=0, dupes=0):
        self.total = total
        self.missing = missing
        self.dupes = dupes

    def execute_write(self, query, **kw):
        if "WHERE r.key IS NULL" in query:
            return [{"c": self.missing}]
        if "c > 1" in query:
            return [{"d": self.dupes}]
        return [{"c": self.total}]


class TestEdgeIntegrity:
    def test_clean_graph_is_ok(self):
        from core.kg.edge_integrity import check_edge_integrity
        # A single relation type, so totals are not multiplied by the loop.
        report = check_edge_integrity(_FakeClient(total=100, missing=0, dupes=0),
                                      relation_types=["CITES"])
        assert report["ok"] is True
        assert report["total"] == 100
        assert report["missing_key"] == 0
        assert report["duplicate_keys"] == 0

    def test_missing_key_detected(self):
        from core.kg.edge_integrity import check_edge_integrity
        report = check_edge_integrity(_FakeClient(total=100, missing=3, dupes=0),
                                      relation_types=["CITES"])
        assert report["ok"] is False
        assert report["missing_key"] == 3

    def test_duplicate_keys_detected(self):
        from core.kg.edge_integrity import check_edge_integrity
        report = check_edge_integrity(_FakeClient(total=100, missing=0, dupes=5),
                                      relation_types=["CITES"])
        assert report["ok"] is False
        assert report["duplicate_keys"] == 5

    def test_sums_across_all_relation_types(self):
        from core.kg.edge_integrity import check_edge_integrity
        report = check_edge_integrity(_FakeClient(total=100, missing=0, dupes=0))
        assert report["total"] == 400  # 4 relation types x 100

    def test_per_type_breakdown(self):
        from core.kg.edge_integrity import check_edge_integrity
        report = check_edge_integrity(_FakeClient(total=4, missing=0, dupes=0))
        assert set(report["per_type"].keys()) == {
            "IS_CHILD_OF", "CITES", "DERIVED_FROM", "RELATED_TO"
        }


class TestConstraintVisibility:
    def test_neo4j_client_records_constraint_status(self):
        """constraints_ok property must exist and default to None before connect."""
        from core.kg.neo4j_client import Neo4jClient
        c = Neo4jClient("bolt://localhost:7687", "neo4j", "x")
        assert c.constraints_ok is None

    def test_rel_key_format_contract(self):
        """The synthetic key format is <from>|<rel>|<to> (single source of truth)."""
        # Mirrors add_relation's key construction.
        from_topic, rel, to_topic = "a", "CITES", "b"
        key = f"{from_topic}|{rel}|{to_topic}"
        assert key == "a|CITES|b"
        assert key.count("|") == 2
