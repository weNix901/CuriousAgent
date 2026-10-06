"""批5 C3-C (v0.3.6): Retrieval hit log 测试。

覆盖：
  * 真命中（known/partial）落库 + matched=1
  * 未命中（unknown/void）落库 + matched=0
  * 统计（total/hits/misses/hit_rate/by_coverage）
  * 按 query_topic / matched_topic 过滤
  * 幂等性无关（每次检索都记一条事件，不去重 —— 这是"频次"信号）
  * 纪律：绝不抛异常（坏路径静默返回）
"""
import os
import tempfile

import pytest

from core.api.retrieval_store import (
    HIT_STATES,
    hit_stats,
    list_retrievals,
    record_retrieval,
)


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "ops.db")


class TestRecordRetrieval:
    def test_known_hit(self, db):
        ok = record_retrieval(
            "RAG", "known", matched_topic="Retrieval Augmented Generation",
            similarity=0.9, quality=8.0, source_count=3, db_path=db,
        )
        assert ok is True
        rows = list_retrievals(db_path=db)
        assert len(rows) == 1
        r = rows[0]
        assert r["query_topic"] == "RAG"
        assert r["matched_topic"] == "Retrieval Augmented Generation"
        assert r["coverage"] == "known"
        assert r["matched"] == 1

    def test_partial_is_hit(self, db):
        record_retrieval("X", "partial", matched_topic="X-full", similarity=0.6, db_path=db)
        rows = list_retrievals(db_path=db)
        assert rows[0]["matched"] == 1

    def test_unknown_is_miss(self, db):
        record_retrieval("知识图谱", "unknown", db_path=db)
        rows = list_retrievals(db_path=db)
        assert rows[0]["matched"] == 0
        assert rows[0]["matched_topic"] is None

    def test_void_is_miss(self, db):
        record_retrieval("失败话题", "void", db_path=db)
        rows = list_retrievals(db_path=db)
        assert rows[0]["matched"] == 0

    def test_coverage_missing_matched_topic_is_miss(self, db):
        """coverage=known 但 matched_topic 为空 → 不算真命中。"""
        record_retrieval("X", "known", matched_topic=None, db_path=db)
        rows = list_retrievals(db_path=db)
        assert rows[0]["matched"] == 0

    def test_empty_query_rejected(self, db):
        assert record_retrieval("", "known", matched_topic="x", db_path=db) is False
        assert record_retrieval("   ", "known", matched_topic="x", db_path=db) is False

    def test_each_retrieval_records_event(self, db):
        """每次检索都记一条（频次信号），不去重。"""
        for _ in range(3):
            record_retrieval("RAG", "known", matched_topic="RAG", db_path=db)
        assert len(list_retrievals(db_path=db)) == 3


class TestListRetrievals:
    def test_filter_by_query_topic(self, db):
        record_retrieval("A", "known", matched_topic="A", db_path=db)
        record_retrieval("B", "unknown", db_path=db)
        rows = list_retrievals(query_topic="A", db_path=db)
        assert len(rows) == 1
        assert rows[0]["query_topic"] == "A"

    def test_filter_by_matched_topic(self, db):
        record_retrieval("A", "known", matched_topic="Shared", db_path=db)
        record_retrieval("B", "known", matched_topic="Shared", db_path=db)
        record_retrieval("C", "known", matched_topic="Other", db_path=db)
        rows = list_retrievals(matched_topic="Shared", db_path=db)
        assert len(rows) == 2

    def test_only_hits(self, db):
        record_retrieval("A", "known", matched_topic="A", db_path=db)
        record_retrieval("B", "unknown", db_path=db)
        rows = list_retrievals(only_hits=True, db_path=db)
        assert len(rows) == 1
        assert rows[0]["query_topic"] == "A"

    def test_limit(self, db):
        for i in range(10):
            record_retrieval(f"t{i}", "known", matched_topic=f"t{i}", db_path=db)
        assert len(list_retrievals(limit=5, db_path=db)) == 5


class TestHitStats:
    def test_stats_mixed(self, db):
        record_retrieval("A", "known", matched_topic="A", db_path=db)
        record_retrieval("B", "partial", matched_topic="B", db_path=db)
        record_retrieval("C", "unknown", db_path=db)
        record_retrieval("D", "void", db_path=db)
        s = hit_stats(db_path=db)
        assert s["total"] == 4
        assert s["hits"] == 2
        assert s["misses"] == 2
        assert s["hit_rate"] == 0.5
        assert s["by_coverage"]["known"] == 1
        assert s["by_coverage"]["unknown"] == 1
        assert s["by_coverage"]["void"] == 1

    def test_stats_empty(self, db):
        s = hit_stats(db_path=db)
        assert s["total"] == 0
        assert s["hit_rate"] == 0.0


class TestDiscipline:
    def test_never_raises_on_bad_path(self):
        """坏 db 路径 → 静默返回，不抛异常。"""
        bad = "/proc/nonexistent_dir_xyz/ops.db"
        assert record_retrieval("X", "known", matched_topic="X", db_path=bad) is False
        assert list_retrievals(db_path=bad) == []
        s = hit_stats(db_path=bad)
        assert s["total"] == 0

    def test_hit_states_constant(self):
        assert set(HIT_STATES) == {"known", "partial"}
