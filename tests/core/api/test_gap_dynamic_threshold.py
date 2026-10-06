"""批4b-2 (v0.3.6): 动态阈值测试 —— 队列健康度驱动的自适应入队闸门。

覆盖：
  * 三档规则（常态/收紧/放松）
  * 滞回（hysteresis）防颤振
  * 硬上下限钳制
  * 信号不可得 → 回退静态默认（行为零回归）
  * GapConfig.resolve() 的优先级（overrides > dynamic > default）
  * QueueStorage 两个新可观测统计方法
"""
import os
import tempfile
import time
import uuid

import pytest

from core.api.gap_calculator import (
    DEFAULT_GAP_THRESHOLD,
    GapConfig,
    THRESHOLD_FLOOR,
    THRESHOLD_CEIL,
    THRESHOLD_LOOSE,
    THRESHOLD_NORMAL,
    THRESHOLD_TIGHT,
    dynamic_threshold,
)
from core.tools.queue_tools import QueueStorage


# =============================================================================
# 三档规则
# =============================================================================

class TestDynamicThresholdTiers:
    def test_normal_tier(self):
        """中等积压 → 常态阈值。"""
        r = dynamic_threshold({"pending": 50, "recent_done": 20})
        assert r["gap_threshold"] == THRESHOLD_NORMAL
        assert "adaptive" in r["source"]

    def test_tight_tier(self):
        """高积压 + 低消费 → 收紧阈值。"""
        r = dynamic_threshold({"pending": 150, "recent_done": 3})
        assert r["gap_threshold"] == THRESHOLD_TIGHT

    def test_loose_tier(self):
        """低积压 → 放松阈值。"""
        r = dynamic_threshold({"pending": 5, "recent_done": 20})
        assert r["gap_threshold"] == THRESHOLD_LOOSE

    def test_high_backlog_but_fast_consume_stays_normal(self):
        """积压高但消费也快 → 不收紧（乘法条件，两因子都需满足）。"""
        r = dynamic_threshold({"pending": 150, "recent_done": 50})
        assert r["gap_threshold"] == THRESHOLD_NORMAL

    def test_low_consume_but_low_backlog_stays_loose(self):
        """消费慢但无积压 → 仍放松（无货可探）。"""
        r = dynamic_threshold({"pending": 5, "recent_done": 1})
        assert r["gap_threshold"] == THRESHOLD_LOOSE


# =============================================================================
# 滞回（防颤振）
# =============================================================================

class TestHysteresis:
    def test_tight_sticks_below_raw_trigger(self):
        """已收紧 + pending 略低于触发点（未越滞回带）→ 保持收紧。"""
        r = dynamic_threshold(
            {"pending": 99, "recent_done": 3}, prev_threshold=THRESHOLD_TIGHT
        )
        assert r["gap_threshold"] == THRESHOLD_TIGHT

    def test_tight_releases_after_band(self):
        """pending 回落到滞回带以下 → 解除收紧。"""
        r = dynamic_threshold(
            {"pending": 90, "recent_done": 3}, prev_threshold=THRESHOLD_TIGHT
        )
        assert r["gap_threshold"] == THRESHOLD_NORMAL

    def test_loose_sticks_above_raw_trigger(self):
        """已放松 + pending 略高于触发点（未越带）→ 保持放松。"""
        r = dynamic_threshold(
            {"pending": 21, "recent_done": 20}, prev_threshold=THRESHOLD_LOOSE
        )
        assert r["gap_threshold"] == THRESHOLD_LOOSE

    def test_loose_releases_after_band(self):
        """pending 回升越过滞回带 → 解除放松。"""
        r = dynamic_threshold(
            {"pending": 22, "recent_done": 20}, prev_threshold=THRESHOLD_LOOSE
        )
        assert r["gap_threshold"] == THRESHOLD_NORMAL

    def test_no_prev_no_hysteresis(self):
        """首轮无 prev → 按原始触发点判档。"""
        r = dynamic_threshold({"pending": 150, "recent_done": 3}, prev_threshold=None)
        assert r["gap_threshold"] == THRESHOLD_TIGHT


# =============================================================================
# 硬上下限 & 回退
# =============================================================================

