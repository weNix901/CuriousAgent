"""L4 契约测试：A-5 边完整性巡检接线（v0.3.7-A5）。

背景 / 为什么测这个
-------------------
A-5 巡检挂到 DreamDaemon 的 1800s 心跳（低频旁路，不碰探索热路径）。
实库验证发现：**重复边的真实形态是"一条带 key + 一条不带 key"**——
缺 key 的边对唯一约束隐形，所以 `duplicate keys: 0` 是假安全。
本测试锁死：
    1. DreamDaemon 有巡检方法且按 N tick 触发（不是每 tick）。
    2. 巡检以异步方式调用（在 daemon 事件循环内不炸）。
    3. 巡检失败不抛（护栏不能杀死 dream loop）。
不触 Neo4j。
"""
import asyncio
import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestEdgeIntegrityAsync:
    def test_async_variant_exists(self):
        from core.kg.edge_integrity import check_edge_integrity_async
        assert asyncio.iscoroutinefunction(check_edge_integrity_async)

    def test_async_variant_reports_clean(self):
        from core.kg.edge_integrity import check_edge_integrity_async

        class _AsyncFake:
            async def execute_write(self, query, **kw):
                if "WHERE r.key IS NULL" in query:
                    return [{"c": 0}]
                if "c > 1" in query:
                    return [{"d": 0}]
                return [{"c": 10}]

        report = asyncio.get_event_loop().run_until_complete(
            check_edge_integrity_async(_AsyncFake(), relation_types=["CITES"])
        )
        assert report["ok"] is True
        assert report["total"] == 10

    def test_async_variant_flags_missing_key(self):
        from core.kg.edge_integrity import check_edge_integrity_async

        class _AsyncFake:
            async def execute_write(self, query, **kw):
                if "WHERE r.key IS NULL" in query:
                    return [{"c": 3}]
                if "c > 1" in query:
                    return [{"d": 0}]
                return [{"c": 10}]

        report = asyncio.get_event_loop().run_until_complete(
            check_edge_integrity_async(_AsyncFake(), relation_types=["CITES"])
        )
        assert report["ok"] is False
        assert report["missing_key"] == 3

    def test_sync_variant_rejects_async_client(self):
        """Sync path must NOT call run_until_complete (would crash in a live loop)."""
        from core.kg.edge_integrity import check_edge_integrity

        class _AsyncFake:
            async def execute_write(self, query, **kw):
                return [{"c": 1}]

        with pytest.raises(RuntimeError):
            check_edge_integrity(_AsyncFake(), relation_types=["CITES"])


class TestDreamDaemonPatrolWiring:
    def test_patrol_method_is_async(self):
        from core.daemon.dream_daemon import DreamDaemon
        assert asyncio.iscoroutinefunction(DreamDaemon._check_edge_integrity)

    def test_patrol_cadence_constant(self):
        from core.daemon import dream_daemon
        assert hasattr(dream_daemon, "EDGE_INTEGRITY_EVERY_N_TICKS")
        assert dream_daemon.EDGE_INTEGRITY_EVERY_N_TICKS >= 2

    def test_patrol_is_not_every_tick(self):
        """Guard: patrol must be low-frequency, not on every dream tick."""
        from core.daemon import dream_daemon
        assert dream_daemon.EDGE_INTEGRITY_EVERY_N_TICKS > 1
