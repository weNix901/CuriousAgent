"""L4 契约测试：残留守卫 — 测试产物绝不进入探索循环（v0.3.7-D1）。

背景 / 为什么测这个
-------------------
OrphanScan 会挑选 KG 里 quality>=7、status=done 的孤立节点重探。测试残留
（TestTopicE2E / test trim / force-delete 等）恰好是 "done + 高质量 + 零关系"
—— 与合法孤儿的特征完全重叠。

更糟的是 add_curiosity 的 dedup 对 "empty done node" 是**故意放行**的
（允许重探），于是残留被反复入队，每轮被 claim 消耗一次循环，且 OrphanScan
还打印一句与实际不符的 "Enqueued orphan node"（日志说谎）。

本测试锁死两件事：
    1. _is_residue_topic() 命中测试产物，放行真实话题（不误伤）。
    2. add_curiosity() 对残留话题拒绝入队（队列零增长）。

设计纪律：用独立临时 DB，绝不污染 knowledge/queue.db。
"""
import os
import sys
import sqlite3
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 纯函数契约：残留判定
# ---------------------------------------------------------------------------
class TestIsResidueTopic:
    @pytest.mark.parametrize("topic", [
        "TestTopicE2E",
        "TestTopic",
        "test trim",
        "test deep",
        "test alpha",
        "force-delete",
        "structure-test",
        "contract-test",
        "stress_topic_1",
        "【test_data】depth-topic",
    ])
    def test_rejects_residue(self, topic):
        from core.knowledge_graph_compat import _is_residue_topic
        assert _is_residue_topic(topic) is True, f"should reject: {topic}"

    @pytest.mark.parametrize("topic", [
        "Is MDPI Peer Reviewed or Predatory? — CASRAI",
        "RoboJEPA: Scaling Robotic Learning",
        "Contract Test",  # 真·话题（对比 contract-test）
        "STF Milestone 4: Parameterized test classes",
        "Attention Mechanism",
        "",
    ])
    def test_allows_real_topics(self, topic):
        from core.knowledge_graph_compat import _is_residue_topic
        assert _is_residue_topic(topic) is False, f"should allow: {topic}"


# ---------------------------------------------------------------------------
# 副作用契约：add_curiosity 对残留拒绝入队
# ---------------------------------------------------------------------------
class TestAddCuriosityResidueGuard:
    @pytest.fixture
    def temp_queue(self, monkeypatch):
        """把 QueueStorage 的默认 DB 指向临时文件。"""
        from core.tools import queue_tools
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(path)
        orig = queue_tools.QueueStorage.__init__

        def patched(self, db_path=None):
            orig(self, db_path=path)

        monkeypatch.setattr(queue_tools.QueueStorage, "__init__", patched)
        yield path
        for p in (path, path + "-wal", path + "-shm"):
            if os.path.exists(p):
                os.unlink(p)

    def test_residue_not_enqueued(self, temp_queue):
        from core import knowledge_graph_compat as kg
        kg.add_curiosity(
            topic="TestTopicE2E",
            reason="OrphanScan: high-quality isolated node (quality=7.0)",
            relevance=7.0,
            depth=7.0,
        )
        # The guard rejects BEFORE any DB write, so the queue table may not even
        # exist yet. Treat "no table" as 0 rows — that is the expected pass state.
        conn = sqlite3.connect(temp_queue)
        try:
            n = conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]
        except sqlite3.OperationalError:
            n = 0
        conn.close()
        assert n == 0, "residue topic must not enter the queue"

    def test_real_topic_enqueued(self, temp_queue):
        from core import knowledge_graph_compat as kg
        kg.add_curiosity(
            topic="RoboJEPA: Scaling Robotic Learning",
            reason="OrphanScan: high-quality isolated node (quality=7.0)",
            relevance=7.0,
            depth=7.0,
        )
        conn = sqlite3.connect(temp_queue)
        n = conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]
        conn.close()
        assert n == 1, "real topic must be enqueued"