class TestBoundsAndFallback:
    def test_signal_unavailable_falls_back(self):
        """信号不可得（None）→ 回退静态默认，行为零回归。"""
        r = dynamic_threshold({"pending": None, "recent_done": None})
        assert r["gap_threshold"] == DEFAULT_GAP_THRESHOLD
        assert "static-default" in r["source"]

    def test_threshold_within_bounds(self):
        """任何输入下阈值都不越硬区间。"""
        for p, d in [(0, 0), (9999, 0), (0, 9999), (150, 0)]:
            r = dynamic_threshold({"pending": p, "recent_done": d})
            assert THRESHOLD_FLOOR <= r["gap_threshold"] <= THRESHOLD_CEIL

    def test_resolve_dynamic_false_is_static(self):
        """dynamic=False → 强制静态默认（向后兼容 / 可重现）。"""
        cfg = GapConfig.resolve(dynamic=False)
        assert cfg.gap_threshold == DEFAULT_GAP_THRESHOLD
        assert cfg.source == "static-default"

    def test_resolve_source_labels_adaptive(self):
        """source 标注：动态来源应标 adaptive-driven，不误标 static。"""
        cfg = GapConfig.resolve(
            queue_stats={"pending": 150, "recent_done": 3}
        )
        assert cfg.gap_threshold == THRESHOLD_TIGHT
        assert "adaptive" in cfg.source

    def test_resolve_overrides_labeled(self):
        """显式 overrides → source 标 overrides。"""
        cfg = GapConfig.resolve({"gap_threshold": 0.5}, dynamic=False)
        assert cfg.source == "overrides"

    def test_resolve_overrides_win(self):
        """显式 overrides 优先级最高，且受硬限钳制。"""
        cfg = GapConfig.resolve({"gap_threshold": 0.99}, dynamic=False)
        assert cfg.gap_threshold == THRESHOLD_CEIL  # 钳到 0.80

    def test_resolve_overrides_beat_dynamic(self):
        """overrides 存在时不被动态覆盖。"""
        cfg = GapConfig.resolve(
            {"gap_threshold": 0.5}, queue_stats={"pending": 150, "recent_done": 3}
        )
        assert cfg.gap_threshold == 0.5


# =============================================================================
# QueueStorage 可观测统计方法
# =============================================================================

@pytest.fixture
def queue_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = QueueStorage(db_path=os.path.join(tmpdir, "q.db"))
        storage.initialize()
        yield storage
        storage.close()


class TestQueueHealthSignals:
    def test_pending_count(self, queue_storage):
        assert queue_storage.pending_count() == 0
        for i in range(3):
            queue_storage.add_item(f"topic {i}", priority=5)
        assert queue_storage.pending_count() == 3

    def test_pending_count_excludes_done(self, queue_storage):
        item_id = queue_storage.add_item("t", priority=5)
        holder = str(uuid.uuid4())
        queue_storage.claim_item(item_id, holder)
        queue_storage.mark_done(item_id, holder)
        assert queue_storage.pending_count() == 0

    def test_done_in_last_counts_recent(self, queue_storage):
        item_id = queue_storage.add_item("t", priority=5)
        holder = str(uuid.uuid4())
        queue_storage.claim_item(item_id, holder)
        queue_storage.mark_done(item_id, holder)
        assert queue_storage.done_in_last(hours=1) == 1
        # 窗口为 0 小时 → 不应包含（严格 >= cutoff=now）
        # 用极小窗口验证边界不崩
        assert queue_storage.done_in_last(hours=0.0) in (0, 1)

    def test_done_in_last_excludes_old(self, queue_storage):
        """completed_at 远早于窗口 → 不计入。"""
        item_id = queue_storage.add_item("t", priority=5)
        holder = str(uuid.uuid4())
        queue_storage.claim_item(item_id, holder)
        queue_storage.mark_done(item_id, holder)
        # 直接改 completed_at 到 2 小时前
        conn = queue_storage._get_connection()
        conn.execute(
            "UPDATE queue SET completed_at = ? WHERE id = ?",
            (time.time() - 7200, item_id),
        )
        conn.commit()
        assert queue_storage.done_in_last(hours=1) == 0
        assert queue_storage.done_in_last(hours=3) == 1

    def test_signals_never_raise(self, queue_storage):
        """纪律：统计方法绝不抛异常。"""
        queue_storage.close()
        # 已关闭的连接 → 应返回安全默认而非抛异常
        assert queue_storage.pending_count() == 0
        assert queue_storage.done_in_last(hours=1) == 0
